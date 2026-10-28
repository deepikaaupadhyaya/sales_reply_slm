"""JSON / JSONL helpers. Stdlib only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"{path} JSON root is not a list")
        return data
    records = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        records.append(json.loads(line))
        if not isinstance(records[-1], dict):
            raise ValueError(f"{path}:{line_no} is not an object")
    return records


def add_issue(record: dict, stage: str, code: str, message: str, severity: str = "review", evidence: str | None = None) -> None:
    """Attach a machine-readable issue. severity: error | review | info."""
    issue = {"stage": stage, "code": code, "message": message, "severity": severity}
    if evidence:
        issue["evidence"] = evidence
    record.setdefault("_issues", []).append(issue)


def load_config(path: Path = Path("config.yaml")) -> dict:
    # config.yaml is written as JSON (a YAML subset) so stdlib can read it.
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
