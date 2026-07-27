from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

EventStage = Literal[
    "council_approved", "on_appeal", "appeal_ended", "expired", "withdrawn"
]
PublicationStatus = Literal["source_only", "verified_ai", "withheld"]


@dataclass
class SourceDocument:
    url: str
    media_type: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    local_path: str | None = None


@dataclass
class SourceRecord:
    source_id: str
    source_kind: Literal["aski", "council"]
    source_type: str
    title: str
    event_date: str
    district: str | None = None
    neighborhood: str | None = None
    parcels: list[str] = field(default_factory=list)
    plan_scales: list[str] = field(default_factory=list)
    appeal_start_date: str | None = None
    appeal_end_date: str | None = None
    decision_number: str | None = None
    documents: dict[str, SourceDocument] = field(default_factory=dict)
    geometry: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    snapshot_hash: str | None = None

    @property
    def external_id(self) -> str:
        return self.source_id

    @property
    def content_hash(self) -> str:
        return self.snapshot_hash or ""

    @property
    def found_at(self) -> str:
        return datetime.now(UTC).isoformat()

    @property
    def snapshot_id(self) -> str:
        suffix = (self.snapshot_hash or "unhashed")[:16]
        safe_source_id = self.source_id.replace(":", "__").replace("/", "_")
        return f"{safe_source_id}__{suffix}"


@dataclass
class Evidence:
    id: str
    document_url: str
    field_names: list[str]
    page: int | None = None
    paragraph: int | None = None
    excerpt: str | None = None
    image_url: str | None = None


@dataclass
class MetricChange:
    old_value: str | float | int | None = None
    new_value: str | float | int | None = None
    unit: str | None = None
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class ExtractedChange:
    function: MetricChange = field(default_factory=MetricChange)
    emsal: MetricChange = field(default_factory=MetricChange)
    taks: MetricChange = field(default_factory=MetricChange)
    yencok: MetricChange = field(default_factory=MetricChange)
    density: MetricChange = field(default_factory=MetricChange)
    categories: list[str] = field(default_factory=list)
    summary: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    model: str | None = None
    parse_error: str | None = None


@dataclass
class PlanningEvent:
    id: str
    slug: str
    source_kind: Literal["aski", "council"]
    source_type: str
    title: str
    summary: str
    stage: EventStage
    event_date: str
    district: str
    neighborhood: str | None
    parcels: list[str]
    plan_scales: list[str]
    categories: list[str]
    impact_score: int
    publication_status: PublicationStatus
    source_urls: dict[str, str | None]
    changes: ExtractedChange
    appeal_start_date: str | None = None
    appeal_end_date: str | None = None
    document_hash: str | None = None
    geometry: dict[str, Any] | None = None
    linked_event_ids: list[str] = field(default_factory=list)
    link_confidence: float | None = None
    source_updated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        extracted = data.pop("changes")
        data["changes"] = {
            key: extracted[key]
            for key in ("function", "emsal", "taks", "yencok", "density")
        }
        data["evidence"] = extracted["evidence"]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanningEvent":
        raw = dict(data)
        raw.pop("content_hash", None)
        evidence_payload = raw.pop("evidence", None)
        raw_changes = dict(raw.get("changes") or {})
        if evidence_payload is not None:
            raw_changes["evidence"] = evidence_payload

        def metric(name: str) -> MetricChange:
            value = raw_changes.get(name)
            return value if isinstance(value, MetricChange) else MetricChange(**(value or {}))

        evidence = [
            item if isinstance(item, Evidence) else Evidence(**item)
            for item in raw_changes.get("evidence") or []
        ]
        raw["changes"] = ExtractedChange(
            function=metric("function"),
            emsal=metric("emsal"),
            taks=metric("taks"),
            yencok=metric("yencok"),
            density=metric("density"),
            categories=list(raw_changes.get("categories") or raw.get("categories") or []),
            summary=raw_changes.get("summary") or raw.get("summary"),
            evidence=evidence,
            model=raw_changes.get("model"),
            parse_error=raw_changes.get("parse_error"),
        )
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in raw.items() if key in allowed})
