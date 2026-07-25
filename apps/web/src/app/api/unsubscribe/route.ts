import { NextRequest, NextResponse } from "next/server";
import {
  deactivateSubscriber,
  readUnsubscribeToken,
} from "@/lib/subscribers";

async function handle(token: string | null) {
  if (!token) {
    return NextResponse.json({ message: "Geçersiz bağlantı." }, { status: 400 });
  }
  const email = readUnsubscribeToken(token);
  if (!email) {
    return NextResponse.json(
      { message: "Bağlantı geçersiz veya bozulmuş." },
      { status: 400 },
    );
  }
  await deactivateSubscriber(email);
  return new NextResponse(
    `<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Abonelik sonlandırıldı</title><body style="font-family:Arial,sans-serif;background:#f4f1e9;color:#17352b;padding:48px"><main style="max-width:560px;margin:auto;background:white;padding:40px;border-radius:16px"><p style="color:#b45424;font-weight:bold;letter-spacing:.12em">İMARSİNYAL ANKARA</p><h1>Aboneliğiniz sonlandırıldı.</h1><p>Bu adrese yeni bülten gönderilmeyecek.</p><a href="/" style="color:#b45424">Ana sayfaya dön →</a></main></body></html>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
}

export async function GET(request: NextRequest) {
  return handle(request.nextUrl.searchParams.get("token"));
}

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as { token?: string };
  return handle(body.token || null);
}
