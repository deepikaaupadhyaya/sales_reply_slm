"""Stage 2: split records into schema-valid and schema-invalid with reasons.

Input:  data/raw/01_raw_snapshot.jsonl
Output: data/intermediate/02_schema_valid.jsonl, data/intermediate/02_schema_errors.jsonl
"""

from __future__ import annotations

from pathlib import Path

from pipeline.io import load_records, write_jsonl

DEFAULT_INPUT = Path("data/raw/01_raw_snapshot.jsonl")
VALID_OUTPUT = Path("data/intermediate/02_schema_valid.jsonl")
ERRORS_OUTPUT = Path("data/intermediate/02_schema_errors.jsonl")

STR_FIELDS = ["decision_id", "thread_id", "prospect_id", "campaign_id", "campaign_name", "channel", "trigger", "author", "split"]
MESSAGE_FIELDS = {"msg_id": str, "sent_at": str, "text": str}
SPLITS = {"train", "validation", "test"}


def _missing_or_type(errors, obj, field, kind, where):
    if field not in obj or obj[field] is None:
        errors.append({"code": "missing_field", "message": f"{where}{field} is missing"})
    elif not isinstance(obj[field], kind):
        errors.append({"code": "wrong_type", "message": f"{where}{field} must be {kind.__name__}"})


def validate(record) -> list[dict]:
    if not isinstance(record, dict):
        return [{"code": "not_an_object", "message": "record is not a JSON object"}]
    errors: list[dict] = []
    for field in STR_FIELDS:
        _missing_or_type(errors, record, field, str, "")
    for field, kind in [("history", list), ("response", dict), ("campaign", dict), ("flags", list), ("review", dict)]:
        _missing_or_type(errors, record, field, kind, "")

    if isinstance(record.get("split"), str) and record["split"].strip().lower() not in SPLITS:
        errors.append({"code": "invalid_split", "message": f"split {record['split']!r} not in train|validation|test"})
    if isinstance(record.get("response"), dict):
        for field, kind in MESSAGE_FIELDS.items():
            _missing_or_type(errors, record["response"], field, kind, "response.")
    if isinstance(record.get("history"), list):
        for i, message in enumerate(record["history"]):
            if not isinstance(message, dict):
                errors.append({"code": "wrong_type", "message": f"history[{i}] must be dict"})
                continue
            for field, kind in {**MESSAGE_FIELDS, "speaker": str}.items():
                _missing_or_type(errors, message, field, kind, f"history[{i}].")
    if isinstance(record.get("campaign"), dict):
        _missing_or_type(errors, record["campaign"], "objective", str, "campaign.")
        for field in ("rules", "facts"):
            _missing_or_type(errors, record["campaign"], field, list, "campaign.")
            if isinstance(record["campaign"].get(field), list) and not all(isinstance(x, str) for x in record["campaign"][field]):
                errors.append({"code": "wrong_type", "message": f"campaign.{field} must contain strings"})
    if isinstance(record.get("review"), dict):
        _missing_or_type(errors, record["review"], "status", str, "review.")
    return errors


def split_valid(records: list) -> tuple[list[dict], list[dict]]:
    valid, invalid = [], []
    for index, record in enumerate(records):
        errors = validate(record)
        if errors:
            invalid.append({"index": index, "decision_id": record.get("decision_id") if isinstance(record, dict) else None, "errors": errors, "record": record})
        else:
            valid.append(record)
    return valid, invalid


def main() -> None:
    valid, invalid = split_valid(load_records(DEFAULT_INPUT))
    write_jsonl(VALID_OUTPUT, valid)
    write_jsonl(ERRORS_OUTPUT, invalid)


if __name__ == "__main__":
    main()
