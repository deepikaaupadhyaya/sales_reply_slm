import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_records  # noqa: E402
from pipeline.labeling import merge_review, read_csv  # noqa: E402
from pipeline.pipeline import run  # noqa: E402
from pipeline.split_validation import validate_splits  # noqa: E402


class SplitValidationTests(unittest.TestCase):
    def test_showcase_has_no_leakage_and_keeps_splits(self):
        records = load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]
        out = validate_splits(records)
        self.assertTrue(all(r["_split"]["status"] == "ok" for r in out))
        self.assertEqual([r["split"] for r in out], [r["split"] for r in records])

    def test_leaking_thread_is_marked_not_moved(self):
        moved = copy.deepcopy(INVENTORY_FIXTURE)
        moved["decision_id"] = "dec_moved"
        moved["split"] = "train"
        out = validate_splits([INVENTORY_FIXTURE, moved])
        self.assertEqual([r["_split"]["status"] for r in out], ["leak", "leak"])
        self.assertEqual([r["split"] for r in out], ["test", "train"])
        self.assertIn("test, train", out[0]["_split"]["reason"])

    def test_reviewed_csv_merges_and_feeds_split_stage(self):
        reviewed = ROOT / "data" / "review" / "review_queue_reviewed.csv"
        if not reviewed.exists():
            self.skipTest("reviewed CSV not present")
        with tempfile.TemporaryDirectory() as tmp:
            run(Path(tmp), ROOT / "showcase" / "candidates-readable.json", ROOT / "config.yaml")
            records = load_records(Path(tmp) / "data/intermediate/07_flagged_responses.jsonl")
        merged = merge_review(records, read_csv(reviewed), "Deepika")
        out = validate_splits(merged)
        self.assertEqual(len(out), 82)
        self.assertTrue(all(r["_split"]["status"] == "ok" for r in out))
        fixture = next(r for r in out if r["decision_id"] == "dec_inventory_fixture")
        self.assertEqual(fixture["review"]["label"], "factual_error")
        self.assertEqual(fixture["review"]["status"], "reviewed")
        self.assertEqual(fixture["response"]["text"], INVENTORY_FIXTURE["response"]["text"])  # original kept

    def test_merge_rejects_bad_or_partial_csv(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        good = {"decision_id": record["decision_id"], "response_text": record["response"]["text"], "proposed_label": "factual_error",
                "reviewer_label": "factual_error", "reviewer_correction": "", "reviewer_rationale": ""}
        merged = merge_review([record], [good], "Deepika")[0]
        self.assertEqual(merged["review"]["status"], "unresolved")  # error label without correction
        for bad in [dict(good, reviewer_label="great"), dict(good, response_text="edited"), dict(good, decision_id="dec_other")]:
            with self.assertRaises(ValueError):
                merge_review([record], [bad], "Deepika")
        with self.assertRaises(ValueError):
            merge_review([record], [], "Deepika")


if __name__ == "__main__":
    unittest.main()
