from __future__ import annotations

import unittest
from unittest.mock import patch

from imarsinyal.models import SourceRecord
from imarsinyal.sources.aski import fetch_aski_records


class SourceResilienceTests(unittest.TestCase):
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
