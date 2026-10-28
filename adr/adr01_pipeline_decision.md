# Sales Conversation Data Cleaning Pipeline: Raw to Golden Data

## 1. Project Overview

### Objective
Build a modular data cleaning pipeline that transforms raw sales conversation data into high-quality, validated, and human-reviewed golden data suitable for training and evaluating AI sales agents.

### Dataset Context
- **Domain:** Sales conversations
- **Product:** Quillmint (fictional invoicing and expense management application)
- **Input format:** JSONL / JSON
- **Unit of analysis:** A sales reply sent within a conversation thread
- **Ground truth sources:**
  - Conversation history
  - Campaign rules and objectives
  - Campaign facts
  - Human-reviewed labels and corrections

### Core Principle
**Clean data is not necessarily golden data.** Golden data must be structurally valid, factually grounded, contextually correct, policy-compliant, and reviewed.

---

## 2. Pipeline Architecture

```text
Raw Dataset
    |
    v
1. Raw Data Ingestion
    |
    v
2. Schema Validation
    |
    v
3. Data Normalization
    |
    v
4. ID and Duplicate Validation
    |
    v
5. Conversation Context Validation
    |
    v
6. Fact and Policy Validation
    |
    v
7. Response Quality Checks
    |
    v
8. Golden Labeling and Human Review
    |
    v
9. Train / Validation / Test Split Validation
    |
    v
10. Quality Gates and Export
    |
    v
Golden Dataset
```

---

## 3. Pipeline Modules

### Step 1: Raw Data Ingestion

**Objective:** Load the original dataset without modifying its contents.

**Tasks:**
- Read JSON and JSONL files.
- Verify that files can be parsed.
- Record the source filename and ingestion timestamp.
- Preserve the original data.
- Generate a checksum to track source changes.

**Input:**
- Original dataset files.

**Output:**
- `data/raw/`
- `01_raw_snapshot.jsonl`

**Validation:**
- Source files are readable.
- Every record can be traced back to its source.

---

### Step 2: Schema Validation

**Objective:** Ensure each record follows the expected data structure.

**Tasks:**
- Check required fields.
- Validate field types.
- Validate nested objects such as `response`, `campaign`, `history`, and `review`.
- Check that `history` is an array.
- Check that `split` contains an allowed value.
- Separate invalid records from valid records.

**Input:**
- `01_raw_snapshot.jsonl`

**Output:**
- `02_schema_valid.jsonl`
- `02_schema_errors.jsonl`

**Validation:**
- Required fields exist.
- Field types are correct.
- Invalid records have explicit error reasons.

---

### Step 3: Data Normalization

**Objective:** Standardize data representation without changing its meaning.

**Tasks:**
- Trim unnecessary whitespace.
- Standardize empty and missing values.
- Normalize string formats where appropriate.
- Standardize timestamps and field representations if applicable.
- Preserve the original text of messages.
- Avoid rewriting prospect messages or AI responses during normalization.

**Input:**
- `02_schema_valid.jsonl`

**Output:**
- `03_normalized.jsonl`

**Validation:**
- Normalized values follow consistent conventions.
- Original message meaning is preserved.

---

### Step 4: ID and Duplicate Validation

**Objective:** Detect duplicate records and identifier inconsistencies.

**Tasks:**
- Check uniqueness of `decision_id`.
- Validate references to `thread_id` and `prospect_id`.
- Detect exact duplicate records.
- Detect potential duplicates using thread IDs, response text, timestamps, or other available fields.
- Generate a duplicate report.
- Avoid deleting potential duplicates automatically without verification.

**Input:**
- `03_normalized.jsonl`

**Output:**
- `04_deduplicated.jsonl`
- `04_duplicate_report.jsonl`

**Validation:**
- No conflicting decision IDs.
- Duplicate handling is documented and traceable.

---

### Step 5: Conversation Context Validation

**Objective:** Ensure every sales reply has sufficient context for evaluation.

