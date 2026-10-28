# sales_reply_slm

This project is a data-cleaning pipeline. It turns raw sales-reply conversations into a **golden dataset** (records checked by the pipeline and reviewed by a human) for training a small language model (SLM) that judges and corrects sales replies.

Clean data is not golden data. A record counts as golden only when all of these hold:
- it passes the schema
- its IDs are consistent
- it's grounded in the campaign's facts and rules
- it has been reviewed by a person
- its conversation thread stays inside one train/validation/test split

The pipeline has 10 stages. The automated stages flag problems; a human makes the final call.

The data is a fully synthetic dataset for **Quillmint**, an invented invoicing app, described in [showcase/README.md](showcase/README.md).

## Results

| | Records |
|---|---|
| Input (81 showcase + 1 synthetic test record) | 82 |
| Golden records exported | **80** (train 62 · validation 8 · test 10) |
| Excluded: reviewer left them unresolved (`needs_review`) | 2 |
| Thread leakage between splits | none |

The automated checks flagged all 10 planted mistakes in the showcase data, plus the synthetic inventory record, and wrongly flagged none of the human-written replies as errors:

| Planted mistake | Caught by stage | Final label |
|---|---|---|
| Wrong price ($24 instead of $27) | Fact and policy checks | `factual_error` |
| Invented feature (payroll) | Fact and policy checks | `factual_error` |
| Invented release date ("April") | Fact and policy checks | `factual_error` |
| Two invented discounts (30%, 50%) | Fact and policy checks | `factual_error` |
| Refund promised instead of handed off | Fact and policy checks | `policy_violation` |
| Sales pitch after an unsubscribe request | Fact and policy checks | `policy_violation` |
| Long reply that dodges the question | Response quality checks | `irrelevant` |
| Template sent twice | ID and duplicate checks, response quality checks | `duplicate` |
| Upgrade pushed for a bug | Response quality checks | `policy_violation` |

Full counts are in [reports/quality_report.json](reports/quality_report.json).

## Pipeline

Each stage has one module in `src/pipeline/` and one test file in `tests/`, and each can run on its own.

| # | Stage | Module | Output |
|---|---|---|---|
| 1 | Ingestion: load the source, record its checksum, add the synthetic test record | `ingestion.py` | `data/raw/01_raw_snapshot.jsonl` |
| 2 | Schema validation | `schema_validation.py` | `02_schema_valid.jsonl`, `02_schema_errors.jsonl` |
| 3 | Normalization (message text is never changed) | `normalization.py` | `03_normalized.jsonl` |
| 4 | ID and duplicate checks (duplicates are reported, not deleted) | `deduplication.py` | `04_deduplicated.jsonl`, `04_duplicate_report.jsonl` |
| 5 | Conversation context checks (truncated history is kept and noted) | `context_validation.py` | `05_context_validated.jsonl` |
| 6 | Fact and policy checks against each record's campaign facts and rules | `fact_validation.py` | `06_fact_policy_checked.jsonl` |
| 7 | Response quality checks (flag records for review, never certify them) | `quality_checks.py` | `07_flagged_responses.jsonl` |
| 8 | Human review: export a CSV, **stop**, then merge the reviewed CSV back | `labeling.py` | `data/review/review_queue.csv`, `08_reviewed_golden.jsonl` |
| 9 | Split validation (no thread in two splits) | `split_validation.py` | `09_split_validated.jsonl` |
| 10 | Golden export and quality report | `export.py` | `data/golden/golden_*.jsonl`, `reports/quality_report.json` |

`pipeline.py` runs stages 1–8 in one go and stops when the review CSV is written. Files from stages 2–9 go in `data/intermediate/`.

## Quick start

You need Python 3.11+. The pipeline uses only the standard library, so there's nothing to install.

Run everything from the repository root:

