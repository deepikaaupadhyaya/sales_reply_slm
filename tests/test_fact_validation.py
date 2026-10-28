import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.fact_validation import check  # noqa: E402
from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_config, load_records  # noqa: E402

CONFIG = load_config(ROOT / "config.yaml")

# Planted fact/policy mistakes in the showcase data (see showcase/README.md).
EXPECTED = {
    "dec_84d4a5c131c3": "unsupported_feature",  # payroll
    "dec_c0d416819201": "wrong_price",  # Studio $24
    "dec_5bb99237916d": "opt_out_violation",  # pitch after "stop emailing me"
    "dec_8f8307a40204": "invented_discount",  # 50% off forever
    "dec_445366b9efa0": "release_date_claim",  # April release
    "dec_a35670de95bf": "invented_discount",  # 30% charity discount
    "dec_8c2d9cb89a57": "refund_promise",  # AI refunded the charge
    "dec_inventory_fixture": "unsupported_feature",
}


def codes(record):
    return [i["code"] for i in record.get("_issues", []) if i["stage"] == "fact_validation"]


class FactValidationTests(unittest.TestCase):
    def setUp(self):
        records = load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]
        self.out = {r["decision_id"]: check(r, CONFIG) for r in records}

    def test_planted_mistakes_are_flagged(self):
        for decision_id, code in EXPECTED.items():
            self.assertIn(code, codes(self.out[decision_id]), decision_id)
            self.assertEqual(self.out[decision_id]["_fact_check"], "flagged")

    def test_no_other_record_is_flagged_as_error(self):
        flagged = {d for d, r in self.out.items() if r["_fact_check"] == "flagged"}
        self.assertEqual(flagged, set(EXPECTED))

    def test_issues_cite_campaign_text(self):
        issue = [i for i in self.out["dec_inventory_fixture"]["_issues"] if i["code"] == "unsupported_feature"][0]
        self.assertEqual(issue["evidence"], "Not available: payroll, inventory, time tracking. Time tracking is on the roadmap with no date.")
        self.assertIn(issue["evidence"], INVENTORY_FIXTURE["campaign"]["facts"])

    def test_negated_mentions_and_unclear_prices(self):
        self.assertEqual(self.out["dec_b248e65c726d"]["_fact_check"], "pass")  # "Not yet. Time tracking ... no date"
        self.assertEqual(self.out["dec_9ffbebac9e7b"]["_fact_check"], "pass")  # "we don't have a ... discount"
        self.assertEqual(self.out["dec_70f0665919f2"]["_fact_check"], "needs_review")  # derived $5.40 commission

    def test_facts_come_from_record_not_code(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        record["campaign"]["facts"] = [f.replace("inventory, ", "") for f in record["campaign"]["facts"]]
        self.assertEqual(check(record, CONFIG)["_fact_check"], "pass")


if __name__ == "__main__":
    unittest.main()
