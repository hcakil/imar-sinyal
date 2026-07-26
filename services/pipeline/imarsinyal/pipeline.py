from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from .extraction import (
    extract_pdf_record,
    extract_text_record,
    numbered_paragraph_text,
)
from .linking import find_links
from .models import ExtractedChange, PlanningEvent, SourceRecord
from .normalization import (
    clear_unchanged_metrics,
    empty_change_from_record,
    impact_score,
    slugify,
    source_stage,
)
from .repository import Repository, create_repository
from .sources.aski import fetch_aski_records
from .sources.council import (
    download_document,
    extract_docx_text,
    fetch_council_records,
)
from .sources.municipal import fetch_municipal_aski_records

logger = logging.getLogger(__name__)
COUNCIL_AI_TERMS = (
    "plan değişik",
    "plan not",
    "nazım imar",
    "uygulama imar",
    "emsal",
    "kaks",
    "taks",
    "yençok",
    "yoğunluk",
    "fonksiyon değişik",
)


def _clear_unproven_values(change: ExtractedChange) -> ExtractedChange:
    evidence_ids = {item.id for item in change.evidence}
    for metric in (
        change.function,
        change.emsal,
        change.taks,
        change.yencok,
        change.density,
    ):
        has_value = metric.old_value is not None or metric.new_value is not None
        has_valid_evidence = bool(metric.evidence_ids) and set(
            metric.evidence_ids
        ).issubset(evidence_ids)
        if has_value and not has_valid_evidence:
            metric.old_value = None
            metric.new_value = None
            metric.unit = None
            metric.evidence_ids = []
    return clear_unchanged_metrics(change)


def _has_verified_value(change: ExtractedChange) -> bool:
    return any(
        metric.old_value is not None or metric.new_value is not None
        for metric in (
            change.function,
            change.emsal,
            change.taks,
            change.yencok,
            change.density,
        )
    )


def extract_record(record: SourceRecord, workdir: Path) -> ExtractedChange:
    if not os.getenv("GEMINI_API_KEY"):
        return empty_change_from_record(record)
    if record.source_kind == "council" and not any(
        term in record.title.casefold() for term in COUNCIL_AI_TERMS
    ):
        return empty_change_from_record(record)
    document = record.documents.get("primary")
    preferred_document = record.documents.get("plan_note") or document
    if (
        preferred_document
        and (preferred_document.media_type or "").startswith("text/")
        and record.raw.get("summary")
    ):
        return extract_text_record(
            record,
            numbered_paragraph_text(
                [
                    {
                        "paragraph": index,
                        "text": paragraph,
                    }
                    for index, paragraph in enumerate(
                        re.split(
                            r"(?<=[.!?])\s+",
                            str(record.raw["summary"]),
                        ),
                        start=1,
                    )
                    if paragraph
                ]
            ),
        )
    if (
        record.source_kind == "council"
        and document
        and (document.media_type or "").endswith(
            "officedocument.wordprocessingml.document"
        )
    ):
        content = download_document(document)
        text, evidence = extract_docx_text(content)
        return extract_text_record(
            record, numbered_paragraph_text(evidence)
        )
    return extract_pdf_record(record, workdir=workdir)


def event_from_record(
    record: SourceRecord, change: ExtractedChange
) -> PlanningEvent:
    change = _clear_unproven_values(change)
    verified = _has_verified_value(change)
    district = record.district or "Ankara"
    title = record.title.strip()
    short_id = (record.snapshot_hash or record.source_id)[-8:].lower()
    slug = slugify(
        f"{district} {record.neighborhood or ''} {title} {record.event_date}"
    )
    slug = f"{slug[:100]}-{short_id}"
    source_urls = {name: value.url for name, value in record.documents.items()}
    primary_document = (
        record.documents.get("plan_note")
        or record.documents.get("primary")
        or next(iter(record.documents.values()), None)
    )
    source_urls["primary"] = primary_document.url if primary_document else ""
    return PlanningEvent(
        id=f"event:{record.source_id}",
        slug=slug,
        source_kind=record.source_kind,
        source_type=record.source_type,
        title=title,
        summary=change.summary or title,
        stage=source_stage(record),  # type: ignore[arg-type]
        event_date=record.event_date,
        district=district,
        neighborhood=record.neighborhood,
        parcels=record.parcels,
        plan_scales=record.plan_scales,
        categories=change.categories,
        impact_score=impact_score(change),
        publication_status="verified_ai" if verified else "source_only",
        source_urls=source_urls,
        changes=change,
        appeal_start_date=record.appeal_start_date,
        appeal_end_date=record.appeal_end_date,
        document_hash=primary_document.sha256 if primary_document else None,
        geometry=record.geometry,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
    )


def _apply_links(repository: Repository) -> int:
    events = repository.list_events()
    by_id = {event.id: event for event in events}
    changed = 0
    for candidate in find_links(events):
        left = by_id[candidate.left_id]
        right = by_id[candidate.right_id]
        if right.id not in left.linked_event_ids:
            left.linked_event_ids.append(right.id)
            left.link_confidence = max(left.link_confidence or 0, candidate.confidence)
            changed += int(repository.save_event(left))
        if left.id not in right.linked_event_ids:
            right.linked_event_ids.append(left.id)
            right.link_confidence = max(right.link_confidence or 0, candidate.confidence)
            changed += int(repository.save_event(right))
    return changed


def run_pipeline(
    *,
    repository: Repository | None = None,
    council_from: date = date(2026, 1, 1),
    include_council: bool = True,
    force: bool = False,
) -> dict[str, object]:
    repo = repository or create_repository()
    started_at = datetime.now(UTC)
    run_id = f"run-{started_at.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    records: list[SourceRecord] = []
    errors: list[str] = []

    ask_records, ask_errors = fetch_aski_records()
    municipal_records, municipal_errors = fetch_municipal_aski_records()
    ask_records.extend(municipal_records)
    ask_errors.extend(municipal_errors)
    records.extend(ask_records)
    errors.extend(ask_errors)
    if include_council:
        council_records, council_errors = fetch_council_records(
            from_date=council_from
        )
        records.extend(council_records)
        errors.extend(council_errors)

    changed_ids, unchanged_ids = repo.save_source_records(records)
    candidates = records if force else [
        record for record in records if record.source_id in changed_ids
    ]
    saved = failed = 0
    with tempfile.TemporaryDirectory(prefix="imarsinyal-") as directory:
        workdir = Path(directory)
        for record in candidates:
            try:
                change = extract_record(record, workdir)
                saved += int(repo.save_event(event_from_record(record, change)))
            except Exception as exc:
                failed += 1
                errors.append(f"{record.source_id}: {exc}")
                logger.exception("Record processing failed: %s", record.source_id)
                source_only = empty_change_from_record(record)
                repo.save_event(event_from_record(record, source_only))

    # A partial layer outage must never mark its records as removed.
    removed = 0
    if not ask_errors:
        removed = repo.mark_unseen_aski(
            {record.source_id for record in ask_records}
        )
    linked_updates = _apply_links(repo)
    finished_at = datetime.now(UTC)
    run: dict[str, object] = {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "success" if failed == 0 and not errors else "partial",
        "source_records": len(records),
        "active_aski_records": len(ask_records),
        "changed_snapshots": len(changed_ids),
        "unchanged_snapshots": len(unchanged_ids),
        "saved_events": saved,
        "failed_records": failed,
        "removed_aski_records": removed,
        "linked_event_updates": linked_updates,
        "errors": errors,
    }
    repo.record_run(run)
    return run
