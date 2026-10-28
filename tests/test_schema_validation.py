import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_records  # noqa: E402
from pipeline.schema_validation import split_valid  # noqa: E402


class SchemaTests(unittest.TestCase):
    def test_showcase_and_fixture_are_valid(self):
        records = load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]
        valid, invalid = split_valid(records)
        self.assertEqual(invalid, [])
        self.assertEqual(len(valid), 82)

    def test_invalid_records_are_isolated_with_reasons(self):
        bad = []
        for mutate in [
            lambda r: r.pop("decision_id"),
            lambda r: r.__setitem__("history", "not a list"),
            lambda r: r.__setitem__("split", "holdout"),
            lambda r: r["response"].pop("text"),
            lambda r: r["history"][0].__setitem__("speaker", 3),
            lambda r: r["campaign"].__setitem__("facts", [1]),
        ]:
            record = copy.deepcopy(INVENTORY_FIXTURE)
            mutate(record)
            bad.append(record)
        valid, invalid = split_valid([INVENTORY_FIXTURE, *bad, "not a dict"])
        self.assertEqual(valid, [INVENTORY_FIXTURE])
        self.assertEqual(len(invalid), 7)
        for row in invalid:
            self.assertTrue(row["errors"])
            for error in row["errors"]:
                self.assertTrue(error["code"] and error["message"])
        codes = [e["code"] for row in invalid for e in row["errors"]]
        self.assertIn("invalid_split", codes)
        self.assertIn("missing_field", codes)


if __name__ == "__main__":
    unittest.main()
