import type {
  ChangeCategory,
  EventStage,
  PlanningEvent,
  PublicationStatus,
} from "@/lib/types";

const APP_ROOT = "https://planaski.ankara.bel.tr/planaski";

interface SeedInput {
  id: string;
  sourceType: "UIP" | "NIP" | "NIP25";
  slug: string;
  title: string;
  summary: string;
  district: string;
  neighborhood?: string;
  parcels: string[];
  scale: string;
  start: string;
  end: string;
  score: number;
  categories: ChangeCategory[];
  status?: PublicationStatus;
  newFunction?: string;
  newEmsal?: string | number;
  newTaks?: string | number;
  newDensity?: string | number;
  evidencePage?: number;
  linked?: string[];
}

function documentUrl(sourceType: string, id: string, file: string): string {
  return `${APP_ROOT}/_files/askiplanlari/${sourceType}/${encodeURIComponent(`{${id}}`)}/${file}`;
}

function currentStage(end: string): EventStage {
  return end >= "2026-07-25" ? "on_appeal" : "appeal_ended";
}

function seed(input: SeedInput): PlanningEvent {
  const planNote = documentUrl(input.sourceType, input.id, "plannotu.pdf");
  const evidenceId = input.evidencePage ? `${input.id}-p${input.evidencePage}` : null;
  const evidenceIds = evidenceId ? [evidenceId] : [];
  const now = "2026-07-25T09:00:00+03:00";
  return {
    id: `{${input.id}}`,
    slug: input.slug,
    source_kind: "aski",
    source_type: input.sourceType,
    title: input.title,
    summary: input.summary,
    stage: currentStage(input.end),
    event_date: input.start,
    appeal_start_date: input.start,
    appeal_end_date: input.end,
    district: input.district,
    neighborhood: input.neighborhood ?? null,
    parcels: input.parcels,
    plan_scales: [input.scale],
    categories: input.categories,
    impact_score: input.score,
    publication_status: input.status ?? "source_only",
    source_urls: {
      primary: planNote,
      plan_note: planNote,
      council_decision: documentUrl(input.sourceType, input.id, "mecliskarari.pdf"),
      plan_sheet: documentUrl(input.sourceType, input.id, "planpafta.pdf"),
    },
    document_hash: null,
    geometry: null,
    changes: {
      function: {
        old_value: null,
        new_value: input.newFunction ?? null,
        unit: null,
        evidence_ids: input.newFunction ? evidenceIds : [],
      },
      emsal: {
        old_value: null,
        new_value: input.newEmsal ?? null,
        unit: null,
        evidence_ids: input.newEmsal ? evidenceIds : [],
      },
      taks: {
        old_value: null,
        new_value: input.newTaks ?? null,
        unit: null,
        evidence_ids: input.newTaks ? evidenceIds : [],
      },
      yencok: {
        old_value: null,
        new_value: null,
        unit: null,
        evidence_ids: [],
      },
      density: {
        old_value: null,
        new_value: input.newDensity ?? null,
        unit: input.newDensity ? "kişi/ha" : null,
        evidence_ids: input.newDensity ? evidenceIds : [],
      },
    },
    evidence: evidenceId
      ? [
          {
            id: evidenceId,
            document_url: planNote,
            page: input.evidencePage,
            paragraph: null,
            excerpt: "Yapılaşma koşulu ilgili plan notu sayfasından çıkarılmıştır.",
            image_url: null,
            field_names: [
              ...(input.newFunction ? ["function.new_value"] : []),
              ...(input.newEmsal ? ["emsal.new_value"] : []),
              ...(input.newTaks ? ["taks.new_value"] : []),
              ...(input.newDensity ? ["density.new_value"] : []),
            ],
          },
        ]
      : [],
    linked_event_ids: input.linked ?? [],
    link_confidence: input.linked?.length ? 0.98 : null,
    created_at: now,
    updated_at: now,
  };
}

