# Product specification — sales_reply_check_slm

> Status: draft until Genesis records human approval. A coding agent must not implement product code until this specification is approved through Genesis.

## Problem

A sales-reply small language model needs golden examples: structurally valid, factually grounded, policy-compliant, split-safe records of a reply sent inside a conversation. Raw synthetic Quillmint conversation data is not golden data. This product is a modular Python pipeline that turns that raw dataset into reviewed golden train, validation, and test files without rewriting source data.

Unit of analysis: one sales reply (`decision_id`) inside a thread. Ground truth is conversation history, campaign rules, campaign facts, and human review.

This implementation slice stops at human review: the pipeline produces a review CSV and waits. It does not write completed golden labels or golden split files until Deepika returns the reviewed CSV.

## Users

- Dataset / ML engineer: runs the pipeline, inspects stage outputs, and collects the review CSV.
- Human reviewer (Deepika): labels and corrects rows in the review CSV.
- Future SLM trainer (downstream consumer): consumes golden files only after that review; out of scope until the CSV comes back.

## Functional requirements

- FR-1: Ingest raw JSON or JSONL without modifying source files; write `data/raw/01_raw_snapshot.jsonl` with source filename, ingestion timestamp, and a checksum of each source.
- FR-2: Validate each record against the showcase schema (required fields, types, nested `response` / `campaign` / `history` / `review`, `history` as an array, `split` in train|validation|test); write `02_schema_valid.jsonl` and `02_schema_errors.jsonl` with explicit error reasons.
- FR-3: Normalize representation without changing meaning: trim whitespace, standardize empty/missing values, keep original message text; write `03_normalized.jsonl`.
- FR-4: Detect conflicting `decision_id` values, invalid `thread_id` / `prospect_id` references, exact duplicates, and potential duplicates; write `04_deduplicated.jsonl` and `04_duplicate_report.jsonl`. Do not delete potential duplicates without documented handling.
- FR-5: Validate conversation context (`history` structure, truncated-history flags, missing or contradictory context). Flag records that need more context; do not drop a record solely because history is truncated. Write `05_context_validated.jsonl`.
- FR-6: Check the reply against `campaign.facts` and `campaign.rules`; flag invented features, prices, discounts, dates, refund/delivery promises, and opt-out violations. Ambiguous cases go to review, not auto-guess. Write `06_fact_policy_checked.jsonl`.
- FR-7: Flag irrelevant, incomplete, evasive/overlong, repeated-template, inappropriate-upsell, or unanswered-question replies with a reason per flag. Automated checks nominate review; they do not certify semantic correctness. Write `07_flagged_responses.jsonl`.
- FR-8: Export `data/review/review_queue.csv` with one row per working record for Deepika to review. Prefill `proposed_label` and `suggested_correction` only as suggestions. Leave `reviewer_label`, `reviewer_correction`, and `reviewer_rationale` empty. Do not write `08_reviewed_golden.jsonl` until the reviewed CSV is returned.
- FR-9: After human review is recorded, preserve original split assignments unless a documented reason changes them. No `thread_id` may appear in more than one of train, validation, and test after filtering. Write `09_split_validated.jsonl`. This stage waits until the CSV review is complete.
- FR-10: After human review is recorded, export only records that meet the golden-record checklist to `golden_train.jsonl`, `golden_validation.jsonl`, `golden_test.jsonl` plus `quality_report.json`. This stage waits until the CSV review is complete.
- FR-11: Each pipeline stage is a separately runnable module with documented inputs, outputs, and tests. A thin orchestrator may chain stages 1-7 plus CSV export; stages must still run alone.
- FR-12: Merge one additional synthetic test record (prospect asks about inventory; reply falsely claims Studio includes it). Fact and quality stages flag it; the review CSV proposes `factual_error` and the correction "Inventory management is not currently available in Quillmint."
- FR-13: Keep generic cleaning (parse, schema, normalize, IDs) separate from dataset-specific Quillmint facts and rules, which stay in configuration rather than hard-coded Python branches.
- FR-14: After each run through the review-CSV stop, emit metrics: input count, valid/invalid, missing-field rate, duplicates, context failures, fact/policy violations, review flags. Golden approved, excluded, and split counts wait until after review.

