# Final Blueprint

This document combines the architecture, engineering decisions, implementation roadmap, repository structure, and evaluation strategy into a single build specification for the Message Notification Router.

## 1. Problem Statement

Build a WhatsApp message router that decides, for each incoming message, whether to:

- `notify`
- `digest`
- `mute`

The decision must be personalized, multimodal, evidence-backed, reproducible, and compatible with the required `output.csv` submission format.

## 2. Design Goals

- Preserve deterministic behavior where possible.
- Support text, image, and voice-note messages.
- Personalize routing using user and conversation history.
- Produce relevant evidence IDs.
- Calibrate confidence honestly.
- Keep the system modular and easy to validate.
- Keep dataset files untouched.
- Make the submission package self-contained.

## 3. System Architecture

The system consists of these layers:

1. Ingestion and schema validation
2. User context assembly
3. Conversation context assembly
4. Multimodal understanding
5. Evidence retrieval
6. Routing decision engine
7. Reason and confidence generation
8. Output writing
9. Logging, caching, configuration, and testing support

## 4. Component Blueprint

### 4.1 Ingestion and validation

- Load all participant-facing datasets.
- Validate required columns and identifiers.
- Normalize timestamps and media paths.
- Fail fast on malformed inputs.

### 4.2 User context

- Build per-user notification behavior summaries.
- Include quiet hours, engagement, dismissals, reports, and business preferences.

### 4.3 Conversation context

- Identify personal, group, and business conversations.
- Derive trust, mute state, verification status, and relationship strength.

### 4.4 Multimodal understanding

- Parse text directly.
- OCR images.
- Transcribe voice notes.
- Convert all modalities into feature bundles.

### 4.5 Evidence retrieval

- Find historical message IDs from similar and relevant past interactions.
- Rank evidence using recency, similarity, and outcome relevance.

### 4.6 Routing decision engine

- Decide `notify`, `digest`, or `mute`.
- Assign the best `message_type`.
- Apply safety overrides for risky content.

### 4.7 Reason and confidence generation

- Generate short explanations based on internal signals.
- Produce calibrated confidence values.
- Emit evidence IDs.

### 4.8 Output writing

- Write exactly one row per incoming message.
- Preserve the exact required column order.
- Ensure the output file is valid for submission.

## 5. End-to-End Pipeline

1. Read one row from `dataset/messages.csv`.
2. Validate and normalize the row.
3. Build user context.
4. Build conversation context.
5. Process any text, image, or voice content.
6. Retrieve evidence.
7. Score the routing decision.
8. Generate reason and confidence.
9. Write the final output row.
10. Repeat for all messages.

## 6. Engineering Decisions

- Develop in `src/` and package into `code/` later.
- Use a hybrid deterministic architecture.
- Use retrieval for evidence support.
- Use OCR and ASR before routing multimodal messages.
- Use score-margin-based confidence calibration.
- Use templated reasons instead of free-form generation.
- Keep `code/` self-contained at submission time.

## 7. Implementation Plan

Build in this order:

1. Project bootstrap and runtime config
2. Dataset loader and schema validator
3. Core domain models
4. User context builder
5. Conversation context builder
6. Evidence index and retrieval
7. Text understanding
8. Image processing
9. Voice processing
10. Routing scorer
11. Reason and confidence builder
12. Batch runner and output writer

Each module should be fully tested before the next one begins.

## 8. Repository Structure

- `dataset/`: read-only inputs
- `docs/`: canonical design docs
- `src/`: development source of truth
- `code/`: self-contained submission package

The final `code` package should contain:

- `main.py`
- `README.md`
- `requirements.txt`
- `evaluation/`
- `src/`
- `cache/`
- `logs/`
- `outputs/`
- `scripts/`

## 9. Evaluation Strategy

The evaluator will likely care about:

- Routing accuracy
- Message type accuracy
- Evidence relevance
- Confidence calibration
- Personalization
- Multimodal reasoning
- Output formatting
- Reproducibility
- Packaging correctness

## 10. Risks and Mitigations

- Use conservative fallbacks when OCR or ASR fails.
- Use explicit safety rules for scam-like content.
- Validate output before writing.
- Cache expensive intermediate results.
- Keep the final bundle independent from the workspace root.

## 11. Canonical Workflow

1. Develop in `src/`.
2. Test each module independently.
3. Validate the end-to-end pipeline.
4. Sync into `code/`.
5. Verify the packaged submission.
6. Produce `output.csv`.

## 12. Final Notes

This blueprint intentionally preserves only the decisions already discussed. Any future change should be treated as an explicit recommendation, not as an implied architectural assumption.
