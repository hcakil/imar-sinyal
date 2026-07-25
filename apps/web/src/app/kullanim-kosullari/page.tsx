import type { Metadata } from "next";

export const metadata: Metadata = { title: "Kullanım koşulları" };

export default function TermsPage() {
  return (
    <section className="page-section legal-page">
      <article className="shell legal-copy">
        <span className="section-kicker">KULLANIM KOŞULLARI</span>
        <h1>Kaynak, doğruluk ve sorumluluk sınırı</h1>
        <p className="legal-updated">Son güncelleme: 25 Temmuz 2026</p>
        <h2>Bağımsız veri ürünü</h2>
        <p>
          İmarSinyal Ankara herhangi bir belediye veya kamu kurumunun resmî
          hizmeti değildir. Kayıtlar kamuya açık kaynakların otomatik
          işlenmesiyle oluşturulur.
        </p>
        <h2>Resmî belge değildir</h2>
        <p>
          Özetler, etki puanları ve AI tarafından çıkarılan alanlar bilgi amaçlıdır;
          imar durumu belgesi, hukuki görüş veya yatırım tavsiyesi oluşturmaz.
          İşlem yapmadan önce resmî kaynağı ve yetkili kurum kayıtlarını kontrol
          etmeniz gerekir.
        </p>
        <h2>Hata bildirimi</h2>
        <p>
          Kaynak servislerin değişmesi, belgelerin kaldırılması veya otomatik
          analiz hataları nedeniyle eksik ya da gecikmiş kayıt oluşabilir. Her
          değişiklik sayfası mümkün olduğunda asıl belge bağlantısını gösterir.
        </p>
        <h2>Kabul edilebilir kullanım</h2>
        <p>
          Hizmeti bozacak otomatik istekler, güvenlik kontrollerini aşma girişimi
          ve içeriklerin kaynağı gizlenerek yeniden satılması yasaktır.
        </p>
      </article>
    </section>
  );
}
