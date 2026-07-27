from __future__ import annotations

import unittest

from imarsinyal.models import Evidence, ExtractedChange, MetricChange, PlanningEvent
from imarsinyal.normalization import (
    clear_unchanged_metrics,
    district_from_text,
    neighborhood_from_text,
    normalize_metric_kind,
    normalize_parcels,
)
from imarsinyal.repair import repaired_district, repaired_parcels


class MetricGuardTests(unittest.TestCase):
    def test_uppercase_turkish_districts_are_normalized(self) -> None:
        self.assertEqual(
            district_from_text("KEÇİÖREN İLÇESİ BAĞLUM 1.VE2.ETAP"),
            "Keçiören",
        )
        self.assertEqual(
            district_from_text("GÖLBAŞI İLÇESİ BEZİRHANE MAH."),
            "Gölbaşı",
        )
        self.assertEqual(
            district_from_text("NALLIHAN İLÇESİ YUKARI BAĞLICA MAH."),
            "Nallıhan",
        )

    def test_uppercase_turkish_neighborhood_is_normalized(self) -> None:
        self.assertEqual(
            neighborhood_from_text("GÖLBAŞI İLÇESİ BEZİRHANE MAH."),
            "Bezirhane",
        )
        self.assertEqual(
            neighborhood_from_text("NALLIHAN İLÇESİ YUKARI BAĞLICA MAH."),
            "Yukarı Bağlıca",
        )

    def test_scales_decisions_and_adjacent_adas_are_not_parcels(self) -> None:
        text = (
            "513, 514, 515, 517 ve 518 adalarda 1/5000 ve 1/1000 ölçekli "
            "plan değişikliği, 2026/750 sayılı karar"
        )
        self.assertEqual(normalize_parcels(text), [])

    def test_explicit_multiple_parcels_are_preserved(self) -> None:
        text = (
            "108 ada 1 parsel ve 109 ada 1 parsel ile "
            "91771 ada 6 ve 9 sayılı parseller"
        )
        self.assertEqual(
            normalize_parcels(text),
            ["108/1", "109/1", "91771/6", "91771/9"],
        )

    def test_shorthand_parcel_lists_are_expanded_per_ada(self) -> None:
        text = (
            "863/1, 2, 3, 4 ve 2150/4, 5, 6, 7, 8, 9, 10, 11, 12 "
            "parsellerde 1/1000 ölçekli plan, 2026/750 sayılı karar"
        )
        self.assertEqual(
            normalize_parcels(text),
            [
                "863/1",
                "863/2",
                "863/3",
                "863/4",
                "2150/4",
                "2150/5",
                "2150/6",
                "2150/7",
                "2150/8",
                "2150/9",
                "2150/10",
                "2150/11",
                "2150/12",
            ],
        )

    def test_multi_ada_ranges_expand_without_plan_number_false_positive(self) -> None:
        text = (
            "40455 Ada 1 ila 3, 40456 Ada 2 ve 4 sayılı parseller ile "
            "86230/1 NPP ve 3629/16 nolu parselasyon planı"
        )
        self.assertEqual(
            normalize_parcels(text),
            ["40455/1", "40455/2", "40455/3", "40456/2", "40456/4"],
        )

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

    def test_identical_old_and_new_values_are_not_changes(self) -> None:
        change = ExtractedChange(
            emsal=MetricChange(
                old_value="1,60",
                new_value="1.6",
                unit="Emsal",
                evidence_ids=["same"],
            )
        )
        normalized = clear_unchanged_metrics(change)
        self.assertIsNone(normalized.emsal.old_value)
        self.assertIsNone(normalized.emsal.new_value)
        self.assertEqual(normalized.emsal.evidence_ids, [])


class ParcelRepairTests(unittest.TestCase):
    @staticmethod
    def event(title: str, parcels: list[str], summary: str = "") -> PlanningEvent:
        return PlanningEvent(
            id="test-event",
            slug="test-event",
            source_kind="aski",
            source_type="abb_aski",
            title=title,
            summary=summary,
            stage="on_appeal",
            event_date="2026-07-26",
            district="Ankara",
            neighborhood=None,
            parcels=parcels,
            plan_scales=[],
            categories=["plan_note"],
            impact_score=10,
            publication_status="source_only",
            source_urls={"source": "https://example.test"},
            changes=ExtractedChange(),
        )

    def test_repair_replaces_old_scale_values_with_explicit_parcels(self) -> None:
        event = self.event(
            "108 ada 1 parsel 1/1000 ölçekli plan değişikliği",
            ["108/1", "1/1000"],
        )
        self.assertEqual(repaired_parcels(event), ["108/1"])

    def test_repair_clears_ada_group_misread_as_parcel_pairs(self) -> None:
        event = self.event(
            "513, 514, 515, 517 ve 518 adalarda 1/5000 ve 1/1000 plan değişikliği",
            ["513/514", "515/517", "1/5000", "1/1000"],
        )
        self.assertEqual(repaired_parcels(event), [])

    def test_repair_preserves_unverifiable_but_plausible_existing_parcel(self) -> None:
        event = self.event("Beytepe plan değişikliği", ["18116/1"])
        self.assertEqual(repaired_parcels(event), ["18116/1"])

    def test_repair_infers_only_missing_ankara_district(self) -> None:
        event = self.event(
            "KEÇİÖREN İLÇESİ BAĞLUM 1.VE2.ETAP",
            [],
        )
        self.assertEqual(repaired_district(event), "Keçiören")
        event.district = "Çankaya"
        self.assertEqual(repaired_district(event), "Çankaya")


if __name__ == "__main__":
    unittest.main()
