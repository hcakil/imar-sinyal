import Link from "next/link";
import {
  categoryLabel,
  formatDate,
  impactTone,
  primaryChange,
  stageLabel,
} from "@/lib/format";
import type { PlanningEvent } from "@/lib/types";

export function EventCard({
  event,
  compact = false,
}: {
  event: PlanningEvent;
  compact?: boolean;
}) {
  const tone = impactTone(event.impact_score);
  return (
    <article className={`event-card ${compact ? "event-card-compact" : ""}`}>
      <div className="event-card-top">
        <span className={`status-pill status-${event.stage}`}>
          <span className="status-dot" aria-hidden="true" />
          {stageLabel(event.stage)}
        </span>
        <span className={`impact impact-${tone}`}>
          Etki {event.impact_score}
        </span>
      </div>
      <div className="event-location">
        {event.district}
        {event.neighborhood ? ` · ${event.neighborhood}` : ""}
      </div>
      <h3>
        <Link href={`/degisiklik/${event.slug}`}>{event.title}</Link>
      </h3>
      <p className="event-summary">{event.summary}</p>
      <div className="change-callout">{primaryChange(event)}</div>
      <div className="event-tags" aria-label="Değişiklik türleri">
        {event.categories.slice(0, 3).map((category) => (
          <span key={category}>{categoryLabel(category)}</span>
        ))}
      </div>
      <div className="event-meta">
        <span>{event.plan_scales.join(" + ")}</span>
        <span>{formatDate(event.event_date)}</span>
        <span>{event.parcels.length ? event.parcels.join(", ") : "Bölgesel plan"}</span>
      </div>
      <Link className="card-link" href={`/degisiklik/${event.slug}`}>
        Kaynak ve değişikliği incele <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}
