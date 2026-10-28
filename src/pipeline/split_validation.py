"""Stage 9: keep original splits and prove no thread leaks across them.

Splits are never reassigned here. A thread found in more than one split is
reported and every record of that thread is marked "leak" so export drops it
with a documented reason.

Input:  data/intermediate/08_reviewed_golden.jsonl
Output: data/intermediate/09_split_validated.jsonl
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from pipeline.io import load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/08_reviewed_golden.jsonl")
DEFAULT_OUTPUT = Path("data/intermediate/09_split_validated.jsonl")


def validate_splits(records: list[dict]) -> list[dict]:
    splits = defaultdict(set)
    for record in records:
        splits[record["thread_id"]].add(record["split"])
    out = []
    for record in records:
        row = dict(record)
        seen = sorted(splits[row["thread_id"]])
        if len(seen) > 1:
            row["_split"] = {"status": "leak", "reason": f"thread {row['thread_id']} appears in splits {', '.join(seen)}"}
        else:
            row["_split"] = {"status": "ok", "reason": None}
        out.append(row)
    return out


def main() -> None:
    write_jsonl(DEFAULT_OUTPUT, validate_splits(load_records(DEFAULT_INPUT)))


if __name__ == "__main__":
    main()
