import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EventCard } from "@/components/event-card";
import {
  categoryLabel,
  formatDate,
  impactTone,
  publicationLabel,
  stageLabel,
} from "@/lib/format";
import { getEventBySlug, getEventsByIds } from "@/lib/events";
import type { MetricChange, PlanningEvent } from "@/lib/types";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event) return { title: "Değişiklik bulunamadı" };
  return {
    title: `${event.district} — ${event.title}`,
    description: event.summary,
    alternates: { canonical: `/degisiklik/${event.slug}` },
  };
}

function MetricRow({
  label,
  metric,
  verified,
}: {
  label: string;
  metric: MetricChange;
  verified: boolean;
}) {
  const hasValue = metric.old_value !== null || metric.new_value !== null;
  return (
    <div className="metric-row">
      <strong>{label}</strong>
      {verified && hasValue ? (
        <div className="metric-values">
          <span className={metric.old_value === null ? "metric-empty" : ""}>
            <small>Önceki</small>
            {metric.old_value ?? "Belirlenemedi"}
          </span>
          <i aria-hidden="true">→</i>
          <span className="metric-new">
            <small>Yeni</small>
            {metric.new_value ?? "Belirlenemedi"}
            {metric.unit ? ` ${metric.unit}` : ""}
          </span>
        </div>
      ) : (
        <span className="unverified-value">
          Belgede otomatik doğrulanamadı
        </span>
      )}
    </div>
  );
}

function EventTimeline({ event }: { event: PlanningEvent }) {
  return (
    <ol className="timeline">
      <li className={event.stage === "council_approved" ? "current" : "done"}>
        <span />
        <div>
          <strong>Meclis kararı</strong>
          <small>
            {event.source_kind === "council"
              ? formatDate(event.event_date)
              : "İlişkili karar aranıyor"}
          </small>
        </div>
      </li>
      <li className={event.stage === "on_appeal" ? "current" : "done"}>
        <span />
        <div>
          <strong>Askıya çıkış</strong>
          <small>{formatDate(event.appeal_start_date)}</small>
        </div>
      </li>
      <li className={event.stage === "appeal_ended" ? "done" : ""}>
        <span />
        <div>
          <strong>Askı bitişi</strong>
          <small>{formatDate(event.appeal_end_date)}</small>
        </div>
      </li>
    </ol>
  );
}

