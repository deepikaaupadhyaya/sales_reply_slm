"""Stage 4: ID consistency and duplicate detection.

Handling (documented in every report row's `action`):
- exact duplicate (same decision_id, same content): later copy dropped
- decision_id conflict (same id, different content): both kept, flagged error
- potential duplicate (same thread, same response text): kept, flagged for review
- thread reference conflict (one thread, several prospects/campaigns): kept, flagged error

Input:  data/intermediate/03_normalized.jsonl
Output: data/intermediate/04_deduplicated.jsonl, data/intermediate/04_duplicate_report.jsonl
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.io import add_issue, load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/03_normalized.jsonl")
DEFAULT_OUTPUT = Path("data/intermediate/04_deduplicated.jsonl")
REPORT_OUTPUT = Path("data/intermediate/04_duplicate_report.jsonl")

ID_PREFIXES = {"decision_id": "dec_", "thread_id": "thr_", "prospect_id": "pro_", "campaign_id": "cmp_"}


def _content(record: dict) -> str:
    return json.dumps({k: v for k, v in record.items() if not k.startswith("_")}, sort_keys=True, ensure_ascii=False)


def _text_key(text: str) -> str:
    return " ".join(text.lower().split())


def deduplicate(records: list[dict]) -> tuple[list[dict], list[dict]]:
    kept, report = [], []
    by_id: dict[str, dict] = {}
    by_thread_text: dict[tuple, dict] = {}
    thread_refs: dict[str, tuple] = {}

    for record in records:
        decision_id = record["decision_id"]
        first = by_id.get(decision_id)
        if first is not None and _content(first) == _content(record):
            report.append({"code": "exact_duplicate", "decision_id": decision_id, "duplicate_of": decision_id, "action": "dropped_exact_duplicate"})
            continue
        row = dict(record)
        if first is not None:
            add_issue(row, "deduplication", "decision_id_conflict", f"decision_id {decision_id} appears with different content", "error")
            report.append({"code": "decision_id_conflict", "decision_id": decision_id, "duplicate_of": decision_id, "action": "kept_both_flagged"})
        by_id.setdefault(decision_id, record)

        for field, prefix in ID_PREFIXES.items():
            if not row[field].startswith(prefix):
                add_issue(row, "deduplication", "invalid_id_format", f"{field} {row[field]!r} should start with {prefix}", "error")

        refs = (row["prospect_id"], row["campaign_id"])
        known = thread_refs.setdefault(row["thread_id"], refs)
        if known != refs:
            add_issue(row, "deduplication", "thread_reference_conflict", f"thread {row['thread_id']} already maps to prospect/campaign {known}", "error")
            report.append({"code": "thread_reference_conflict", "decision_id": decision_id, "duplicate_of": None, "action": "kept_flagged"})

        key = (row["thread_id"], _text_key(row["response"]["text"]))
        earlier = by_thread_text.setdefault(key, row)
        if earlier is not row:
            add_issue(row, "deduplication", "potential_duplicate", f"same response text as {earlier['decision_id']} in this thread", "review")
            report.append({"code": "potential_duplicate", "decision_id": decision_id, "duplicate_of": earlier["decision_id"], "action": "kept_for_review"})
        kept.append(row)
    return kept, report


def main() -> None:
    kept, report = deduplicate(load_records(DEFAULT_INPUT))
    write_jsonl(DEFAULT_OUTPUT, kept)
    write_jsonl(REPORT_OUTPUT, report)


if __name__ == "__main__":
    main()
