import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.fact_validation import check  # noqa: E402
from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_config, load_records  # noqa: E402
from pipeline.quality_checks import check_all  # noqa: E402

CONFIG = load_config(ROOT / "config.yaml")

EXPECTED = {
    "dec_8864a6e7f8cb": "evasive_long",  # long reply dodging "is my data stored in the US?"
    "dec_96608358cd88": "repeated_template",  # branding template sent twice
    "dec_7b6d74b1a05f": "inappropriate_upsell",  # upgrade pushed for a currency bug
    "dec_inventory_fixture": "factual_or_policy_error",
    "dec_c0d416819201": "factual_or_policy_error",
}


def codes(record):
    return [i["code"] for i in record.get("_issues", []) if i["stage"] == "quality_checks"]


class QualityTests(unittest.TestCase):
    def setUp(self):
        records = load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]
        self.out = {r["decision_id"]: r for r in check_all([check(r, CONFIG) for r in records], CONFIG)}

    def test_planted_quality_problems_are_flagged(self):
        for decision_id, code in EXPECTED.items():
            self.assertIn(code, codes(self.out[decision_id]), decision_id)

    def test_every_flag_has_a_reason(self):
        for record in self.out.values():
            for issue in record.get("_issues", []):
                self.assertTrue(issue["code"] and issue["message"])
            self.assertEqual(record["_quality"] == "flagged", bool(codes(record)))

    def test_human_replies_and_good_answers_pass(self):
        for record in self.out.values():
            if record["author"] == "human":
                self.assertEqual(record["_quality"], "pass", record["decision_id"])
        # On-topic answer using synonyms: nominated softly, never as evasive.
        self.assertEqual(codes(self.out["dec_6e6c4e1dd069"]), ["possibly_unanswered"])
        self.assertEqual(self.out["dec_03734aa5ad69"]["_quality"], "pass")  # handoff to the team

    def test_template_sent_over_open_question(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        record["author"] = "template"
        record["response"]["text"] = "Subject: Tips\n\nAdd your logo under Settings."
        out = check_all([record], CONFIG)[0]
        self.assertIn("template_ignores_question", codes(out))


if __name__ == "__main__":
    unittest.main()
