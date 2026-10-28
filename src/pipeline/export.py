"""Stage 10: apply the golden-record checklist and export per split.

A record is golden only if its context is ok, it has no unresolved ID/context
error, a human review is complete (label, plus correction where required),
and its thread does not leak across splits. Everything else is listed in
quality_report.json with the reasons. No wall-clock values, so reruns are
byte-identical.

Input:  data/intermediate/09_split_validated.jsonl
Output: data/golden/golden_{train,validation,test}.jsonl, reports/quality_report.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pipeline.io import load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/09_split_validated.jsonl")
GOLDEN_DIR = Path("data/golden")
REPORT_OUTPUT = Path("reports/quality_report.json")
SPLITS = ["train", "validation", "test"]
BLOCKING_STAGES = {"deduplication", "context_validation", "normalization"}


def exclusion_reasons(record: dict) -> list[str]:
    reasons = []
    if record.get("_context", {}).get("status") != "ok":
        reasons.append("context: needs more context")
    for issue in record.get("_issues", []):
        if issue["stage"] in BLOCKING_STAGES and issue["severity"] == "error":
            reasons.append(f"{issue['stage']}: {issue['code']}")
    review = record["review"]
    if review.get("status") != "reviewed":
        reasons.append(f"review: {review.get('unresolved_reason') or 'not reviewed'}")
    if record.get("_split", {}).get("status") != "ok":
        reasons.append(f"split: {record['_split']['reason']}")
    return reasons


def export(records: list[dict]) -> tuple[dict[str, list[dict]], dict]:
    golden = {split: [] for split in SPLITS}
    excluded = []
    for record in records:
        reasons = exclusion_reasons(record)
        if reasons:
            excluded.append({"decision_id": record["decision_id"], "split": record["split"], "label": record["review"].get("label"), "reasons": reasons})
        else:
            golden[record["split"]].append(record)

    threads = {split: {r["thread_id"] for r in rows} for split, rows in golden.items()}
    leaked = sorted((threads["train"] & threads["validation"]) | (threads["train"] & threads["test"]) | (threads["validation"] & threads["test"]))
    if leaked:
        raise ValueError(f"thread leakage in golden export: {leaked}")

    report = {
        "input_records": len(records),
        "golden_records": sum(len(rows) for rows in golden.values()),
        "excluded_records": len(excluded),
        "per_split": {split: {"records": len(rows), "threads": len(threads[split]), "labels": dict(sorted(Counter(r["review"]["label"] for r in rows).items()))} for split, rows in golden.items()},
        "corrections_provided": sum(1 for rows in golden.values() for r in rows if r["review"].get("corrected_response")),
        "reviewer_changed_proposed_label": sum(1 for rows in golden.values() for r in rows if r["review"]["label"] != r["review"].get("proposed_label")),
        "source_checksums": sorted({f"{r['_source']['filename']}:{r['_source']['sha256']}" for r in records if "_source" in r}),
        "checks": {"thread_leakage": "none", "every_golden_record_reviewed": True},
        "excluded": excluded,
    }
    return golden, report


def write_outputs(root: Path, golden: dict[str, list[dict]], report: dict) -> None:
    root = Path(root)
    for split, rows in golden.items():
        write_jsonl(root / GOLDEN_DIR / f"golden_{split}.jsonl", rows)
    out = root / REPORT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    write_outputs(Path("."), *export(load_records(DEFAULT_INPUT)))


if __name__ == "__main__":
    main()
