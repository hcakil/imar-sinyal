from __future__ import annotations

import unittest

from imarsinyal.linking import score_event_pair
from imarsinyal.models import ExtractedChange, PlanningEvent


def event(identifier: str, source_kind: str, source_type: str, scale: str):
    return PlanningEvent(
        id=identifier,
        slug=identifier,
        source_kind=source_kind,  # type: ignore[arg-type]
        source_type=source_type,
        title="Çankaya Beytepe 28517 ada 2 parsel plan değişikliği",
        summary="Kaynak özeti",
        stage="on_appeal" if source_kind == "aski" else "council_approved",
        event_date="2026-06-24",
        district="Çankaya",
        neighborhood="Beytepe",
        parcels=["28517/2"],
        plan_scales=[scale],
        categories=["land_use"],
        impact_score=35,
        publication_status="source_only",
        source_urls={"primary": "https://example.test/source"},
        changes=ExtractedChange(),
    )


class LinkingTests(unittest.TestCase):
    def test_council_and_aski_link_with_parcel_and_date(self) -> None:
        candidate = score_event_pair(
            event("council", "council", "ABB_COUNCIL", "1/5000"),
            event("aski", "aski", "NIP", "1/5000"),
        )
        self.assertIsNotNone(candidate)
        self.assertGreaterEqual(candidate.confidence, 0.9)  # type: ignore[union-attr]

    def test_beytepe_uip_nip_stay_separate_but_are_linked(self) -> None:
        candidate = score_event_pair(
            event("uip", "aski", "UIP", "1/1000"),
            event("nip", "aski", "NIP", "1/5000"),
        )
        self.assertIsNotNone(candidate)
        self.assertGreaterEqual(candidate.confidence, 0.75)  # type: ignore[union-attr]
        self.assertNotEqual(candidate.left_id, candidate.right_id)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
