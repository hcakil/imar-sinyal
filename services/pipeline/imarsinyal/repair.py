from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from .models import PlanningEvent
from .normalization import (
    clear_unchanged_metrics,
    district_from_text,
    impact_score,
    normalize_parcels,
)
from .repository import Repository

PLAN_SCALES = {"1/1000", "1/5000", "1/25000", "1/100000"}


def _is_obviously_invalid_parcel(value: str) -> bool:
    normalized = value.replace(" ", "")
    if normalized in PLAN_SCALES:
        return True
    match = re.fullmatch(r"(\d{1,6})/(\d{1,6})", normalized)
    return bool(match and 1900 <= int(match.group(1)) <= 2100)


def repaired_parcels(event: PlanningEvent) -> list[str]:
    """Return a conservative parcel repair proposal for an existing event."""
    source_text = f"{event.title} {event.summary or ''}".strip()
    explicit = normalize_parcels(source_text)
    if explicit:
        return explicit

    title_folded = event.title.casefold()
    title_has_ada_group = bool(
        re.search(r"\bada(?:lar|larda|ların|ları)\b", title_folded)
    )
    if title_has_ada_group and "parsel" not in title_folded:
        # "513, 514 ve 515 adalarda" lists separate blocks, not ada/parsel pairs.
        return []

    return [
        value
        for value in event.parcels
        if not _is_obviously_invalid_parcel(value)
    ]


def repair_event_parcels(
    repository: Repository, *, apply: bool = False
) -> dict[str, Any]:
    checked = 0
    changed = 0
    written = 0
    samples: list[dict[str, Any]] = []

    for event in repository.list_events():
        checked += 1
        before = list(event.parcels)
        after = repaired_parcels(event)
        if before == after:
            continue
        changed += 1
        if len(samples) < 25:
            samples.append(
                {
                    "event_id": event.id,
                    "slug": event.slug,
                    "before": before,
                    "after": after,
                }
            )
        if apply:
            event.parcels = after
            if repository.save_event(event):
                written += 1

    return {
        "mode": "apply" if apply else "dry_run",
        "checked_events": checked,
        "changed_events": changed,
        "written_events": written,
        "samples": samples,
    }


def repaired_district(event: PlanningEvent) -> str:
    if event.district and event.district != "Ankara":
        return event.district
    inferred = district_from_text(f"{event.title} {event.summary or ''}")
    return inferred or event.district or "Ankara"


def repair_event_districts(
    repository: Repository, *, apply: bool = False
) -> dict[str, Any]:
    checked = 0
    changed = 0
    written = 0
    samples: list[dict[str, Any]] = []

    for event in repository.list_events():
        checked += 1
        before = event.district
        after = repaired_district(event)
        if before == after:
            continue
        changed += 1
        if len(samples) < 25:
            samples.append(
                {
                    "event_id": event.id,
                    "slug": event.slug,
                    "before": before,
                    "after": after,
                }
            )
        if apply:
            event.district = after
            if repository.save_event(event):
                written += 1

    return {
        "mode": "apply" if apply else "dry_run",
        "checked_events": checked,
        "changed_events": changed,
        "written_events": written,
        "samples": samples,
    }


def repair_equal_metrics(
    repository: Repository, *, apply: bool = False
) -> dict[str, Any]:
    checked = 0
    changed = 0
    written = 0
    samples: list[dict[str, Any]] = []

    for event in repository.list_events():
        checked += 1
        before_changes = asdict(event.changes)
        before_score = event.impact_score
        before_status = event.publication_status
        clear_unchanged_metrics(event.changes)
        event.impact_score = impact_score(event.changes)
        has_verified_value = any(
            metric.old_value is not None or metric.new_value is not None
            for metric in (
                event.changes.function,
                event.changes.emsal,
                event.changes.taks,
                event.changes.yencok,
                event.changes.density,
            )
        )
        if event.publication_status != "withheld":
            event.publication_status = (
                "verified_ai" if has_verified_value else "source_only"
            )

        after_changes = asdict(event.changes)
        if (
            before_changes == after_changes
            and before_score == event.impact_score
            and before_status == event.publication_status
        ):
            continue
        changed += 1
        if len(samples) < 25:
            samples.append(
                {
                    "event_id": event.id,
                    "slug": event.slug,
                    "before_score": before_score,
                    "after_score": event.impact_score,
                    "before_status": before_status,
                    "after_status": event.publication_status,
                }
            )
        if apply and repository.save_event(event):
            written += 1

    return {
        "mode": "apply" if apply else "dry_run",
        "checked_events": checked,
        "changed_events": changed,
        "written_events": written,
        "samples": samples,
    }
