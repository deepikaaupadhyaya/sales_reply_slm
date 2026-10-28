"""Stage 7: nominate low-quality replies for review, one reason per flag.

These are heuristics: they nominate records for human review and never
certify that a reply is semantically correct. Only automated replies
(config automated_authors) are judged; human replies pass through.

Input:  data/intermediate/06_fact_policy_checked.jsonl
Output: data/intermediate/07_flagged_responses.jsonl
"""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.io import add_issue, load_config, load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/06_fact_policy_checked.jsonl")
DEFAULT_OUTPUT = Path("data/intermediate/07_flagged_responses.jsonl")
STAGE = "quality_checks"


def _stems(text: str, stopwords: set[str]) -> set[str]:
    return {w[:5] for w in re.findall(r"\w+", text.lower()) if len(w) > 2 and w not in stopwords}


def _last_prospect(record: dict) -> str | None:
    if record["history"] and record["history"][-1]["speaker"] == "prospect":
        return record["history"][-1]["text"]
    return None


def check_all(records: list[dict], config: dict) -> list[dict]:
    cfg = config["quality_checks"]
    stopwords = set(cfg["stopwords"])
    sent_texts = {}  # (thread_id, text) -> earliest sent_at
    for r in records:
        key = (r["thread_id"], " ".join(r["response"]["text"].split()))
        sent_texts[key] = min(sent_texts.get(key, r["response"]["sent_at"]), r["response"]["sent_at"])

    out = []
    for record in records:
        row = dict(record)
        row["_issues"] = list(record.get("_issues", []))
        text = row["response"]["text"]
        prospect = _last_prospect(row)

        def flag(code, message, severity="review"):
            add_issue(row, STAGE, code, message, severity)

        fact_errors = sorted({i["code"] for i in row["_issues"] if i["stage"] == "fact_validation" and i["severity"] == "error"})
        if fact_errors:
            flag("factual_or_policy_error", f"reply carries fact/policy errors: {', '.join(fact_errors)}", "error")

        if row["author"] in config["automated_authors"]:
            words = len(text.split())
            if not text.strip():
                flag("empty_response", "reply has no text", "error")
            limit = cfg["max_words"].get(row["campaign_name"])
            if limit and words > limit:
                flag("overlong", f"{words} words, campaign limit is {limit}")
            if " ".join(text.split()) and sent_texts[(row["thread_id"], " ".join(text.split()))] < row["response"]["sent_at"]:
                flag("repeated_template", "same text was already sent earlier in this thread")
            if prospect and "?" in prospect:
                if row["author"] == "template":
                    flag("template_ignores_question", "scheduled template sent in reply to an open prospect question")
                elif not _stems(prospect, stopwords) & _stems(text, stopwords):
                    if words >= cfg["evasive_min_words"] and (limit is None or words > limit):
                        flag("evasive_long", f"{words}-word reply shares no key terms with the prospect's question")
                    elif not any(p in text.lower() for p in config["fact_checks"]["handoff_phrases"]):
                        flag("possibly_unanswered", "reply shares no key terms with the prospect's question")
            if prospect and any(p in prospect.lower() for p in cfg["bug_patterns"]) \
                    and any(p.lower() in text.lower() for p in cfg["upsell_patterns"]):
                flag("inappropriate_upsell", "prospect reports a problem and the reply pushes a plan change")

        own = [i for i in row["_issues"] if i["stage"] == STAGE]
        row["_quality"] = "flagged" if own else "pass"
        if not row["_issues"]:
            del row["_issues"]
        out.append(row)
    return out


def main() -> None:
    write_jsonl(DEFAULT_OUTPUT, check_all(load_records(DEFAULT_INPUT), load_config()))


if __name__ == "__main__":
    main()
