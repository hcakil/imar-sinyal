import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { FieldValue } from "firebase-admin/firestore";
import { Resend } from "resend";
import { firestoreDb } from "./firestore";

const fallbackSecret = "local-development-only-change-this-secret";
const resendApiBase = "https://api.resend.com";

type ResendContact = {
  id: string;
  email?: string;
  unsubscribed?: boolean;
};

async function resendRequest<T>(
  apiKey: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${resendApiBase}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  const body = (await response.json().catch(() => null)) as
    | T
    | { message?: string }
    | null;
  if (!response.ok) {
    const message =
      body &&
      typeof body === "object" &&
      "message" in body &&
      typeof body.message === "string"
        ? body.message
        : `Resend API ${response.status}`;
    throw new Error(message);
  }
  return body as T;
}

async function syncResendContact({
  apiKey,
  segmentId,
  email,
  contactId,
}: {
  apiKey: string;
  segmentId: string;
  email: string;
  contactId?: string | null;
}): Promise<string> {
  let id = contactId || null;
  if (id) {
    try {
      await resendRequest(apiKey, `/contacts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({ unsubscribed: false }),
      });
    } catch {
      // A Resend account migration invalidates contact IDs stored by the
      // previous account. Resolve the contact again by email below.
      id = null;
    }
  }
  if (!id) {
    try {
      const created = await resendRequest<ResendContact>(apiKey, "/contacts", {
        method: "POST",
        body: JSON.stringify({
          email,
          unsubscribed: false,
          segments: [{ id: segmentId }],
        }),
      });
      id = created.id;
    } catch {
      const current = await resendRequest<ResendContact>(
        apiKey,
        `/contacts/${encodeURIComponent(email)}`,
      );
      id = current.id;
      if (current.unsubscribed) {
        await resendRequest(apiKey, `/contacts/${encodeURIComponent(id)}`, {
          method: "PATCH",
          body: JSON.stringify({ unsubscribed: false }),
        });
      }
    }
  }

  await resendRequest(
    apiKey,
    `/contacts/${encodeURIComponent(id)}/segments/${encodeURIComponent(segmentId)}`,
    { method: "POST" },
  );
  return id;
}

export function normalizeEmail(email: string): string {
  return email.trim().toLocaleLowerCase("en-US");
}

export function emailHash(email: string): string {
  return createHash("sha256").update(normalizeEmail(email)).digest("hex");
}

export function unsubscribeToken(email: string): string {
  const secret = process.env.UNSUBSCRIBE_SECRET || fallbackSecret;
  const normalized = normalizeEmail(email);
  const signature = createHmac("sha256", secret)
    .update(normalized)
    .digest("base64url");
  return Buffer.from(`${normalized}.${signature}`).toString("base64url");
}

export function readUnsubscribeToken(token: string): string | null {
  try {
    const decoded = Buffer.from(token, "base64url").toString("utf8");
    const splitAt = decoded.lastIndexOf(".");
    if (splitAt < 1) return null;
    const email = decoded.slice(0, splitAt);
    const supplied = Buffer.from(decoded.slice(splitAt + 1), "base64url");
    const secret = process.env.UNSUBSCRIBE_SECRET || fallbackSecret;
    const expected = createHmac("sha256", secret).update(email).digest();
    return supplied.length === expected.length &&
      timingSafeEqual(supplied, expected)
      ? email
      : null;
  } catch {
    return null;
  }
}

export async function saveSubscriber({
  email,
  districts,
  consentIpHash,
}: {
  email: string;
  districts: string[];
  consentIpHash: string;
}): Promise<{ preview: boolean; existing: boolean }> {
  const normalized = normalizeEmail(email);
  const id = emailHash(normalized);
  const db = firestoreDb();
  if (!db) return { preview: true, existing: false };

  const ref = db.collection("subscribers").doc(id);
  const existing = await ref.get();
  let resendContactId = existing.get("resend_contact_id") as
    | string
    | null
    | undefined;
  const resendKey = process.env.RESEND_API_KEY?.trim();
  const segmentId = process.env.RESEND_SEGMENT_ID?.trim();
  if (resendKey && segmentId) {
    try {
      resendContactId = await syncResendContact({
        apiKey: resendKey,
        segmentId,
        email: normalized,
        contactId: resendContactId,
      });
    } catch (error) {
      console.error("resend_contact_sync_failed", error);
    }
  }
  await ref.set(
    {
      email: normalized,
      email_hash: id,
      districts,
      status: "active",
      resend_contact_id: resendContactId || null,
      consent_version: "2026-07-25",
      consent_ip_hash: consentIpHash,
      consented_at: existing.exists
        ? existing.get("consented_at") || FieldValue.serverTimestamp()
        : FieldValue.serverTimestamp(),
      updated_at: FieldValue.serverTimestamp(),
    },
    { merge: true },
  );
  return { preview: false, existing: existing.exists };
}

export async function deactivateSubscriber(email: string): Promise<boolean> {
  const db = firestoreDb();
  if (!db) return true;
  const ref = db.collection("subscribers").doc(emailHash(email));
  const snapshot = await ref.get();
  if (!snapshot.exists) return true;
  await ref.set(
    {
      status: "unsubscribed",
      unsubscribed_at: FieldValue.serverTimestamp(),
      updated_at: FieldValue.serverTimestamp(),
    },
    { merge: true },
  );
  const resendKey = process.env.RESEND_API_KEY?.trim();
  if (resendKey) {
    try {
      const contactId = snapshot.get("resend_contact_id") as string | undefined;
      const contactKey = contactId || normalizeEmail(email);
      await resendRequest(
        resendKey,
        `/contacts/${encodeURIComponent(contactKey)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ unsubscribed: true }),
        },
      );
    } catch (error) {
      console.error("resend_contact_unsubscribe_failed", error);
    }
  }
  return true;
}

export async function sendWelcomeEmail(email: string): Promise<void> {
  const key = process.env.RESEND_API_KEY?.trim();
  const publicSends = process.env.NEWSLETTER_PUBLIC_SENDS === "true";
  const testRecipient = process.env.RESEND_TEST_RECIPIENT;
  const recipient = publicSends ? email : testRecipient;
  if (!key || !recipient) return;

  const siteUrl =
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  const token = unsubscribeToken(email);
  const resend = new Resend(key);
  await resend.emails.send({
    from:
      process.env.RESEND_FROM_EMAIL ||
      "İmarSinyal <onboarding@resend.dev>",
    to: recipient,
    subject: publicSends
      ? "İmarSinyal Ankara bültenine hoş geldiniz"
      : `[TEST] Yeni İmarSinyal kaydı: ${email}`,
    html: `
      <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#17352b">
        <p style="font-size:12px;letter-spacing:.14em;color:#b36b2c">İMARSİNYAL ANKARA</p>
        <h1 style="font-size:28px;line-height:1.2">Kaydınız tamamlandı.</h1>
        <p style="font-size:16px;line-height:1.6">
          Ankara'daki önemli imar kararlarını ve bitişi yaklaşan askıları
          her pazartesi kaynak bağlantılarıyla paylaşacağız.
        </p>
        <p><a href="${siteUrl}/degisiklikler" style="color:#b45424">Güncel değişiklikleri inceleyin →</a></p>
        <hr style="border:0;border-top:1px solid #e3ddd1;margin:32px 0">
        <p style="font-size:12px;color:#6b756f">
          Bu e-postayı istemiyorsanız
          <a href="${siteUrl}/api/unsubscribe?token=${token}">abonelikten ayrılın</a>.
        </p>
      </div>
    `,
  });
}
