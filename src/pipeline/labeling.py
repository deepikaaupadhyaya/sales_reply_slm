"""Stage 8: export the human review queue as CSV, then merge it back once reviewed.

Export:  python3 -m pipeline.labeling
Merge:   python3 -m pipeline.labeling --merge data/review/review_queue_reviewed.csv --reviewer NAME
         -> data/intermediate/08_reviewed_golden.jsonl


proposed_label / suggested_correction are suggestions only. Corrections are
templated from campaign facts, never free-written. Reviewer columns are left
empty for Deepika. 08_reviewed_golden.jsonl is NOT written here; it waits
for the reviewed CSV.

Input:  data/intermediate/07_flagged_responses.jsonl
Output: data/review/review_queue.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from pipeline.io import load_config, load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/07_flagged_responses.jsonl")
DEFAULT_OUTPUT = Path("data/review/review_queue.csv")
PRODUCT_NAME = "Quillmint"  # ponytail: one dataset; move to config.yaml when a second product arrives

# First matching label wins, so the most serious problem is proposed.
LABELS = [
    ("factual_error", {"unsupported_feature", "wrong_price", "invented_discount", "release_date_claim"}),
    ("policy_violation", {"refund_promise", "opt_out_violation", "inappropriate_upsell", "overlong"}),
    ("irrelevant", {"evasive_long", "template_ignores_question"}),
    ("duplicate", {"repeated_template", "potential_duplicate"}),
    ("incomplete", {"empty_response"}),
]
LABEL_ORDER = [label for label, _ in LABELS] + ["needs_review", "correct"]

COLUMNS = [
    "decision_id", "thread_id", "split", "campaign_name", "author", "trigger",
    "last_prospect_message", "response_text", "issue_codes", "issue_messages", "evidence",
    "context_limitations", "later_human_reply", "proposed_label", "suggested_correction",
    "reviewer_label", "reviewer_correction", "reviewer_rationale",
]


def propose_label(issues: list[dict]) -> str:
    codes = {i["code"] for i in issues}
    for label, label_codes in LABELS:
        if codes & label_codes:
            return label
    return "needs_review" if any(i["severity"] != "info" for i in issues) else "correct"


def suggest_correction(record: dict, issues: list[dict], config: dict) -> str:
    text = record["response"]["text"].lower()
    lines = []
    if any(i["code"] == "unsupported_feature" for i in issues):
        for item, name in config["fact_checks"]["feature_display_names"].items():
            if item in text:
                lines.append(f"{name} is not currently available in {PRODUCT_NAME}.")
    for issue in issues:
        price = re.match(r"(\w+) quoted at \$\S+ \(facts: \$(\d+(?:\.\d+)?)\)", issue["message"])
        if issue["code"] == "wrong_price" and price:
            lines.append(f"{price.group(1)} is ${price.group(2)}/month.")
    return " ".join(lines)


def build_rows(records: list[dict], config: dict) -> list[dict]:
    rows = []
    for index, record in enumerate(records):
        issues = record.get("_issues", [])
        prospect = [m["text"] for m in record["history"] if m["speaker"] == "prospect"]
        later_human = sorted(
            (r["response"]["sent_at"], r["response"]["text"]) for r in records
            if r["thread_id"] == record["thread_id"] and r["author"] == "human"
            and r["response"]["sent_at"] > record["response"]["sent_at"]
        )
        label = propose_label(issues)
        rows.append((LABEL_ORDER.index(label), index, {
            "decision_id": record["decision_id"],
            "thread_id": record["thread_id"],
            "split": record["split"],
            "campaign_name": record["campaign_name"],
            "author": record["author"],
            "trigger": record["trigger"],
            "last_prospect_message": prospect[-1] if prospect else "",
            "response_text": record["response"]["text"],
            "issue_codes": ";".join(i["code"] for i in issues),
            "issue_messages": " | ".join(i["message"] for i in issues),
            "evidence": " | ".join(dict.fromkeys(i["evidence"] for i in issues if i.get("evidence"))),
            "context_limitations": " | ".join(record.get("_context", {}).get("limitations", [])),
            "later_human_reply": later_human[0][1] if later_human else "",
            "proposed_label": label,
            "suggested_correction": suggest_correction(record, issues, config),
            "reviewer_label": "",
            "reviewer_correction": "",
            "reviewer_rationale": "",
        }))
    return [row for _, _, row in sorted(rows, key=lambda r: (r[0], r[1]))]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel shows Spanish/Portuguese text correctly.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


REVIEWED_INPUT = Path("data/review/review_queue_reviewed.csv")
GOLDEN_OUTPUT = Path("data/intermediate/08_reviewed_golden.jsonl")
NEEDS_CORRECTION = {"factual_error", "policy_violation", "irrelevant", "incomplete"}


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def merge_review(records: list[dict], rows: list[dict], reviewer: str) -> list[dict]:
    """Stage 8 (second half): attach the human review to each record.

    The original response is kept; the review lands in record["review"].
    Refuses a CSV that is missing rows, has unknown rows, invalid labels, or
    edited response text, rather than merging a partial review.
    """
    by_id = {r["decision_id"]: r for r in rows}
    problems = sorted(set(by_id) ^ {r["decision_id"] for r in records})
    problems = [f"row set mismatch: {d}" for d in problems]
    for record in records:
        row = by_id.get(record["decision_id"])
        if row is None:
            continue
        if row["reviewer_label"] not in LABEL_ORDER:
            problems.append(f"{record['decision_id']}: reviewer_label {row['reviewer_label']!r} not in {LABEL_ORDER}")
        if row["response_text"] != record["response"]["text"]:
            problems.append(f"{record['decision_id']}: response_text was edited in the CSV")
    if problems:
        raise ValueError("reviewed CSV rejected:\n" + "\n".join(problems))

    out = []
    for record in records:
        row = by_id[record["decision_id"]]
        label = row["reviewer_label"]
        correction = row["reviewer_correction"].strip() or None
        if label == "needs_review":
            status, reason = "unresolved", "reviewer marked needs_review"
        elif label in NEEDS_CORRECTION and not correction:
            status, reason = "unresolved", f"{label} has no reviewer_correction"
        else:
            status, reason = "reviewed", None
        reviewed = dict(record)
        reviewed["review"] = {
            "status": status,
            "label": label,
            "corrected_response": correction,
            "rationale": row["reviewer_rationale"].strip() or None,
            "reviewer": reviewer,
            "proposed_label": row["proposed_label"],
            "unresolved_reason": reason,
        }
        out.append(reviewed)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merge", type=Path, help="reviewed CSV to merge into 08_reviewed_golden.jsonl")
    parser.add_argument("--reviewer", help="name of the human who filled the reviewer columns")
    args = parser.parse_args()
    if args.merge:
        if not args.reviewer:
            parser.error("--merge needs --reviewer")
        write_jsonl(GOLDEN_OUTPUT, merge_review(load_records(DEFAULT_INPUT), read_csv(args.merge), args.reviewer))
    else:
        write_csv(DEFAULT_OUTPUT, build_rows(load_records(DEFAULT_INPUT), load_config()))


if __name__ == "__main__":
    main()
