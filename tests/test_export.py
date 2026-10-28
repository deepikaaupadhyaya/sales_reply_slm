import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.export import export, write_outputs  # noqa: E402
from pipeline.io import load_records  # noqa: E402
from pipeline.labeling import merge_review, read_csv  # noqa: E402
from pipeline.pipeline import run  # noqa: E402
from pipeline.split_validation import validate_splits  # noqa: E402

REVIEWED = ROOT / "data" / "review" / "review_queue_reviewed.csv"


@unittest.skipUnless(REVIEWED.exists(), "reviewed CSV not present")
class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            run(Path(tmp), ROOT / "showcase" / "candidates-readable.json", ROOT / "config.yaml")
            stage7 = load_records(Path(tmp) / "data/intermediate/07_flagged_responses.jsonl")
        cls.records = validate_splits(merge_review(stage7, read_csv(REVIEWED), "Deepika"))
        cls.golden, cls.report = export(cls.records)

    def test_only_reviewed_records_are_golden(self):
        for rows in self.golden.values():
            for record in rows:
                self.assertEqual(record["review"]["status"], "reviewed")
        excluded = {e["decision_id"] for e in self.report["excluded"]}
        self.assertEqual(excluded, {"dec_ab673cd36e7c", "dec_32bd7f0ab708"})
        self.assertEqual(self.report["golden_records"] + self.report["excluded_records"], 82)

    def test_no_thread_in_two_golden_files(self):  # AC-4
        seen = {}
        for split, rows in self.golden.items():
            for record in rows:
                self.assertEqual(seen.setdefault(record["thread_id"], split), split)

    def test_inventory_fixture_is_golden_with_correction(self):
        fixture = next(r for r in self.golden["test"] if r["decision_id"] == "dec_inventory_fixture")
        self.assertEqual(fixture["review"]["label"], "factual_error")
        self.assertTrue(fixture["review"]["corrected_response"])

    def test_reviewer_relabel_reaches_golden(self):
        record = next(r for r in self.golden["train"] if r["decision_id"] == "dec_70f0665919f2")
        self.assertEqual(record["review"]["label"], "policy_violation")
        self.assertNotIn("$27", record["review"]["corrected_response"])

    def test_reruns_are_byte_identical(self):  # AC-5
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            write_outputs(Path(a), *export(self.records))
            write_outputs(Path(b), *export(copy.deepcopy(self.records)))
            for path in sorted(Path(a).rglob("*")):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (Path(b) / path.relative_to(a)).read_bytes(), path.name)
            report = json.loads((Path(a) / "reports/quality_report.json").read_text())
            self.assertEqual(report["checks"]["thread_leakage"], "none")

    def test_leak_or_blocking_error_is_excluded(self):
        leak = copy.deepcopy(self.records[0])
        leak["_split"] = {"status": "leak", "reason": "thread x appears in splits test, train"}
        broken = copy.deepcopy(self.records[1])
        broken.setdefault("_issues", []).append({"stage": "deduplication", "code": "decision_id_conflict", "message": "m", "severity": "error"})
        golden, report = export([leak, broken])
        self.assertEqual(sum(len(v) for v in golden.values()), 0)
        self.assertIn("split: thread x appears in splits test, train", report["excluded"][0]["reasons"])
        self.assertIn("deduplication: decision_id_conflict", report["excluded"][1]["reasons"])


if __name__ == "__main__":
    unittest.main()
