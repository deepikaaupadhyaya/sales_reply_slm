import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.deduplication import deduplicate  # noqa: E402
from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_records  # noqa: E402


def codes(record):
    return [issue["code"] for issue in record.get("_issues", [])]


class DeduplicationTests(unittest.TestCase):
    def test_showcase_keeps_everything_and_finds_double_template(self):
        records = load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]
        kept, report = deduplicate(records)
        self.assertEqual(len(kept), len(records))  # AC-7: nothing deleted
        self.assertEqual(codes(kept[-1]), [])  # inventory fixture passes
        potential = [r for r in report if r["code"] == "potential_duplicate"]
        self.assertIn(("dec_96608358cd88", "dec_edf94a26b229"), [(r["decision_id"], r["duplicate_of"]) for r in potential])
        self.assertFalse([r for r in report if r["code"] != "potential_duplicate"])

    def test_exact_conflict_and_reference_handling(self):
        conflict = copy.deepcopy(INVENTORY_FIXTURE)
        conflict["response"]["text"] = "different"
        other_prospect = copy.deepcopy(INVENTORY_FIXTURE)
        other_prospect["decision_id"] = "dec_other"
        other_prospect["prospect_id"] = "pro_other"
        other_prospect["response"]["text"] = "another reply"
        bad_id = copy.deepcopy(INVENTORY_FIXTURE)
        bad_id["decision_id"] = "x123"
        bad_id["response"]["text"] = "third reply"
        kept, report = deduplicate([INVENTORY_FIXTURE, copy.deepcopy(INVENTORY_FIXTURE), conflict, other_prospect, bad_id])
        self.assertEqual(len(kept), 4)
        actions = {r["code"]: r["action"] for r in report}
        self.assertEqual(actions["exact_duplicate"], "dropped_exact_duplicate")
        self.assertEqual(actions["decision_id_conflict"], "kept_both_flagged")
        self.assertEqual(actions["thread_reference_conflict"], "kept_flagged")
        self.assertIn("decision_id_conflict", codes(kept[1]))
        self.assertIn("invalid_id_format", codes(kept[3]))


if __name__ == "__main__":
    unittest.main()
