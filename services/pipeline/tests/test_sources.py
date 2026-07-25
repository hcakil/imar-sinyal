from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from imarsinyal.models import SourceRecord
from imarsinyal.sources.aski import feature_to_record, fetch_aski_records


class SourceResilienceTests(unittest.TestCase):
    def test_arcgis_polygon_is_firestore_safe_without_losing_geometry(self) -> None:
        geometry = {
            "rings": [
                [
                    [32.8, 39.9],
                    [32.9, 39.9],
                    [32.9, 40.0],
                    [32.8, 39.9],
                ]
            ],
            "spatialReference": {"wkid": 4326},
        }
        record = feature_to_record(
            {
                "attributes": {
                    "GLOBALID": "{A}",
                    "planadi": "Çankaya Beytepe 28517 ada 2 parsel",
                },
                "geometry": geometry,
            },
            source_type="UIP",
            source_title="1/1000 Uygulama İmar Planı",
        )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(json.loads(record.geometry["arcgis_json"]), geometry)
        self.assertEqual(record.geometry["bbox"], [32.8, 39.9, 32.9, 40.0])
        self.assertEqual(record.geometry["centroid"], [32.85, 39.925])

    @patch("imarsinyal.sources.aski.query_layer")
    def test_one_layer_failure_does_not_stop_other_layers(self, query) -> None:
        query.side_effect = [
            [
                {
                    "attributes": {
                        "GLOBALID": "{A}",
                        "planadi": "Çankaya Beytepe 28517 ada 2 parsel",
                    }
                }
            ],
            RuntimeError("CDP unavailable"),
            [],
            [],
        ]
        records, errors = fetch_aski_records()
        self.assertEqual(len(records), 1)
        self.assertIsInstance(records[0], SourceRecord)
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
