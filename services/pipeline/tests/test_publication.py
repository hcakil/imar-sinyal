from __future__ import annotations

import json
import unittest
from pathlib import Path

from imarsinyal.models import ExtractedChange, MetricChange, SourceRecord
from imarsinyal.pipeline import event_from_record


class PublicationGuardTests(unittest.TestCase):
    def test_unproven_old_new_value_is_not_published(self) -> None:
        record = SourceRecord(
            source_id="aski:UIP:unproven",
            source_kind="aski",
            source_type="UIP",
            title="Çankaya örnek plan değişikliği",
            event_date="2026-07-25",
            district="Çankaya",
            plan_scales=["1/1000"],
            snapshot_hash="snapshot",
        )
        event = event_from_record(
            record,
            ExtractedChange(
                emsal=MetricChange(old_value="1.20", new_value="2.00"),
                categories=["construction_conditions"],
            ),
        )
        self.assertEqual(event.publication_status, "source_only")
        self.assertIsNone(event.changes.emsal.old_value)
        self.assertIsNone(event.changes.emsal.new_value)

    def test_regression_fixture_preserves_eleven_documents(self) -> None:
        fixture = (
            Path(__file__).parent / "fixtures" / "regression_events.json"
        )
        events = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(len(events), 11)
        self.assertEqual(len({item["id"] for item in events}), 11)


if __name__ == "__main__":
    unittest.main()
