from __future__ import annotations

import unittest
from datetime import UTC, datetime

from imarsinyal.models import ExtractedChange, PlanningEvent
from imarsinyal.newsletter import select_weekly_events
from imarsinyal.repository import Repository


class MemoryRepository(Repository):
    def __init__(self, events: list[PlanningEvent]) -> None:
        self.events = events

    def save_source_records(self, records):
        raise NotImplementedError

    def save_event(self, event):
        raise NotImplementedError

    def list_events(self, published_only: bool = False):
        if not published_only:
            return self.events
        return [
            event
            for event in self.events
            if event.publication_status != "withheld"
        ]

    def record_run(self, run):
        raise NotImplementedError

    def mark_unseen_aski(self, seen_external_ids):
        raise NotImplementedError


def event(
    event_id: str,
    *,
    event_date: str,
    source_updated_at: str | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
    publication_status: str = "source_only",
) -> PlanningEvent:
    return PlanningEvent(
        id=event_id,
        slug=event_id,
        source_kind="aski",
        source_type="NIP",
        title=event_id,
        summary=event_id,
        stage="on_appeal",
        event_date=event_date,
        district="Ankara",
        neighborhood=None,
        parcels=[],
        plan_scales=["1/5000"],
        categories=["procedural"],
        impact_score=10,
        publication_status=publication_status,
        source_urls={"primary": "https://example.test"},
        changes=ExtractedChange(),
        source_updated_at=source_updated_at,
        created_at=created_at,
        updated_at=updated_at,
    )


class NewsletterSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 7, 27, 5, 30, tzinfo=UTC)

    def test_includes_officially_recent_and_recently_changed_events(self) -> None:
        repository = MemoryRepository(
            [
                event("official", event_date="2026-07-27"),
                event(
                    "changed",
                    event_date="2026-01-10",
                    source_updated_at="2026-07-26T08:00:00+00:00",
                ),
                event("old", event_date="2026-01-09"),
            ]
        )

        selection = select_weekly_events(repository, now=self.now)

        self.assertEqual(
            {item.id for item in selection.events},
            {"official", "changed"},
        )
        self.assertEqual(selection.official_date_count, 1)
        self.assertEqual(selection.source_activity_count, 1)

    def test_event_matching_both_rules_is_not_duplicated(self) -> None:
        repository = MemoryRepository(
            [
                event(
                    "both",
                    event_date="2026-07-27",
                    source_updated_at="2026-07-27T00:16:00Z",
                )
            ]
        )

        selection = select_weekly_events(repository, now=self.now)

        self.assertEqual([item.id for item in selection.events], ["both"])
        self.assertEqual(selection.official_date_count, 1)
        self.assertEqual(selection.source_activity_count, 1)

    def test_legacy_timestamps_do_not_create_false_source_activity(self) -> None:
        repository = MemoryRepository(
            [
                event(
                    "legacy",
                    event_date="2026-01-10",
                    created_at="2026-07-27T00:16:00+00:00",
                    updated_at="2026-07-27T00:16:01+00:00",
                ),
            ]
        )

        selection = select_weekly_events(repository, now=self.now)

        self.assertEqual(selection.events, [])
        self.assertEqual(selection.source_activity_count, 0)

    def test_withheld_event_is_never_selected(self) -> None:
        repository = MemoryRepository(
            [
                event(
                    "withheld",
                    event_date="2026-07-27",
                    source_updated_at="2026-07-27T00:16:00Z",
                    publication_status="withheld",
                )
            ]
        )

        selection = select_weekly_events(repository, now=self.now)

        self.assertEqual(selection.events, [])


if __name__ == "__main__":
    unittest.main()
