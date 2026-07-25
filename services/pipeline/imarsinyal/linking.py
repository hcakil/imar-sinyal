from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .models import PlanningEvent


@dataclass(frozen=True)
class LinkCandidate:
    left_id: str
    right_id: str
    confidence: float
    reasons: tuple[str, ...]


def _date_distance(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    try:
        return abs((date.fromisoformat(left) - date.fromisoformat(right)).days)
    except ValueError:
        return None


def score_event_pair(left: PlanningEvent, right: PlanningEvent) -> LinkCandidate | None:
    if left.source_type == right.source_type:
        return None
    if left.source_kind == right.source_kind == "council":
        return None
    if not left.district or left.district != right.district:
        return None

    score = 0.25
    reasons: list[str] = ["ilçe eşleşmesi"]

    parcel_overlap = set(left.parcels) & set(right.parcels)
    if parcel_overlap:
        score += 0.45
        reasons.append(f"{len(parcel_overlap)} ada/parsel eşleşmesi")
    elif left.parcels and right.parcels:
        return None

    scale_overlap = set(left.plan_scales) & set(right.plan_scales)
    if scale_overlap:
        score += 0.15
        reasons.append("plan ölçeği eşleşmesi")

    left_date = left.event_date or left.appeal_start_date
    right_date = right.event_date or right.appeal_start_date
    distance = _date_distance(left_date, right_date)
    if distance is not None:
        if distance <= 45:
            score += 0.15
            reasons.append(f"tarih yakınlığı ({distance} gün)")
        elif distance <= 120:
            score += 0.05
            reasons.append(f"zayıf tarih yakınlığı ({distance} gün)")
        else:
            score -= 0.15

    if left.neighborhood and left.neighborhood == right.neighborhood:
        score += 0.05
        reasons.append("mahalle eşleşmesi")

    return LinkCandidate(
        left_id=left.id,
        right_id=right.id,
        confidence=min(round(score, 2), 1.0),
        reasons=tuple(reasons),
    )


def find_links(
    events: Iterable[PlanningEvent], minimum_confidence: float = 0.75
) -> list[LinkCandidate]:
    event_list = list(events)
    links: list[LinkCandidate] = []
    for index, left in enumerate(event_list):
        for right in event_list[index + 1 :]:
            candidate = score_event_pair(left, right)
            if candidate and candidate.confidence >= minimum_confidence:
                links.append(candidate)
    return links
