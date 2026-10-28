"""Stage 6: check replies against campaign.facts and campaign.rules.

The record's own campaign facts/rules are the only product truth. config.yaml
only says how to spot claims. Clear contradictions are severity "error";
anything the check cannot settle is "review" (never auto-guessed).

Input:  data/intermediate/05_context_validated.jsonl
Output: data/intermediate/06_fact_policy_checked.jsonl
"""

from __future__ import annotations

import re
from pathlib import Path

from pipeline.io import add_issue, load_config, load_records, write_jsonl

DEFAULT_INPUT = Path("data/intermediate/05_context_validated.jsonl")
DEFAULT_OUTPUT = Path("data/intermediate/06_fact_policy_checked.jsonl")
STAGE = "fact_validation"
AMOUNT = r"\$(\d+(?:\.\d+)?)"


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _negated(sentence: str, words: list[str]) -> bool:
    lowered = sentence.lower()
    return any(w in lowered if "'" in w else re.search(rf"\b{re.escape(w)}\b", lowered) for w in words)


def _evidence(record: dict, keyword: str) -> str:
    for text in record["campaign"]["facts"] + record["campaign"]["rules"]:
        if re.search(keyword, text, re.IGNORECASE):
            return text
    return ""


def check(record: dict, config: dict) -> dict:
    cfg = config["fact_checks"]
    row = dict(record)
    row["_issues"] = list(record.get("_issues", []))
    facts_text = "\n".join(row["campaign"]["facts"])
    text = row["response"]["text"]
    sentences = _sentences(text)
    negations = cfg["negation_words"]
    automated = row["author"] in config["automated_authors"]

    def flag(code, message, severity="error"):
        add_issue(row, STAGE, code, message, severity, _evidence(row, cfg["evidence_keywords"].get(code, code)))

    # Features the facts list as not available, claimed without negation.
    for fact in row["campaign"]["facts"]:
        if fact.startswith(cfg["not_available_prefix"]):
            items = fact[len(cfg["not_available_prefix"]):].split(".")[0]
            for item in (i.strip().lower() for i in items.split(",")):
                for sentence in sentences:
                    if item and item in sentence.lower() and not _negated(sentence, negations):
                        flag("unsupported_feature", f"reply claims '{item}' but facts list it as not available")
                        break

    # Prices: an amount absent from the facts is wrong if tied to a plan, otherwise unverified.
    fact_amounts = set(re.findall(AMOUNT, facts_text))
    plans = "|".join(cfg["plan_names"])
    for amount in dict.fromkeys(re.findall(AMOUNT, text)):
        if amount in fact_amounts:
            continue
        tied = re.search(rf"\b({plans})\b[^$]{{0,25}}\${re.escape(amount)}\b", text)
        listed = tied and re.search(rf"\b{tied.group(1)}\b\s*=\s*{AMOUNT}", facts_text)
        if listed:
            flag("wrong_price", f"{tied.group(1)} quoted at ${amount} (facts: ${listed.group(1)})")
        else:
            flag("unverified_price", f"${amount} does not appear in campaign facts", "review")

    # Discounts.
    for sentence in sentences:
        if _negated(sentence, negations):
            continue
        percents = [p for p in re.findall(cfg["percent_off_pattern"], sentence, re.IGNORECASE) if f"{p}%" not in facts_text]
        if percents:
            flag("invented_discount", f"reply offers {', '.join(p + '% off' for p in percents)}, not in facts")
        elif re.search(cfg["discount_word_pattern"], sentence, re.IGNORECASE):
            flag("discount_claim", "reply mentions a discount; check it is in facts", "review")

    # Release dates.
    for pattern in cfg["release_date_patterns"]:
        match = re.search(pattern, text)
        if match and match.group(0).lower() not in facts_text.lower():
            flag("release_date_claim", f"reply gives a date/timeline '{match.group(0)}' not in facts")
            break

    if automated:
        # Refunds are human-only; an automated reply must not grant one.
        # Clause-level negation so "No problem, I've refunded" still counts.
        for clause in re.split(r"[.!?,;:\n—]+", text):
            if re.search(cfg["refund_pattern"], clause, re.IGNORECASE) and not _negated(clause, negations) \
                    and not any(p in clause.lower() for p in cfg["handoff_phrases"]):
                flag("refund_promise", "automated reply promises or processes a refund instead of handing off")
                break
        # Opt-out: after the prospect opts out, an automated reply may confirm only.
        opted_out = any(
            m["speaker"] == "prospect" and any(p in m["text"].lower() for p in cfg["opt_out_patterns"])
            for m in row["history"]
        )
        if opted_out:
            pitched = [p for p in cfg["pitch_markers"] if p in text]
            if pitched:
                flag("opt_out_violation", f"reply after opt-out contains pitch markers: {', '.join(pitched)}")

    own = [i for i in row["_issues"] if i["stage"] == STAGE]
    row["_fact_check"] = "flagged" if any(i["severity"] == "error" for i in own) else "needs_review" if own else "pass"
    if not row["_issues"]:
        del row["_issues"]
    return row


def main() -> None:
    config = load_config()
    write_jsonl(DEFAULT_OUTPUT, [check(r, config) for r in load_records(DEFAULT_INPUT)])


if __name__ == "__main__":
    main()