export const seedEvents: PlanningEvent[] = [
  seed({
    id: "B6E5ADA7-EE09-40E8-9B22-9176387034DB",
    sourceType: "NIP",
    slug: "beypazari-ayvasik-404-ada-1-parsel",
    title: "Beypazarı Ayvaşık 404 ada 1 parsel nazım imar planı",
    summary:
      "404 ada 1 parsel için ticaret alanı ve düğün salonu kullanımına ilişkin plan koşulları askıya çıkarıldı.",
    district: "Beypazarı",
    neighborhood: "Ayvaşık",
    parcels: ["404/1"],
    scale: "1/5000",
    start: "2026-07-14",
    end: "2026-08-12",
    score: 58,
    categories: ["land_use"],
    status: "verified_ai",
    newFunction: "Ticaret Alanı (Düğün Salonu)",
    evidencePage: 1,
  }),
  seed({
    id: "71251D75-81C4-4EE2-B1E6-6B8439A9CEA5",
    sourceType: "NIP",
    slug: "yenimahalle-yuva-166-ada-36-parsel",
    title: "Yenimahalle Yuva Mahallesi 166 ada 36 parsel",
    summary:
      "Alan orta yoğunluklu gelişme konut alanı ve sosyal donatı kullanımlarıyla düzenlendi.",
    district: "Yenimahalle",
    neighborhood: "Yuva",
    parcels: ["166/36"],
    scale: "1/5000",
    start: "2026-07-13",
    end: "2026-08-11",
    score: 72,
    categories: ["land_use", "construction_conditions"],
    status: "verified_ai",
    newFunction: "Orta Yoğunlukta Gelişme Konut Alanı",
    newDensity: "121–250",
    evidencePage: 1,
  }),
  seed({
    id: "B245194C-772F-44C6-BFDB-F0F03847605C",
    sourceType: "NIP",
    slug: "sincan-temelli-malikoy-227-262-adalar",
    title: "Sincan Temelli / Malıköy 227–262 adalar",
    summary:
      "Geniş planlama alanında konut ve sosyal donatı kararları alt ölçekli planlara yön verecek şekilde düzenlendi.",
    district: "Sincan",
    neighborhood: "Malıköy",
    parcels: ["227–262 adalar"],
    scale: "1/5000",
    start: "2026-07-13",
    end: "2026-08-11",
    score: 61,
    categories: ["plan_note", "land_use"],
  }),
  seed({
    id: "CE77B50C-D4A8-43B1-8B06-C9D622162854",
    sourceType: "UIP",
    slug: "yeni-mamak-kdgpa-plan-notu-revizyonu",
    title: "Yeni Mamak KDGPA plan notu ilavesi ve revizyonu",
    summary:
      "Kentsel dönüşüm alanının 2–8. etaplarında konut, ticaret ve donatı yapılaşma koşulları güncellendi.",
    district: "Mamak",
    parcels: [],
    scale: "1/1000",
    start: "2026-07-03",
    end: "2026-08-03",
    score: 86,
    categories: ["plan_note", "construction_conditions", "land_use"],
    status: "verified_ai",
    newFunction: "Konut ve Ticaret",
    newEmsal: "2.00–2.50",
    evidencePage: 6,
  }),
  seed({
    id: "F1EDFC28-A89A-4B36-A491-C67FAE86C909",
    sourceType: "NIP",
    slug: "haymana-karahoca-103-ada-85-parsel",
    title: "Haymana Karahoca 103 ada 85 parsel",
    summary:
      "Parsel kamu hizmet alanı ve ceza infaz kurumu kullanımıyla düzenlendi.",
    district: "Haymana",
    neighborhood: "Karahoca",
    parcels: ["103/85"],
    scale: "1/5000",
    start: "2026-07-03",
    end: "2026-08-03",
    score: 19,
    categories: ["public_infrastructure", "land_use"],
    status: "verified_ai",
    newFunction: "Kamu Hizmet Alanı (Ceza İnfaz Kurumu)",
    evidencePage: 1,
  }),
  seed({
    id: "96742291-CA36-4E38-AB37-2E592AAC73F7",
    sourceType: "NIP",
    slug: "polatli-basri-108-109-adalar",
    title: "Polatlı Basri 108 ada 1 ve 109 ada 1 parseller",
    summary:
      "Plan notundaki belediye meclisi karar tarihi ve numarası güncellendi.",
    district: "Polatlı",
    neighborhood: "Basri",
    parcels: ["108/1", "109/1"],
    scale: "1/5000",
    start: "2026-06-29",
    end: "2026-07-28",
    score: 16,
    categories: ["procedural"],
  }),
  seed({
    id: "8BDA90D1-21DE-4BBB-B30B-616635A8855D",
    sourceType: "UIP",
    slug: "cankaya-korkutreis-1154-ada-25-parsel",
    title: "Çankaya Korkutreis 1154 ada 25 parsel",
    summary:
      "Zemin katta ticaret kullanımı ve toplam inşaat alanının TAKS üzerinden hesaplanmasına ilişkin plan notu askıya çıktı.",
    district: "Çankaya",
    neighborhood: "Korkutreis",
    parcels: ["1154/25"],
    scale: "1/1000",
    start: "2026-06-24",
    end: "2026-07-23",
    score: 78,
    categories: ["construction_conditions", "land_use", "plan_note"],
    status: "verified_ai",
    newFunction: "Konut + Ticaret",
    newTaks: "0.60",
    evidencePage: 1,
  }),
  seed({
    id: "2F2EC949-BF11-4E2D-A78B-2EA5FC29D009",
    sourceType: "UIP",
    slug: "cankaya-beytepe-28517-ada-2-uip",
    title: "Çankaya Beytepe 28517 ada 2 parsel uygulama planı",
    summary:
      "Parsel sosyal tesis alanı olarak düzenlendi; yapılaşma koşulu E=1.00 olarak belirtildi.",
    district: "Çankaya",
    neighborhood: "Beytepe",
    parcels: ["28517/2"],
    scale: "1/1000",
    start: "2026-06-24",
    end: "2026-07-23",
    score: 69,
    categories: ["land_use", "construction_conditions"],
    status: "verified_ai",
    newFunction: "Sosyal Tesis Alanı",
    newEmsal: "1.00",
    evidencePage: 1,
    linked: ["{53C330C4-8F54-43C3-A04A-7112BF996286}"],
  }),
  seed({
    id: "53C330C4-8F54-43C3-A04A-7112BF996286",
    sourceType: "NIP",
    slug: "cankaya-beytepe-28517-ada-2-nip",
    title: "Çankaya Beytepe 28517 ada 2 parsel nazım planı",
    summary:
      "Aynı parselin üst ölçekli planında sosyal tesis alanı kullanım kararı askıya çıkarıldı.",
    district: "Çankaya",
    neighborhood: "Beytepe",
    parcels: ["28517/2"],
    scale: "1/5000",
    start: "2026-06-24",
    end: "2026-07-23",
    score: 65,
    categories: ["land_use"],
    status: "verified_ai",
    newFunction: "Sosyal Tesis Alanı",
    evidencePage: 1,
    linked: ["{2F2EC949-BF11-4E2D-A78B-2EA5FC29D009}"],
  }),
  seed({
    id: "CDC99CFB-1CA1-42C4-B337-53A2EB26EC40",
    sourceType: "NIP25",
    slug: "cankaya-alacaatli-60912-ada-1-nip25",
    title: "Çankaya Alacaatlı 60912 ada 1 parsel 1/25000 planı",
    summary:
      "Düşük yoğunluklu konut, belediye hizmet ve rekreasyon alanı kararları üst ölçekli planda düzenlendi.",
    district: "Çankaya",
    neighborhood: "Alacaatlı",
    parcels: ["60912/1"],
    scale: "1/25000",
    start: "2026-06-23",
    end: "2026-07-22",
    score: 54,
    categories: ["land_use"],
  }),
  seed({
    id: "1C96952B-51B6-4E21-8AF5-B865D9CF3B38",
    sourceType: "NIP",
    slug: "cankaya-alacaatli-60912-ada-1-nip",
    title: "Çankaya Alacaatlı 60912 ada 1 parsel nazım planı",
    summary:
      "Düşük yoğunluklu konut ve sosyal donatı kullanımları için nazım plan koşulları askıya çıkarıldı.",
    district: "Çankaya",
    neighborhood: "Alacaatlı",
    parcels: ["60912/1"],
    scale: "1/5000",
    start: "2026-06-23",
    end: "2026-07-22",
    score: 57,
    categories: ["land_use", "construction_conditions"],
    status: "verified_ai",
    newFunction: "Düşük Yoğunluklu Gelişme Konut Alanı ve Sosyal Donatı",
    newDensity: "51–120",
    evidencePage: 1,
  }),
];
