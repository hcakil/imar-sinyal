import { createHash } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { allowRequest } from "@/lib/rate-limit";
import { saveSubscriber, sendWelcomeEmail } from "@/lib/subscribers";
import { getPostHogClient } from "@/lib/posthog-server";

const subscriberSchema = z.object({
  email: z.string().trim().email().max(254),
  districts: z
    .array(z.string().trim().min(2).max(80))
    .max(3)
    .default([]),
  consent: z.literal(true),
  company: z.string().max(0).optional().or(z.literal("")),
});

export async function POST(request: NextRequest) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown";
  const rateKey = createHash("sha256").update(ip).digest("hex");
  if (!allowRequest(`subscribe:${rateKey}`, 5, 60_000)) {
    return NextResponse.json(
      { message: "Çok fazla deneme yapıldı. Bir dakika sonra tekrar deneyin." },
      { status: 429 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { message: "Geçersiz istek gövdesi." },
      { status: 400 },
    );
  }
  const parsed = subscriberSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { message: "Geçerli bir e-posta ve açık rıza gereklidir." },
      { status: 400 },
    );
  }

  const result = await saveSubscriber({
    email: parsed.data.email,
    districts: [...new Set(parsed.data.districts)],
    consentIpHash: rateKey,
  });

  try {
    await sendWelcomeEmail(parsed.data.email);
  } catch (error) {
    console.error("welcome_email_failed", error);
  }

  const posthog = getPostHogClient();
  if (posthog) {
    const distinctId =
      request.headers.get("X-PostHog-Distinct-Id") ||
      `subscriber:${rateKey}`;
    posthog.capture({
      distinctId,
      event: "newsletter_subscribed",
      properties: {
        district_count: parsed.data.districts.length,
        is_existing: result.existing,
        $session_id: request.headers.get("X-PostHog-Session-Id") || undefined,
      },
    });
    await posthog.flush();
  }

  return NextResponse.json(
    {
      ok: true,
      preview: result.preview,
      message: result.preview
        ? "Yerel önizleme kaydı doğrulandı. Firestore bağlandığında kalıcı olarak saklanacak."
        : result.existing
          ? "Tercihleriniz güncellendi."
          : "Kaydınız alındı. İlk bülten hazır olduğunda haber vereceğiz.",
    },
    { status: result.existing ? 200 : 201 },
  );
}
