"""Stage 1: ingest JSON/JSONL without modifying the source file."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.inventory_fixture import INVENTORY_FIXTURE
from pipeline.io import load_records, sha256_file, write_jsonl

DEFAULT_SOURCE = Path("showcase/candidates-readable.json")
DEFAULT_OUTPUT = Path("data/raw/01_raw_snapshot.jsonl")
METADATA_NAME = "01_ingest_metadata.json"


def ingest(
    source: Path,
    output: Path,
    ingested_at: str | None = None,
    extra_records: list[dict] | None = None,
) -> list[dict]:
    source = Path(source)
    output = Path(output)
    checksum = sha256_file(source)
    stamp = ingested_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    extras = extra_records if extra_records is not None else [INVENTORY_FIXTURE]
    snapshot = []
    for record in load_records(source):
        row = dict(record)
        row["_source"] = {"filename": source.name, "sha256": checksum}
        snapshot.append(row)
    for record in extras:
        row = dict(record)
        row["_source"] = {"filename": "inventory_fixture", "sha256": "fixture"}
        snapshot.append(row)
    write_jsonl(output, snapshot)
    # Wall-clock time lives only in run metadata so record outputs stay reproducible (NFR-2).
    metadata = {"ingested_at": stamp, "sources": [{"filename": source.name, "sha256": checksum, "records": len(snapshot) - len(extras)}]}
    output.with_name(METADATA_NAME).write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return snapshot


def main() -> None:
    ingest(DEFAULT_SOURCE, DEFAULT_OUTPUT)


if __name__ == "__main__":
    main()
