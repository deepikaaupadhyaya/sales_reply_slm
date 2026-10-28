"""Stage 5: check each reply has usable conversation context.

Records are never dropped here. Truncated history is kept and recorded as a
limitation; structural problems are flagged so review does not guess.

Input:  data/intermediate/04_deduplicated.jsonl
Output: data/intermediate/05_context_validated.jsonl
"""

from __future__ import annotations

from pathlib import Path

from pipeline.io import add_issue, load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/04_deduplicated.jsonl")
DEFAULT_OUTPUT = Path("data/intermediate/05_context_validated.jsonl")

SPEAKERS = {"prospect", "ai", "human", "template"}
NEEDS_PROSPECT = {"prospect_reply", "human_takeover"}


def validate_context(record: dict) -> dict:
    row = dict(record)
    row["_issues"] = list(record.get("_issues", []))
    history = row["history"]
    limitations = []

    def issue(code, message, severity):
        add_issue(row, "context_validation", code, message, severity)

    times = [m["sent_at"] for m in history]
    if times != sorted(times):
        issue("history_out_of_order", "history messages are not in chronological order", "review")
    if any(t > row["response"]["sent_at"] for t in times):
        issue("history_after_response", "a history message is dated after the response", "error")
    ids = [m["msg_id"] for m in history] + [row["response"]["msg_id"]]
    if len(ids) != len(set(ids)):
        issue("duplicate_message_id", "a msg_id repeats within history or the response", "error")
    unknown = sorted({m["speaker"] for m in history} - SPEAKERS)
    if unknown:
        issue("unknown_speaker", f"unknown speaker(s): {', '.join(unknown)}", "review")
    if (not history) != ("empty_history" in row["flags"]):
        issue("empty_history_flag_mismatch", "empty_history flag does not match history length", "review")
    if row["trigger"] in NEEDS_PROSPECT and not any(m["speaker"] == "prospect" for m in history):
        issue("missing_prospect_message", f"trigger {row['trigger']} but no prospect message in history", "review")
    if "history_truncated" in row["flags"]:
        limitations.append("history_truncated: older messages were dropped; judge only on visible context")
        issue("history_truncated", "older history was dropped; kept with documented limitation", "info")

    blocking = [i for i in row["_issues"] if i["stage"] == "context_validation" and i["severity"] != "info"]
    row["_context"] = {"status": "needs_context" if blocking else "ok", "limitations": limitations}
    if not row["_issues"]:
        del row["_issues"]
    return row


def main() -> None:
    write_jsonl(DEFAULT_OUTPUT, [validate_context(r) for r in load_records(DEFAULT_INPUT)])


if __name__ == "__main__":
    main()
