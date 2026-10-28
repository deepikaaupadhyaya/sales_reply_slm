"""Thin orchestrator: stages 1-7 plus the review CSV, then stop for human review.

Each stage still runs alone (`python3 -m pipeline.<stage>`). This file only
wires stage functions to their default paths and counts metrics.

Run from the repo root:  PYTHONPATH=src python3 -m pipeline.pipeline
Output: data/raw, data/intermediate, data/review/review_queue.csv, reports/metrics.json
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from pipeline import context_validation, deduplication, fact_validation, ingestion, labeling, normalization, quality_checks, schema_validation
from pipeline.io import load_config, write_jsonl

METRICS_OUTPUT = Path("reports/metrics.json")


def run(root: Path = Path("."), source: Path = ingestion.DEFAULT_SOURCE, config_path: Path = Path("config.yaml")) -> dict:
    root = Path(root)
    config = load_config(config_path)

    raw = ingestion.ingest(source, root / ingestion.DEFAULT_OUTPUT)
    valid, invalid = schema_validation.split_valid(raw)
    write_jsonl(root / schema_validation.VALID_OUTPUT, valid)
    write_jsonl(root / schema_validation.ERRORS_OUTPUT, invalid)
    normalized = [normalization.normalize(r) for r in valid]
    write_jsonl(root / normalization.DEFAULT_OUTPUT, normalized)
    deduped, duplicate_report = deduplication.deduplicate(normalized)
    write_jsonl(root / deduplication.DEFAULT_OUTPUT, deduped)
    write_jsonl(root / deduplication.REPORT_OUTPUT, duplicate_report)
    contextual = [context_validation.validate_context(r) for r in deduped]
    write_jsonl(root / context_validation.DEFAULT_OUTPUT, contextual)
    checked = [fact_validation.check(r, config) for r in contextual]
    write_jsonl(root / fact_validation.DEFAULT_OUTPUT, checked)
    flagged = quality_checks.check_all(checked, config)
    write_jsonl(root / quality_checks.DEFAULT_OUTPUT, flagged)
    rows = labeling.build_rows(flagged, config)
    labeling.write_csv(root / labeling.DEFAULT_OUTPUT, rows)

    report_codes = Counter(r["code"] for r in duplicate_report)
    missing = sum(any(e["code"] == "missing_field" for e in r["errors"]) for r in invalid)
    metrics = {
        "input_records": len(raw),
        "schema_valid": len(valid),
        "schema_invalid": len(invalid),
        "missing_field_rate": round(missing / len(raw), 4) if raw else 0.0,
        "exact_duplicates_dropped": report_codes["exact_duplicate"],
        "potential_duplicates": report_codes["potential_duplicate"],
        "decision_id_conflicts": report_codes["decision_id_conflict"],
        "context_failures": sum(r["_context"]["status"] != "ok" for r in contextual),
        "fact_policy_violations": sum(r["_fact_check"] == "flagged" for r in checked),
        "fact_policy_needs_review": sum(r["_fact_check"] == "needs_review" for r in checked),
        "quality_flagged": sum(r["_quality"] == "flagged" for r in flagged),
        "review_rows": len(rows),
        "proposed_labels": dict(sorted(Counter(r["proposed_label"] for r in rows).items())),
        "status": "stopped_for_human_review",
    }
    out = root / METRICS_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
