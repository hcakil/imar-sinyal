import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell nav-shell">
        <Link className="brand" href="/" aria-label="İmarSinyal Ankara ana sayfa">
          <span className="brand-mark" aria-hidden="true">
            İS
          </span>
          <span>
            <strong>İmarSinyal</strong>
            <small>Ankara</small>
          </span>
        </Link>
        <nav className="main-nav" aria-label="Ana navigasyon">
          <Link href="/degisiklikler">Değişiklikler</Link>
          <Link href="/#nasil-calisir">Nasıl çalışır?</Link>
          <Link className="nav-cta" href="/bulten">
            Ücretsiz bülten
          </Link>
        </nav>
      </div>
    </header>
  );
}
