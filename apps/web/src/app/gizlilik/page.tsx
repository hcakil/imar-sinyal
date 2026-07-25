import type { Metadata } from "next";

export const metadata: Metadata = { title: "Gizlilik ve KVKK" };

export default function PrivacyPage() {
  const contact = process.env.CONTACT_EMAIL || "iletisim@example.com";
  const controller =
    process.env.DATA_CONTROLLER_NAME || "İmarSinyal Ankara işletmecisi";
  return (
    <section className="page-section legal-page">
      <article className="shell legal-copy">
        <span className="section-kicker">GİZLİLİK</span>
        <h1>Gizlilik ve kişisel veri bilgilendirmesi</h1>
        <p className="legal-updated">Son güncelleme: 25 Temmuz 2026</p>
        <h2>Veri sorumlusu</h2>
        <p>
          Bu hizmet kapsamında veri sorumlusu {controller}&apos;dir. İletişim:
          {" "}
          <a href={`mailto:${contact}`}>{contact}</a>.
        </p>
        <h2>Hangi verileri işleriz?</h2>
        <p>
          Bültene kaydolduğunuzda e-posta adresiniz, açık rıza zamanınız,
          seçtiğiniz ilçeler ve kötüye kullanımı önlemek için sınırlı teknik
          kayıtlar işlenir. E-posta adresinin tek yönlü özeti sistemde mükerrer
          kayıt kontrolü için tutulabilir.
        </p>
        <h2>Amaç ve saklama</h2>
        <p>
          Veriler yalnızca İmarSinyal bültenini göndermek, teslimat durumunu
          izlemek ve hizmet güvenliğini sağlamak için kullanılır. Abonelikten
          ayrıldığınızda gönderim durdurulur; yasal zorunluluk bulunmayan
          kayıtlar makul süre içinde silinir veya anonimleştirilir.
        </p>
        <h2>Hizmet sağlayıcılar</h2>
        <p>
          Barındırma ve veri işleme için Google Cloud/Firebase, e-posta teslimatı
          için Resend kullanılabilir. Bu sağlayıcılar kendi güvenlik ve veri
          işleme şartlarına tabidir.
        </p>
        <h2>Haklarınız</h2>
        <p>
          Kişisel verilerinize erişme, düzeltme, silme ve işlemeye itiraz
          taleplerinizi yukarıdaki iletişim adresine gönderebilirsiniz. Her
          bültendeki bağlantıyla abonelikten çıkabilirsiniz.
        </p>
      </article>
    </section>
  );
}
