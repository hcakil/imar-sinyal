import Link from "next/link";
import { EventCard } from "@/components/event-card";
import { NewsletterForm } from "@/components/newsletter-form";
import { listEvents } from "@/lib/events";

export const revalidate = 900;

export default async function HomePage() {
  const events = await listEvents({}, 100);
  const featured = [...events]
    .sort((a, b) => b.impact_score - a.impact_score)
    .slice(0, 3);
  const activeCount = events.filter((event) => event.stage === "on_appeal").length;
  const districtCount = new Set(events.map((event) => event.district)).size;
  const evidenceCount = events.filter(
    (event) => event.publication_status === "verified_ai",
  ).length;

  return (
    <>
      <section className="hero">
        <div className="hero-grid-bg" aria-hidden="true" />
        <div className="shell hero-grid">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="live-dot" />
              Ankara planlama süreçleri · her gün güncellenir
            </div>
            <h1>
              İmar değişikliklerini
              <span> belge belge aramayın.</span>
            </h1>
            <p className="hero-lead">
              Meclis kararlarını ve askı ilanlarını otomatik okuyup ada/parsel,
              plan aşaması ve yapılaşma koşullarıyla tek akışta gösteriyoruz.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary" href="/degisiklikler">
                Değişiklikleri incele <span aria-hidden="true">→</span>
              </Link>
              <Link className="button button-ghost" href="/bulten">
                Haftalık özeti al
              </Link>
            </div>
            <div className="trust-line">
              <span>✓ Resmî kaynak bağlantısı</span>
              <span>✓ Kanıt sayfası</span>
              <span>✓ Ücretsiz genel akış</span>
            </div>
          </div>
          <div className="signal-panel" aria-label="Güncel veri özeti">
            <div className="signal-panel-header">
              <div>
                <span className="panel-kicker">CANLI ÖZET</span>
                <strong>Ankara İmar Nabzı</strong>
              </div>
              <span className="updated">25 Tem 2026</span>
            </div>
            <div className="signal-map">
              <div className="district-shape shape-one">
                <span>Çankaya</span>
                <i className="signal-point signal-high" />
              </div>
              <div className="district-shape shape-two">
                <span>Mamak</span>
                <i className="signal-point signal-high" />
              </div>
              <div className="district-shape shape-three">
                <span>Yenimahalle</span>
                <i className="signal-point signal-medium" />
              </div>
              <div className="district-shape shape-four">
                <span>Sincan</span>
                <i className="signal-point signal-low" />
              </div>
            </div>
            <div className="signal-stats">
              <div>
                <strong>{activeCount}</strong>
                <span>aktif askı</span>
              </div>
              <div>
                <strong>{districtCount}</strong>
                <span>ilçe</span>
              </div>
              <div>
                <strong>{evidenceCount}</strong>
                <span>kanıtlı analiz</span>
              </div>
            </div>
            <p className="panel-note">
              <span aria-hidden="true">i</span>
              Bu ekran resmî belge yerine geçmez; her kayıt asıl kaynağa bağlanır.
            </p>
          </div>
        </div>
      </section>

      <section className="proof-strip">
        <div className="shell proof-grid">
          <div>
            <strong>{events.length}</strong>
            <span>örnek olay normalize edildi</span>
          </div>
          <div>
            <strong>3</strong>
            <span>plan ölçeği izleniyor</span>
          </div>
          <div>
            <strong>7/24</strong>
            <span>kaynak kontrolü</span>
          </div>
          <div>
            <strong>0</strong>
            <span>kanıtsız yatırım iddiası</span>
          </div>
        </div>
      </section>

      <section className="section latest-section">
        <div className="shell">
          <div className="section-heading split-heading">
            <div>
              <span className="section-kicker">ÖNE ÇIKAN SİNYALLER</span>
              <h2>Bu hafta incelenmesi gerekenler</h2>
              <p>
                Ham ilan kalabalığı yerine, kaynağına bağlı ve etki puanıyla
                sıralanmış değişiklikler.
              </p>
            </div>
            <Link className="text-link" href="/degisiklikler">
              Tüm akışı aç <span aria-hidden="true">→</span>
            </Link>
          </div>
          <div className="event-grid">
            {featured.map((event) => (
              <EventCard event={event} key={event.id} />
            ))}
          </div>
        </div>
      </section>

      <section className="section process-section" id="nasil-calisir">
        <div className="shell">
          <div className="section-heading centered">
            <span className="section-kicker">BELGEDEN SİNYALE</span>
            <h2>Bir ilanı karar verisine nasıl çeviriyoruz?</h2>
            <p>
              Otomasyon hızlı davranır; yayınlama kuralları belirsizliği gizlemek
              yerine görünür kılar.
            </p>
          </div>
          <div className="process-grid">
            <article>
              <span className="process-number">01</span>
              <div className="process-icon" aria-hidden="true">
                ⌁
              </div>
              <h3>Kaynağı izliyoruz</h3>
              <p>
                ABB meclis kararları ve aktif askı katmanları düzenli olarak
                snapshot&apos;lanır.
              </p>
            </article>
            <article>
              <span className="process-number">02</span>
              <div className="process-icon" aria-hidden="true">
                ≠
              </div>
              <h3>Farkı çıkarıyoruz</h3>
              <p>
                Ada/parsel, fonksiyon, emsal, TAKS ve yoğunluk birbirinden ayrı
                veri alanlarına dönüştürülür.
              </p>
            </article>
            <article>
              <span className="process-number">03</span>
              <div className="process-icon" aria-hidden="true">
                ✓
              </div>
              <h3>Kanıtla yayımlıyoruz</h3>
              <p>
                Doğrulanmayan değer saklanmaz; kullanıcı daima resmî belgeye ve
                ilgili sayfaya gider.
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className="section newsletter-section">
        <div className="shell newsletter-panel">
          <div>
            <span className="section-kicker section-kicker-light">
              PAZARTESİ 08:30
            </span>
            <h2>Ankara&apos;nın haftalık imar özetini alın.</h2>
            <p>
              Yalnızca anlamlı değişiklikler, bitişi yaklaşan askılar ve kaynak
              bağlantıları. Reklam yok, gürültü yok.
            </p>
          </div>
          <NewsletterForm />
        </div>
      </section>
    </>
  );
}
