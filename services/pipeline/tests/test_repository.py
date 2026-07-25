from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from imarsinyal.models import ExtractedChange, PlanningEvent, SourceRecord
from imarsinyal.repository import SQLiteRepository


class RepositoryTests(unittest.TestCase):
    def test_same_snapshot_and_event_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteRepository(Path(directory) / "test.db")
            record = SourceRecord(
                source_id="aski:NIP:fixture",
                source_kind="aski",
                source_type="NIP",
                title="Fixture",
                event_date="2026-07-25",
                snapshot_hash="abc123",
            )
            first_changed, _ = repository.save_source_records([record])
            second_changed, second_unchanged = repository.save_source_records([record])
            self.assertEqual(first_changed, {"aski:NIP:fixture"})
            self.assertEqual(second_changed, set())
            self.assertEqual(second_unchanged, {"aski:NIP:fixture"})

            event = PlanningEvent(
                id="event:fixture",
                slug="fixture",
                source_kind="aski",
                source_type="NIP",
                title="Fixture",
                summary="Fixture",
                stage="on_appeal",
                event_date="2026-07-25",
                district="Ankara",
                neighborhood=None,
                parcels=[],
                plan_scales=["1/5000"],
                categories=["procedural"],
                impact_score=0,
                publication_status="source_only",
                source_urls={"primary": "https://example.test"},
                changes=ExtractedChange(),
            )
            self.assertTrue(repository.save_event(event))
            self.assertFalse(repository.save_event(event))
            self.assertEqual(repository.list_events()[0].slug, "fixture")
            version_count = repository.connection.execute(
                "SELECT COUNT(*) AS count FROM planning_event_versions"
            ).fetchone()["count"]
            self.assertEqual(version_count, 1)
            event.impact_score = 10
            self.assertTrue(repository.save_event(event))
            version_count = repository.connection.execute(
                "SELECT COUNT(*) AS count FROM planning_event_versions"
            ).fetchone()["count"]
            self.assertEqual(version_count, 2)


if __name__ == "__main__":
    unittest.main()
