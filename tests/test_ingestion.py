import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.ingestion import ingest  # noqa: E402
from pipeline.inventory_fixture import INVENTORY_FIXTURE  # noqa: E402
from pipeline.io import load_records, sha256_file  # noqa: E402


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / "showcase" / "candidates-readable.json"
        self.original = self.source.read_bytes()
        self.checksum = hashlib.sha256(self.original).hexdigest()

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_snapshot_checksum_and_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "01_raw_snapshot.jsonl"
            rows = ingest(self.source, out, ingested_at="2026-10-28T00:00:00Z")
            self.assertTrue(out.exists())
            self.assertEqual(self.source.read_bytes(), self.original)
            self.assertEqual(sha256_file(self.source), self.checksum)
            loaded = load_records(out)
            self.assertEqual(len(loaded), len(rows))
            self.assertGreaterEqual(len(loaded), 82)
            self.assertEqual(loaded[0]["_source"]["filename"], "candidates-readable.json")
            self.assertEqual(loaded[0]["_source"]["sha256"], self.checksum)
            last = loaded[-1]
            self.assertEqual(last["decision_id"], INVENTORY_FIXTURE["decision_id"])
            self.assertEqual(last["_source"]["filename"], "inventory_fixture")
            self.assertEqual(last["response"]["text"], INVENTORY_FIXTURE["response"]["text"])
            metadata = json.loads((Path(tmp) / "01_ingest_metadata.json").read_text())
            self.assertEqual(metadata["ingested_at"], "2026-10-28T00:00:00Z")
            self.assertEqual(metadata["sources"][0]["sha256"], self.checksum)
            self.assertNotIn("ingested_at", loaded[0]["_source"])


if __name__ == "__main__":
    unittest.main()
