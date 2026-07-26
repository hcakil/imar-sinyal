import type { Metadata, Viewport } from "next";
import { AnalyticsConsent } from "@/components/analytics-consent";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL || "https://imarsinyal-ankara.web.app";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "İmarSinyal Ankara — İmar değişiklikleri tek akışta",
    template: "%s | İmarSinyal Ankara",
  },
  description:
    "Ankara'daki meclis kararlarını ve imar askılarını kaynak belgeleriyle takip edin. Ada/parsel, eski-yeni koşullar ve askı tarihleri tek ekranda.",
  applicationName: "İmarSinyal Ankara",
  openGraph: {
    type: "website",
    locale: "tr_TR",
    siteName: "İmarSinyal Ankara",
    title: "Ankara'da imar değişiklikleri tek akışta",
    description:
      "Meclis kararından askı sonuna kadar kaynak belgeli imar değişikliği takibi.",
    images: [
      {
        url: "/og.png",
        width: 1731,
        height: 909,
        alt: "İmarSinyal Ankara — İmar değişiklikleri kaynak belgeleriyle tek akışta",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "İmarSinyal Ankara",
    description:
      "Ankara'daki kaynak belgeli imar değişikliği akışı.",
    images: ["/og.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#102820",
  colorScheme: "light",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const posthogProjectToken = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN || "";
  const posthogHost =
    process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";
  return (
    <html lang="tr">
      <body>
        <SiteHeader />
        <main>{children}</main>
        <SiteFooter analyticsEnabled={posthogProjectToken.startsWith("phc_")} />
        <AnalyticsConsent
          projectToken={posthogProjectToken}
          apiHost={posthogHost}
        />
      </body>
    </html>
  );
}
