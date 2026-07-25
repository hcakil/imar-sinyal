import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div>
          <div className="brand footer-brand">
            <span className="brand-mark" aria-hidden="true">
              İS
            </span>
            <span>
              <strong>İmarSinyal</strong>
              <small>Ankara</small>
            </span>
          </div>
          <p>
            Ankara&apos;daki planlama süreçlerini resmî kaynaklardan izleyen
            bağımsız veri ürünüdür.
          </p>
        </div>
        <div>
          <strong>Ürün</strong>
          <Link href="/degisiklikler">Değişiklik akışı</Link>
          <Link href="/bulten">Haftalık bülten</Link>
        </div>
        <div>
          <strong>Bilgi</strong>
          <Link href="/gizlilik">Gizlilik</Link>
          <Link href="/kullanim-kosullari">Kullanım koşulları</Link>
        </div>
      </div>
      <div className="shell footer-bottom">
        <span>© 2026 İmarSinyal Ankara</span>
          <span>
            AI analizi, resmî imar belgesi veya yatırım tavsiyesi değildir.
          </span>
      </div>
    </footer>
  );
}