export default async function EventDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event) notFound();

  const related = await getEventsByIds(event.linked_event_ids);
  const verified = event.publication_status === "verified_ai";
  const tone = impactTone(event.impact_score);

  return (
    <section className="detail-page">
      <div className="shell">
        <Link className="back-link" href="/degisiklikler">
          ← Değişiklik akışına dön
        </Link>
        <div className="detail-hero">
          <div>
            <div className="detail-badges">
              <span className={`status-pill status-${event.stage}`}>
                <span className="status-dot" />
                {stageLabel(event.stage)}
              </span>
              <span className="source-badge">{event.source_type}</span>
              <span className={`impact impact-${tone}`}>
                Etki {event.impact_score}
              </span>
            </div>
            <p className="detail-location">
              {event.district}
              {event.neighborhood ? ` · ${event.neighborhood}` : ""}
            </p>
            <h1>{event.title}</h1>
            <p className="detail-summary">{event.summary}</p>
            <div className="event-tags">
              {event.categories.map((category) => (
                <span key={category}>{categoryLabel(category)}</span>
              ))}
            </div>
          </div>
          <aside className="source-card">
            <span className="source-card-label">RESMÎ KAYNAK</span>
            <strong>Ankara Büyükşehir Belediyesi</strong>
            <p>
              Bu kayıt kaynak belgeye bağlıdır. Karar vermeden önce belgenin
              tamamını inceleyin.
            </p>
            <a
              className="button button-primary"
              href={event.source_urls.primary}
              target="_blank"
              rel="noreferrer"
            >
              Kaynak belgeyi aç ↗
            </a>
            <span className="source-status">
              ✓ {publicationLabel(event.publication_status)}
            </span>
          </aside>
        </div>

        <div className="detail-layout">
          <div className="detail-main">
            <section className="detail-card">
              <div className="detail-card-heading">
                <div>
                  <span className="section-kicker">YAPILANDIRILMIŞ ANALİZ</span>
                  <h2>Eski ve yeni koşullar</h2>
                </div>
                <span className={verified ? "verified-chip" : "source-chip"}>
                  {verified ? "✓ Kanıt mevcut" : "Kaynak kaydı"}
                </span>
              </div>
              <div className="metrics">
                <MetricRow
                  label="Plan fonksiyonu"
                  metric={event.changes.function}
                  verified={verified}
                />
                <MetricRow
                  label="Emsal (KAKS)"
                  metric={event.changes.emsal}
                  verified={verified}
                />
                <MetricRow label="TAKS" metric={event.changes.taks} verified={verified} />
                <MetricRow
                  label="Yençok"
                  metric={event.changes.yencok}
                  verified={verified}
                />
                <MetricRow
                  label="Nüfus yoğunluğu"
                  metric={event.changes.density}
                  verified={verified}
                />
              </div>
              <div className="ai-notice">
                <span aria-hidden="true">AI</span>
                <p>
                  Yapılandırılmış alanlar otomatik belge analiziyle hazırlanır.
                  Resmî imar belgesi veya yatırım tavsiyesi değildir.
                </p>
              </div>
            </section>

            <section className="detail-card">
              <div className="detail-card-heading">
                <div>
                  <span className="section-kicker">KANIT</span>
                  <h2>Bu bilgi nereden çıktı?</h2>
                </div>
              </div>
              {event.evidence.length ? (
                <div className="evidence-list">
                  {event.evidence.map((item) => (
                    <article key={item.id}>
                      <div className="document-icon" aria-hidden="true">
                        PDF
                      </div>
                      <div>
                        <strong>
                          Plan notu
                          {item.page ? ` · Sayfa ${item.page}` : ""}
                        </strong>
                        <p>{item.excerpt || "Kaynak belge kanıtı"}</p>
                        <a href={item.document_url} target="_blank" rel="noreferrer">
                          Belgede görüntüle ↗
                        </a>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-evidence">
                  <strong>Alan bazında kanıt henüz yayımlanmadı.</strong>
                  <p>
                    Kaynak belge erişilebilir; otomatik extraction yeterli güvene
                    ulaşmadığı için değerler boş bırakıldı.
                  </p>
                </div>
              )}
            </section>

            {related.length ? (
              <section className="related-section">
                <span className="section-kicker">İLİŞKİLİ PLANLAR</span>
                <h2>Aynı olayın diğer ölçekleri</h2>
                <div className="event-grid">
                  {related.map((item) => (
                    <EventCard event={item} key={item.id} compact />
                  ))}
                </div>
              </section>
            ) : null}
          </div>

          <aside className="detail-sidebar">
            <section className="detail-card sidebar-card">
              <h2>Plan bilgileri</h2>
              <dl>
                <div>
                  <dt>İlçe</dt>
                  <dd>{event.district}</dd>
                </div>
                <div>
                  <dt>Mahalle</dt>
                  <dd>{event.neighborhood || "Belirtilmedi"}</dd>
                </div>
                <div>
                  <dt>Ada / parsel</dt>
                  <dd>
                    {event.parcels.length
                      ? event.parcels.join(", ")
                      : "Bölgesel plan"}
                  </dd>
                </div>
                <div>
                  <dt>Plan ölçeği</dt>
                  <dd>{event.plan_scales.join(" + ")}</dd>
                </div>
                <div>
                  <dt>Olay tarihi</dt>
                  <dd>{formatDate(event.event_date)}</dd>
                </div>
              </dl>
            </section>
            <section className="detail-card sidebar-card">
              <h2>Süreç</h2>
              <EventTimeline event={event} />
            </section>
            <section className="sidebar-cta">
              <span>HAFTALIK TAKİP</span>
              <strong>{event.district} değişikliklerini kaçırmayın.</strong>
              <Link href="/bulten">Ücretsiz bültene katıl →</Link>
            </section>
          </aside>
        </div>
      </div>
    </section>
  );
}
