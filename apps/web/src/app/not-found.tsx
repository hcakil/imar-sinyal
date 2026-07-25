import Link from "next/link";

export default function NotFound() {
  return (
    <section className="page-section">
      <div className="shell empty-state not-found">
        <span className="section-kicker">404</span>
        <h1>Kayıt bulunamadı.</h1>
        <p>Aradığınız değişiklik kaldırılmış veya adresi değişmiş olabilir.</p>
        <Link className="button button-primary" href="/degisiklikler">
          Değişiklik akışına dön
        </Link>
      </div>
    </section>
  );
}