```bash
# Stages 1–8: writes data/review/review_queue.csv, then stops for human review
PYTHONPATH=src python3 -m pipeline.pipeline

# After review: merge the reviewed CSV, validate splits, export golden files
PYTHONPATH=src python3 -m pipeline.labeling --merge data/review/review_queue_reviewed.csv --reviewer "Your Name"
PYTHONPATH=src python3 -m pipeline.split_validation
PYTHONPATH=src python3 -m pipeline.export

# Tests
python3 -m unittest discover -s tests -t .
```

Any single stage also runs on its own, for example `PYTHONPATH=src python3 -m pipeline.fact_validation`. It reads the previous stage's file.

## Human review

The review CSV has one row per record, with the rows that have problems listed first.

| Column | What it holds |
|---|---|
| `last_prospect_message`, `response_text` | The conversation turn being judged |
| `issue_codes`, `issue_messages`, `evidence` | What the checks found, and the fact or rule text behind each finding |
| `later_human_reply` | The next human reply in the same thread, which often contains the real correction |
| `proposed_label`, `suggested_correction` | Suggestions only. Corrections are filled in only where they can be built word for word from the facts |
| `reviewer_label`, `reviewer_correction`, `reviewer_rationale` | Left empty for the reviewer to fill in |

Labels: `correct`, `factual_error`, `policy_violation`, `irrelevant`, `incomplete`, `duplicate`, `needs_review`.

The merge step refuses the CSV, rather than merging part of it, if rows are missing or extra, a label is invalid, or the reply text was edited.

## Design decisions

- **Source data is read-only.** Files in `showcase/` stay byte-identical, and the tests check this.
- **Product truth comes only from each record's `campaign.facts` and `campaign.rules`.** [config.yaml](config.yaml) holds Quillmint-specific settings for *how* to detect claims, not *what* is true. It's written as JSON, which YAML parsers also accept, so the standard library can read it.
- **Flags are not verdicts.** Every flag carries a machine-readable code and a message. Uncertain cases go to review instead of being guessed.
- **Reproducible.** The same input and config produce byte-identical outputs. The only wall-clock timestamp lives in `01_ingest_metadata.json`.
- **Splits are kept, not reassigned.** A thread that appears in two splits is excluded and the reason is recorded.

The architecture comes from [adr/adr01_pipeline_decision.md](adr/adr01_pipeline_decision.md). Requirements (FR-\*, NFR-\*, AC-\*) are in [SPEC.md](SPEC.md).

## Project structure

```text
├── adr/                  Architecture decision record
├── config.yaml           Quillmint-specific check settings
├── data/
│   ├── review/           Review CSV (as exported, and as reviewed)
│   └── golden/           Golden train / validation / test files
├── reports/              quality_report.json
├── showcase/             Source dataset (read-only)
├── src/pipeline/         One module per stage, plus the runner (pipeline.py)
├── tests/                One test file per stage
├── SPEC.md               Requirements and acceptance criteria
└── .genesis/             Genesis plan, approvals and test proof
```

`data/raw/` and `data/intermediate/` aren't committed; the pipeline regenerates them.

## Known limitations

- **The validation split has no error examples.** All 8 validation records are labeled `correct`, so validation can't measure error detection yet. Two error types (`irrelevant` and `duplicate`) have only one example each in the whole dataset.
- **The checks match words, not meaning.** They can miss a reworded false claim and can flag a correct answer that uses different words. Replies in Portuguese and Spanish aren't recognised as handoffs to the team.

## How this was built

Development followed the [Genesis](https://github.com/ayush488-glitch/genesis-kit) workflow:
1. The spec was written and approved first.
2. The plan was approved, with one task per pipeline stage.
3. Each task had to pass its own test command before it could be marked complete.
4. The medium-risk tasks also needed a human reviewer's sign-off.

The approvals and test proof are in `.genesis/`.

## License

The code is under the [Apache License 2.0](LICENSE). The synthetic showcase dataset is free to use under MIT, as stated in [showcase/README.md](showcase/README.md).
