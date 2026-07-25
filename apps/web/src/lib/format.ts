import type {
  ChangeCategory,
  EventStage,
  PlanningEvent,
  PublicationStatus,
} from "./types";

const stageLabels: Record<EventStage, string> = {
  council_approved: "Mecliste onaylandı",
  on_appeal: "Askıda",
  appeal_ended: "Askı süresi bitti",
  expired: "Süresi doldu",
  withdrawn: "Kaynaktan kaldırıldı",
};

const categoryLabels: Record<ChangeCategory, string> = {
  construction_conditions: "Yapılaşma koşulu",
  land_use: "Fonksiyon değişikliği",
  plan_note: "Plan notu",
  public_infrastructure: "Kamu / altyapı",
  transportation: "Ulaşım",
  procedural: "Prosedürel",
};

const publicationLabels: Record<PublicationStatus, string> = {
  source_only: "Kaynak kaydı",
  verified_ai: "Kanıtlı AI analizi",
  withheld: "Yayına kapalı",
};

export function formatDate(value?: string | null): string {
  if (!value) return "Belirtilmedi";
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Istanbul",
  }).format(new Date(`${value}T12:00:00+03:00`));
}

export function stageLabel(stage: EventStage): string {
  return stageLabels[stage];
}

export function categoryLabel(category: ChangeCategory): string {
  return categoryLabels[category];
}

export function publicationLabel(status: PublicationStatus): string {
  return publicationLabels[status];
}

export function primaryChange(event: PlanningEvent): string {
  const entries = [
    ["Emsal", event.changes.emsal],
    ["TAKS", event.changes.taks],
    ["Yençok", event.changes.yencok],
    ["Yoğunluk", event.changes.density],
    ["Fonksiyon", event.changes.function],
  ] as const;

  for (const [label, metric] of entries) {
    if (metric.new_value !== null) {
      const prefix =
        metric.old_value !== null ? `${metric.old_value} → ` : "";
      const unit = metric.unit ? ` ${metric.unit}` : "";
      return `${label}: ${prefix}${metric.new_value}${unit}`;
    }
  }
  return "Yapısal değişiklik belgede otomatik doğrulanamadı";
}

export function impactTone(score: number): "high" | "medium" | "low" {
  if (score >= 70) return "high";
  if (score >= 45) return "medium";
  return "low";
}
