import type { Metadata } from "next";
import { NewsletterForm } from "@/components/newsletter-form";

export const metadata: Metadata = {
  title: "Ücretsiz Ankara İmar Bülteni",
  description:
    "Ankara'daki önemli imar değişikliklerini ve bitişi yaklaşan askıları her pazartesi e-posta ile alın.",
};

export default function NewsletterPage() {
  return (
    <section className="page-section bulletin-page">
      <div className="shell bulletin-grid">
        <div className="bulletin-copy">
          <span className="section-kicker">ÜCRETSİZ HAFTALIK ÖZET</span>
          <h1>İmar gündemini belge aramadan takip edin.</h1>
          <p className="page-lead">
            Her pazartesi 08:30&apos;da, Ankara&apos;da dikkat çeken plan
            kararlarını kaynak belgeleriyle birlikte gönderiyoruz.
          </p>
          <ul className="benefit-list">
            <li>
              <span>01</span>
              <div>
                <strong>Yüksek etkili değişiklikler</strong>
                <p>Fonksiyon ve yapılaşma koşulu sinyalleri önce gelir.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Bitişi yaklaşan askılar</strong>
                <p>İtiraz süresi dolmadan tarih ve kaynak görünür.</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>İlçe tercihi</strong>
                <p>En fazla üç öncelikli ilçeyi seçebilirsiniz.</p>
              </div>
            </li>
          </ul>
        </div>
        <div className="bulletin-form-card">
          <span className="form-card-kicker">KAYIT FORMU</span>
          <h2>İlk özeti kaçırmayın.</h2>
          <p>İstediğiniz zaman tek tıkla ayrılabilirsiniz.</p>
          <NewsletterForm mode="full" />
          <div className="privacy-note">
            E-posta adresiniz yalnızca İmarSinyal bülteni için kullanılır.
          </div>
        </div>
      </div>
    </section>
  );
}
