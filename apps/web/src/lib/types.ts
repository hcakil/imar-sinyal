export type EventStage =
  | "council_approved"
  | "on_appeal"
  | "appeal_ended"
  | "expired"
  | "withdrawn";

export type PublicationStatus = "source_only" | "verified_ai" | "withheld";

export type ChangeCategory =
  | "construction_conditions"
  | "land_use"
  | "plan_note"
  | "public_infrastructure"
  | "transportation"
  | "procedural";

export interface MetricChange {
  old_value: string | number | null;
  new_value: string | number | null;
  unit?: string | null;
  evidence_ids: string[];
}

export interface Evidence {
  id: string;
  document_url: string;
  page?: number | null;
  paragraph?: number | null;
  excerpt?: string | null;
  image_url?: string | null;
  field_names: string[];
}

export interface PlanningEvent {
  id: string;
  slug: string;
  source_kind: "aski" | "council";
  source_type: string;
  title: string;
  summary: string;
  stage: EventStage;
  event_date: string;
  appeal_start_date?: string | null;
  appeal_end_date?: string | null;
  district: string;
  neighborhood?: string | null;
  parcels: string[];
  plan_scales: string[];
  categories: ChangeCategory[];
  impact_score: number;
  publication_status: PublicationStatus;
  source_urls: {
    primary: string;
    plan_note?: string | null;
    council_decision?: string | null;
    plan_sheet?: string | null;
  };
  document_hash?: string | null;
  geometry?: {
    centroid?: [number, number] | null;
    bbox?: [number, number, number, number] | null;
  } | null;
  changes: {
    function: MetricChange;
    emsal: MetricChange;
    taks: MetricChange;
    yencok: MetricChange;
    density: MetricChange;
  };
  evidence: Evidence[];
  linked_event_ids: string[];
  link_confidence?: number | null;
  source_updated_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EventFilters {
  district?: string;
  stage?: EventStage | "";
  category?: ChangeCategory | "";
  query?: string;
  minImpact?: number;
  fromDate?: string;
  toDate?: string;
}