## Non-functional requirements

- NFR-1: Source files under `showcase/` and other originals remain byte-identical after any pipeline run.
- NFR-2: Identical inputs and configuration reproduce identical JSONL and CSV outputs (stable ordering and deterministic checks, ignoring wall-clock ingestion timestamps stored only in run metadata).
- NFR-3: Python 3.11+ stdlib first; add a third-party package only if stdlib cannot parse JSON/JSONL or write CSV/reports. No web service, database, or UI in this release.
- NFR-4: Every automated exclusion or flag includes a machine-readable reason code and human-readable message.
- NFR-5: Semantic corrections must cite campaign facts, campaign rules, or conversation history; the pipeline never invents product claims.
- NFR-6: Each stage owns one Python module and one focused test file; the orchestrator does not embed stage logic.

## Constraints

- Input schema is the showcase sales-reply record in `showcase/README.md` (decision, thread, prospect, campaign, history, response, split, flags, review).
- Default v1 input is `showcase/candidates-readable.json`.
- Domain is fully synthetic Quillmint data; no real customer data.
- Genesis governs work: one bounded implementation task per pipeline stage (FR-1 through FR-10). This slice implements through FR-8 (review CSV) and stops for Deepika.
- Trust boundary: campaign.facts and campaign.rules are the only allowed product-truth sources for automated fact checks.
- Review artifact is CSV, not a web UI and not an interactive labeling CLI.
- Do not edit shell startup files; do not overwrite Genesis kit or unrelated local files.

## Non-goals

- Training, fine-tuning, or serving the sales-reply SLM.
- A web UI, labeling app, or live human-in-the-loop server.
- Completing golden labels or golden split exports before Deepika returns the review CSV.
- Automatic deletion of suspected duplicates.
- Automatic semantic rewrite of prospect messages or AI replies during normalization.
- Tax, legal, or refund decisions by the pipeline; those stay handoff/review.
- Multi-dataset productization beyond this Quillmint showcase (keep hooks in config, do not build a plugin framework).
- Cloud storage, job queues, or distributed execution.

## Acceptance criteria

- AC-1: Running stage 1 on `showcase/candidates-readable.json` produces a raw snapshot and checksum while leaving the source file unchanged.
- AC-2: Schema-invalid records never appear in `02_schema_valid.jsonl` and each invalid record has an error reason in `02_schema_errors.jsonl`.
- AC-3: The inventory synthetic record passes schema, normalize, ID, and context stages; fact and quality stages flag it; the review CSV row proposes `factual_error` and a correction grounded in "Not available: payroll, inventory, time tracking."
- AC-4: After review, no exported golden file contains a `thread_id` that also appears in another split file.
- AC-5: After review, a second run with the same inputs and config yields byte-identical golden files and quality report (ignoring wall-clock timestamps stored only in a separate run-metadata field).
- AC-6: `python3 -m unittest` for each implemented stage exits 0.
- AC-7: Potential duplicates are listed in the duplicate report and remain in the working set until a documented rule or human decision resolves them.
- AC-8: History-truncated records are kept with a documented limitation rather than dropped by context validation alone.
- AC-9: `data/review/review_queue.csv` exists with one row per record from stage 7, empty reviewer columns, and at least the inventory fixture row.

## Risks

- Automated fact checks may miss paraphrased hallucinations; mitigation: flag uncertain matches for human review (`needs_review`) instead of auto-approving.
- Split leakage if filtering drops some thread members unevenly; mitigation: validate at thread grain in FR-9 only after review.
- Over-normalization could alter reply meaning; mitigation: never rewrite message bodies in FR-3.
- Treating unreviewed records as golden; mitigation: this slice stops at CSV review and does not export golden files.

## Open questions

- None. Default input is `showcase/candidates-readable.json`. Review is CSV for Deepika. Tests use stdlib unittest. Planted showcase mistakes are flagged when checks catch them; v1 proof is the inventory fixture plus CSV review, not a recall target.
