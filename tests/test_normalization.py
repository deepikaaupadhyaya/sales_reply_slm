import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_records  # noqa: E402
from pipeline.normalization import normalize  # noqa: E402


class NormalizationTests(unittest.TestCase):
    def test_showcase_is_already_normal_and_text_untouched(self):
        for record in load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]:
            self.assertEqual(normalize(record), record)

    def test_messy_values_are_standardized_but_text_kept(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        record["decision_id"] = "  dec_x \n"
        record["author"] = " AI "
        record["split"] = "Test"
        record["response"]["sent_at"] = "2026-03-01T11:00:20+01:00"
        record["response"]["text"] = "  Yes —  inventory!  "
        record["history"][0]["text"] = "\tDoes it?  "
        record["flags"] = ["synthetic", " Synthetic", ""]
        record["review"]["label"] = "  "
        out = normalize(record)
        self.assertEqual(out["decision_id"], "dec_x")
        self.assertEqual(out["author"], "ai")
        self.assertEqual(out["split"], "test")
        self.assertEqual(out["response"]["sent_at"], "2026-03-01T10:00:20Z")
        self.assertEqual(out["response"]["text"], "  Yes —  inventory!  ")
        self.assertEqual(out["history"][0]["text"], "\tDoes it?  ")
        self.assertEqual(out["flags"], ["synthetic"])
        self.assertIsNone(out["review"]["label"])
        self.assertEqual(record["author"], " AI ")  # input not mutated

    def test_bad_timestamp_is_flagged_not_dropped(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        record["response"]["sent_at"] = "yesterday"
        out = normalize(record)
        self.assertEqual(out["response"]["sent_at"], "yesterday")
        self.assertEqual(out["_issues"][0]["code"], "unparseable_timestamp")


if __name__ == "__main__":
    unittest.main()
