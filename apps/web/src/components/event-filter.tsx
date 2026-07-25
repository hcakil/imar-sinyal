"use client";

import { useMemo, useState } from "react";
import { EventCard } from "./event-card";
import type { ChangeCategory, PlanningEvent } from "@/lib/types";

export function EventFilter({
  events,
  districts,
}: {
  events: PlanningEvent[];
  districts: string[];
}) {
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("");
  const [stage, setStage] = useState("");
  const [category, setCategory] = useState("");
  const [highImpact, setHighImpact] = useState(false);

  const filtered = useMemo(() => {
    const normalizedQuery = query.toLocaleLowerCase("tr-TR").trim();
    return events.filter((event) => {
      if (district && event.district !== district) return false;
      if (stage && event.stage !== stage) return false;
      if (
        category &&
        !event.categories.includes(category as ChangeCategory)
      )
        return false;
      if (highImpact && event.impact_score < 70) return false;
      if (normalizedQuery) {
        const text = [
          event.title,
          event.summary,
          event.district,
          event.neighborhood,
          ...event.parcels,
        ]
          .filter(Boolean)
          .join(" ")
          .toLocaleLowerCase("tr-TR");
        if (!text.includes(normalizedQuery)) return false;
      }
      return true;
    });
  }, [category, district, events, highImpact, query, stage]);

  return (
    <>
      <div className="filter-panel">
        <label className="search-field">
          <span className="sr-only">Ara</span>
          <span aria-hidden="true">⌕</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Mahalle, ada/parsel veya karar ara"
          />
        </label>
        <label>
          <span>İlçe</span>
          <select value={district} onChange={(event) => setDistrict(event.target.value)}>
            <option value="">Tüm ilçeler</option>
            {districts.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Aşama</span>
          <select value={stage} onChange={(event) => setStage(event.target.value)}>
            <option value="">Tüm aşamalar</option>
            <option value="council_approved">Mecliste onaylandı</option>
            <option value="on_appeal">Askıda</option>
            <option value="appeal_ended">Askı süresi bitti</option>
          </select>
        </label>
        <label>
          <span>Değişiklik</span>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">Tüm türler</option>
            <option value="construction_conditions">Yapılaşma koşulu</option>
            <option value="land_use">Fonksiyon</option>
            <option value="plan_note">Plan notu</option>
            <option value="public_infrastructure">Kamu / altyapı</option>
            <option value="procedural">Prosedürel</option>
          </select>
        </label>
        <label className="impact-toggle">
          <input
            type="checkbox"
            checked={highImpact}
            onChange={(event) => setHighImpact(event.target.checked)}
          />
          <span>Yalnızca yüksek etki</span>
        </label>
      </div>
      <div className="results-heading">
        <strong>{filtered.length} değişiklik</strong>
        <span>Resmî kaynak bağlantılarıyla</span>
      </div>
      <div className="event-grid event-grid-feed">
        {filtered.map((event) => (
          <EventCard event={event} key={event.id} />
        ))}
      </div>
      {!filtered.length ? (
        <div className="empty-state">
          <strong>Bu filtrelerle eşleşen kayıt bulunamadı.</strong>
          <p>Filtrelerden birini kaldırarak tekrar deneyin.</p>
        </div>
      ) : null}
    </>
  );
}
