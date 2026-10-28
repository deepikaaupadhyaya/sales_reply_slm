"""Stage 3: standardize representation without changing meaning.

Message text (history[].text, response.text) is never modified.

Input:  data/intermediate/02_schema_valid.jsonl
Output: data/intermediate/03_normalized.jsonl
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

from pipeline.io import add_issue, load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/02_schema_valid.jsonl")
DEFAULT_OUTPUT = Path("data/intermediate/03_normalized.jsonl")

ID_FIELDS = ["decision_id", "thread_id", "prospect_id", "campaign_id"]
ENUM_FIELDS = ["campaign_name", "channel", "trigger", "author", "split"]


def _timestamp(value: str, record: dict, where: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        add_issue(record, "normalization", "unparseable_timestamp", f"{where} {value!r} is not ISO-8601", "review")
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


def normalize(record: dict) -> dict:
    row = copy.deepcopy(record)
    for field in ID_FIELDS:
        row[field] = row[field].strip()
    for field in ENUM_FIELDS:
        row[field] = row[field].strip().lower()
    for message in row["history"]:
        message["msg_id"] = message["msg_id"].strip()
        message["speaker"] = message["speaker"].strip().lower()
        message["sent_at"] = _timestamp(message["sent_at"], row, f"history {message['msg_id']} sent_at")
    row["response"]["msg_id"] = row["response"]["msg_id"].strip()
    row["response"]["sent_at"] = _timestamp(row["response"]["sent_at"], row, "response.sent_at")
    row["campaign"]["rules"] = [rule.strip() for rule in row["campaign"]["rules"]]
    row["campaign"]["facts"] = [fact.strip() for fact in row["campaign"]["facts"]]
    row["flags"] = list(dict.fromkeys(str(flag).strip().lower() for flag in row["flags"] if str(flag).strip()))
    row["review"] = {key: _blank_to_none(value) for key, value in row["review"].items()}
    row["review"].setdefault("label", None)
    row["review"].setdefault("corrected_response", None)
    return row


def main() -> None:
    write_jsonl(DEFAULT_OUTPUT, [normalize(r) for r in load_records(DEFAULT_INPUT)])


if __name__ == "__main__":
    main()
