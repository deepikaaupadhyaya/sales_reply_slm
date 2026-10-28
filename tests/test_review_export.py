import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.pipeline import run  # noqa: E402

SOURCE = ROOT / "showcase" / "candidates-readable.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class ReviewExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = SOURCE.read_bytes()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.metrics = run(cls.root, SOURCE, ROOT / "config.yaml")
        cls.rows = read_csv(cls.root / "data/review/review_queue.csv")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_one_row_per_stage7_record_with_empty_reviewer_columns(self):
        stage7 = (self.root / "data/intermediate/07_flagged_responses.jsonl").read_text().splitlines()
        self.assertEqual(len(self.rows), len(stage7))
        self.assertEqual(len(self.rows), 82)
        for row in self.rows:
            self.assertEqual((row["reviewer_label"], row["reviewer_correction"], row["reviewer_rationale"]), ("", "", ""))

    def test_inventory_row_proposes_grounded_correction(self):
        row = next(r for r in self.rows if r["decision_id"] == "dec_inventory_fixture")
        self.assertEqual(row["proposed_label"], "factual_error")
        self.assertEqual(row["suggested_correction"], "Inventory management is not currently available in Quillmint.")
        self.assertIn("Not available: payroll, inventory, time tracking.", row["evidence"])

    def test_planted_mistakes_get_a_problem_label(self):
        by_id = {r["decision_id"]: r for r in self.rows}
        expected = {
            "dec_c0d416819201": "factual_error", "dec_84d4a5c131c3": "factual_error",
            "dec_445366b9efa0": "factual_error", "dec_a35670de95bf": "factual_error",
            "dec_8f8307a40204": "factual_error", "dec_8c2d9cb89a57": "policy_violation",
            "dec_5bb99237916d": "policy_violation", "dec_7b6d74b1a05f": "policy_violation",
            "dec_8864a6e7f8cb": "policy_violation", "dec_96608358cd88": "duplicate",
        }
        for decision_id, label in expected.items():
            self.assertEqual(by_id[decision_id]["proposed_label"], label, decision_id)
        self.assertEqual(by_id["dec_c0d416819201"]["suggested_correction"], "Studio is $27/month.")
        self.assertEqual(self.rows[0]["proposed_label"], "factual_error")  # problems first

    def test_stops_before_golden_and_reports_metrics(self):
        self.assertFalse(list(self.root.glob("data/**/08_*")))
        self.assertFalse((self.root / "data/golden").exists())
        metrics = json.loads((self.root / "reports/metrics.json").read_text())
        self.assertEqual(metrics["input_records"], 82)
        self.assertEqual(metrics["review_rows"], 82)
        self.assertEqual(metrics["status"], "stopped_for_human_review")
        for key in ["schema_invalid", "missing_field_rate", "potential_duplicates", "context_failures", "fact_policy_violations", "quality_flagged"]:
            self.assertIn(key, metrics)

    def test_source_unchanged_and_outputs_reproducible(self):
        self.assertEqual(SOURCE.read_bytes(), self.original)
        with tempfile.TemporaryDirectory() as other:
            run(Path(other), SOURCE, ROOT / "config.yaml")
            for path in sorted(self.root.rglob("*")):
                if path.is_file() and path.name != "01_ingest_metadata.json":
                    self.assertEqual(path.read_bytes(), (Path(other) / path.relative_to(self.root)).read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
