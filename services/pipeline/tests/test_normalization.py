from __future__ import annotations

import unittest

from imarsinyal.models import Evidence, ExtractedChange, MetricChange
from imarsinyal.normalization import normalize_metric_kind


class MetricGuardTests(unittest.TestCase):
    def test_yuva_density_never_becomes_emsal(self) -> None:
        change = ExtractedChange(
            emsal=MetricChange(
                new_value="121–250 kişi/ha",
                unit="kişi/ha",
                evidence_ids=["yuva-p1"],
            ),
            evidence=[
                Evidence(
                    id="yuva-p1",
                    document_url="https://example.test/yuva.pdf",
                    field_names=["density.new_value"],
                    page=1,
                )
            ],
        )
        normalized = normalize_metric_kind(change)
        self.assertIsNone(normalized.emsal.new_value)
        self.assertEqual(normalized.density.new_value, "121–250 kişi/ha")
        self.assertEqual(normalized.density.evidence_ids, ["yuva-p1"])

    def test_korkutreis_taks_never_becomes_emsal(self) -> None:
        change = ExtractedChange(
            emsal=MetricChange(
                new_value="0.60",
                unit="TAKS",
                evidence_ids=["korkutreis-p1"],
            )
        )
        normalized = normalize_metric_kind(change)
        self.assertIsNone(normalized.emsal.new_value)
        self.assertEqual(normalized.taks.new_value, "0.60")
        self.assertEqual(normalized.taks.evidence_ids, ["korkutreis-p1"])


if __name__ == "__main__":
    unittest.main()