**Tasks:**
- Validate the structure of `history`.
- Check whether the current response matches the conversation context.
- Inspect `history_truncated` when available.
- Identify missing or contradictory conversation details.
- Flag records that require additional context.
- Do not automatically discard records solely because their history is truncated.

**Input:**
- `04_deduplicated.jsonl`

**Output:**
- `05_context_validated.jsonl`

**Validation:**
- Conversation context is available or the limitation is documented.
- Context-dependent decisions are not made from unsupported assumptions.

---

### Step 6: Fact and Policy Validation

**Objective:** Verify sales responses against authoritative campaign information.

**Tasks:**
- Use `campaign.facts` as the source of truth for product claims.
- Use `campaign.rules` to validate sales policies and response constraints.
- Detect invented features, prices, discounts, and release dates.
- Detect unsupported refund or delivery promises.
- Detect responses that violate unsubscribe or opt-out instructions.
- Flag ambiguous cases for review.

**Input:**
- `05_context_validated.jsonl`

**Output:**
- `06_fact_policy_checked.jsonl`

**Validation:**
- Product claims are supported by authoritative facts.
- Responses comply with campaign rules.
- Uncertain cases are flagged instead of guessed.

---

### Step 7: Response Quality Checks

**Objective:** Identify responses that are incorrect, irrelevant, or unsuitable for the conversation.

**Tasks:**
- Detect irrelevant responses.
- Detect incomplete answers.
- Detect excessively long or evasive responses.
- Detect repeated template messages.
- Detect inappropriate upselling.
- Detect responses that fail to address the prospect's question.
- Record the reason for each flagged response.

**Input:**
- `06_fact_policy_checked.jsonl`

**Output:**
- `07_flagged_responses.jsonl`

**Validation:**
- Every flagged record has a reason.
- Automated checks identify candidates for review rather than automatically asserting semantic correctness.

---

### Step 8: Golden Labeling and Human Review

**Objective:** Turn validated records into reliable reference examples.

**Tasks:**
- Assign a quality label to each record.
- Identify the specific error, if present.
- Provide a corrected response when necessary.
- Preserve the original response.
- Record the reviewer decision and rationale.
- Mark unresolved records for further review.

**Proposed labels:**
- `correct`
- `factual_error`
- `policy_violation`
- `irrelevant`
- `incomplete`
- `duplicate`
- `needs_review`

**Input:**
- `07_flagged_responses.jsonl`

**Output:**
- `08_reviewed_golden.jsonl`

**Validation:**
- Golden records have an approved label.
- Incorrect responses have an appropriate correction.
- Corrections are grounded in conversation context, campaign facts, and campaign rules.
- Review status and provenance are preserved.

---

### Step 9: Train / Validation / Test Split Validation

**Objective:** Prevent data leakage between dataset splits.

**Tasks:**
- Preserve the original split assignments unless there is a documented reason to change them.
- Ensure records belonging to the same `thread_id` do not appear across different splits.
- Verify split membership after filtering and deduplication.
- Ensure evaluation records are not used to guide training corrections.
- Document any excluded records.

**Input:**
- `08_reviewed_golden.jsonl`

**Output:**
- `09_split_validated.jsonl`

**Validation:**
- No conversation thread leaks across splits.
- Split assignments remain traceable to the source dataset.

---

### Step 10: Quality Gates and Export

**Objective:** Export only records that satisfy the defined golden-data criteria.

**Tasks:**
- Check schema validity.
- Check identifier consistency.
- Check duplicate handling.
- Check fact and policy validation results.
- Check review status.
- Check split integrity.
- Generate a pipeline quality report.
- Export approved datasets.

**Output:**
- `golden_train.jsonl`
- `golden_validation.jsonl`
- `golden_test.jsonl`
- `quality_report.json`

**Validation:**
- Every exported record satisfies the defined acceptance criteria.
- Excluded records have documented reasons.
- Output files are reproducible from the preserved source data.

---

## 4. Golden Record Definition

A record qualifies as golden data when it satisfies the following criteria:

