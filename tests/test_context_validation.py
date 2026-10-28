import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.context_validation import validate_context  # noqa: E402
from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_records  # noqa: E402


def codes(record):
    return [issue["code"] for issue in record.get("_issues", [])]


class ContextTests(unittest.TestCase):
    def test_showcase_and_fixture_pass(self):
        for record in load_records(ROOT / "showcase" / "candidates-readable.json") + [INVENTORY_FIXTURE]:
            out = validate_context(record)
            self.assertEqual(out["_context"]["status"], "ok", (record["decision_id"], codes(out)))

    def test_truncated_history_is_kept_with_limitation(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        record["flags"].append("history_truncated")
        out = validate_context(record)
        self.assertEqual(out["_context"]["status"], "ok")
        self.assertTrue(out["_context"]["limitations"])
        self.assertEqual(codes(out), ["history_truncated"])

    def test_broken_context_is_flagged(self):
        record = copy.deepcopy(INVENTORY_FIXTURE)
        record["history"][0]["sent_at"] = "2026-03-02T00:00:00Z"
        record["history"][0]["speaker"] = "ai"
        record["response"]["msg_id"] = record["history"][0]["msg_id"]
        out = validate_context(record)
        self.assertEqual(out["_context"]["status"], "needs_context")
        for code in ["history_after_response", "duplicate_message_id", "missing_prospect_message"]:
            self.assertIn(code, codes(out))


if __name__ == "__main__":
    unittest.main()