- [ ] Schema is valid.
- [ ] Required fields are present.
- [ ] IDs are consistent and non-conflicting.
- [ ] Duplicate status is resolved.
- [ ] Conversation context is sufficient, or an approved exception is documented.
- [ ] Product claims are grounded in campaign facts.
- [ ] Response follows campaign rules.
- [ ] Quality label is assigned.
- [ ] Correction is provided when required.
- [ ] Human review is complete where required.
- [ ] Train / validation / test assignment is valid.
- [ ] Original data and transformation history remain traceable.

---

## 5. Additional Synthetic Test Record

Use this record to test the pipeline independently of the original dataset.

### Scenario
A prospect asks whether Quillmint supports inventory management. The response incorrectly claims that inventory is included in the Studio plan, while the campaign facts state that inventory management is unavailable.

### Expected Pipeline Behavior
- Schema validation: Pass
- Normalization: Pass
- ID validation: Pass
- Context validation: Pass
- Fact validation: Flag unsupported feature claim
- Quality checks: Flag factual error
- Golden labeling: Assign `factual_error`
- Correction: Provide a factually supported response
- Final review: Require approval before golden export

### Expected Correction

> Inventory management is not currently available in Quillmint.

The test record should include the full required dataset schema and should be merged with its review metadata rather than replacing the original record.

---

## 6. Proposed Project Structure

```text
sales-data-pipeline/
├── data/
│   ├── raw/
│   ├── intermediate/
│   ├── review/
│   └── golden/
│       ├── golden_train.jsonl
│       ├── golden_validation.jsonl
│       └── golden_test.jsonl
├── reports/
│   ├── schema_errors.json
│   ├── duplicate_report.json
│   └── quality_report.json
├── src/
│   └── pipeline/
│       ├── ingestion.py
│       ├── schema_validation.py
│       ├── normalization.py
│       ├── deduplication.py
│       ├── context_validation.py
│       ├── fact_validation.py
│       ├── quality_checks.py
│       ├── labeling.py
│       ├── split_validation.py
│       ├── export.py
│       └── pipeline.py
├── tests/
│   ├── test_schema_validation.py
│   ├── test_normalization.py
│   ├── test_deduplication.py
│   ├── test_fact_validation.py
│   └── test_pipeline.py
├── config.yaml
├── requirements.txt
└── DATA_CLEANING_PIPELINE.md
```

---

## 7. Implementation Strategy

Implement the pipeline incrementally:

1. Load the dataset and preserve a raw snapshot.
2. Build schema validation and error reporting.
3. Add normalization and duplicate detection.
4. Add conversation-context validation.
5. Add fact and policy checks using campaign data.
6. Add response-quality flags.
7. Create a human-review workflow for labels and corrections.
8. Add split-integrity checks.
9. Export golden datasets and a quality report.
10. Add automated tests for each module.

### Design Principle

Keep **generic data-cleaning logic** separate from **dataset-specific business rules**. For example, JSON parsing and schema checks can be reused across datasets, while Quillmint product facts and sales policies should remain configurable.

---

## 8. Metrics to Track

Track these metrics after each pipeline run:

- Total input records
- Valid and invalid records
- Missing-field rate
- Duplicate-record count
- Context-validation failure count
- Fact and policy violation count
- Records flagged for human review
- Golden records approved
- Records excluded from golden export
- Train / validation / test counts
- Cross-split thread leakage count

---

## 9. Definition of Done

The pipeline is complete when:

- [ ] Each stage runs independently.
- [ ] Each stage has documented inputs and outputs.
- [ ] Each stage has automated tests.
- [ ] Errors and exclusions are reported with reasons.
- [ ] The original dataset remains unchanged.
- [ ] Semantic corrections are traceable to authoritative sources.
- [ ] Human review is supported for ambiguous cases.
- [ ] Thread-level data leakage is prevented.
- [ ] Golden exports meet all acceptance criteria.
- [ ] The same inputs and configuration reproduce the same outputs.
