# Implementation Plan

## Overview

This roadmap converts the architecture into a step-by-step build sequence that can be followed in Anti-Gravity IDE with Ponytail. Each milestone is designed to reduce refactoring and ensure the submission remains runnable and deterministic.

## Module-by-Module Roadmap

### 1. Project bootstrap and runtime config

- **Development milestone:** establish a reliable startup path and runtime configuration layer.
- **Files:** `src/configs/settings.py`, `src/configs/paths.py`, `src/utils/logging.py`, `src/utils/types.py`, `code/main.py`, `code/README.md`, `code/requirements.txt`
- **Acceptance criteria:** the app resolves dataset and output paths, configuration loads deterministically, and startup fails fast on invalid paths.
- **Unit tests:** config path resolution, environment override parsing, missing-file handling, smoke test for bootstrap.
- **Dependencies:** none.
- **Common mistakes:** hardcoded absolute paths, mixing dev and submission paths, skipping config validation.

### 2. Dataset loader and schema validator

- **Development milestone:** load all CSVs safely and validate required columns and references.
- **Files:** `src/loader/csv_loader.py`, `src/loader/schema_validator.py`, `src/loader/normalizer.py`, `src/utils/file_io.py`
- **Acceptance criteria:** all participant-facing datasets load without mutation; required columns and identifiers are validated.
- **Unit tests:** valid CSV load, missing-column failure, malformed timestamp failure, duplicate ID failure, media path normalization.
- **Dependencies:** Module 1.
- **Common mistakes:** silent type coercion, mutating the raw dataset, ignoring referential integrity.

### 3. Core domain models and shared data contracts

- **Development milestone:** define canonical internal objects used by all later modules.
- **Files:** `src/models/message.py`, `src/models/context.py`, `src/models/evidence.py`, `src/models/prediction.py`
- **Acceptance criteria:** every module consumes the same stable internal shapes.
- **Unit tests:** serialization/deserialization, required fields, default-value behavior.
- **Dependencies:** Modules 1–2.
- **Common mistakes:** multiple ad hoc schemas, raw dictionaries everywhere, ambiguous optional fields.

### 4. User context builder

- **Development milestone:** compute per-recipient behavioral and preference signals.
- **Files:** `src/context/user_context.py`, `src/context/user_aggregates.py`
- **Acceptance criteria:** each user has a stable profile including notification load, engagement, dismissal/report rates, quiet hours, and business preference signals.
- **Unit tests:** aggregate calculations, quiet-hour overlap logic, sparse-history fallback, opt-out handling.
- **Dependencies:** Modules 1–3.
- **Common mistakes:** using global averages, double-counting history, overfitting to a single recent event.

### 5. Conversation context builder

- **Development milestone:** compute sender, group, and business trust context.
- **Files:** `src/context/conversation_context.py`, `src/context/group_context.py`, `src/context/business_context.py`
- **Acceptance criteria:** the app can distinguish personal, group, and business conversations and derive trust/mute/verification signals.
- **Unit tests:** group admin vs member handling, muted-group behavior, verified vs unverified business logic, unknown-sender fallback.
- **Dependencies:** Modules 1–3.
- **Common mistakes:** treating all groups the same, ignoring business opt-out state, failing to preserve conversation-type-specific rules.

### 6. Evidence index and retrieval

- **Development milestone:** retrieve relevant historical message IDs for each incoming row.
- **Files:** `src/retrieval/index.py`, `src/retrieval/ranker.py`, `src/retrieval/evidence_selector.py`
- **Acceptance criteria:** the system returns ranked evidence candidates with deterministic ordering and `none` when no useful history exists.
- **Unit tests:** same-sender retrieval, same-group retrieval, same-business retrieval, recency ranking, evidence suppression when irrelevant.
- **Dependencies:** Modules 1–5.
- **Common mistakes:** choosing evidence only by lexical similarity, returning noisy IDs, ignoring events and historical outcomes.

### 7. Text understanding

- **Development milestone:** classify text-only messages and extract routing clues from message text.
- **Files:** `src/multimodal/text_features.py`, `src/multimodal/text_rules.py`, `src/multimodal/text_classifier.py`
- **Acceptance criteria:** text cues for urgent, payment, business_update, promotion, greeting, spam, scam, forward, and unknown are extracted consistently.
- **Unit tests:** scam keyword detection, payment reminder detection, promotion detection, forward-chain handling, ambiguous-text fallback.
- **Dependencies:** Modules 1–6.
- **Common mistakes:** over-relying on keyword matches, missing negative cues like OTP or suspicious domains, collapsing short text into unknown.

### 8. Image processing

- **Development milestone:** convert image messages into OCR text and visual labels.
- **Files:** `src/multimodal/image_ocr.py`, `src/multimodal/image_classifier.py`, `src/multimodal/image_preprocess.py`
- **Acceptance criteria:** image messages produce OCR text when possible, plus a usable fallback label when OCR fails.
- **Unit tests:** image path resolution, OCR success case, OCR failure fallback, poster-like text classification.
- **Dependencies:** Modules 1–7.
- **Common mistakes:** treating images as opaque attachments, failing to cache OCR, depending on perfect OCR.

### 9. Voice processing

- **Development milestone:** transcribe voice notes and convert them into the same feature space as text.
- **Files:** `src/multimodal/voice_asr.py`, `src/multimodal/voice_features.py`
- **Acceptance criteria:** voice notes produce a transcript or a graceful low-confidence fallback.
- **Unit tests:** voice path resolution, transcript extraction, empty-audio fallback, transcript-based intent classification.
- **Dependencies:** Modules 1–8.
- **Common mistakes:** skipping transcription entirely, not caching ASR output, treating ASR failure as a hard error.

### 10. Routing scorer

- **Development milestone:** choose `notify`, `digest`, or `mute` and assign `message_type`.
- **Files:** `src/routing/scorer.py`, `src/routing/decision_rules.py`, `src/routing/thresholds.py`
- **Acceptance criteria:** routing is deterministic, personalized, safety-aware, and stable across supported inputs.
- **Unit tests:** urgent notify cases, safe digest cases, mute cases, scam overrides, personalized business opt-in vs opt-out behavior.
- **Dependencies:** Modules 1–9.
- **Common mistakes:** mixing explanation generation into scoring, using one threshold for all users, allowing risky content to be digested.

### 11. Reason and confidence builder

- **Development milestone:** convert internal signals into a short explanation and calibrated confidence.
- **Files:** `src/output/reason_builder.py`, `src/output/confidence.py`
- **Acceptance criteria:** every prediction has a concise reason, a numeric confidence in range, and evidence IDs that match the decision.
- **Unit tests:** confidence range checks, high-confidence obvious case, low-confidence ambiguous case, evidence-linked reason text.
- **Dependencies:** Modules 1–10.
- **Common mistakes:** fabricating reasons unrelated to the evidence, using a constant confidence, overconfident outputs for weak signals.

### 12. Batch runner and output writer

- **Development milestone:** run the full pipeline over `messages.csv` and write a valid submission CSV.
- **Files:** `code/main.py`, `src/output/writer.py`, `src/pipeline/run_batch.py`, `code/evaluation/main.py`, `code/README.md`
- **Acceptance criteria:** exactly one row per `message_id`, exact required columns, stable ordering, valid CSV, runnable from terminal.
- **Unit tests:** row-count alignment, column order, duplicate detection, output schema validation, end-to-end smoke test on sample rows.
- **Dependencies:** Modules 1–11.
- **Common mistakes:** writing partial outputs, dropping messages, changing column order, depending on state outside the package.

## Milestones

1. Bootstrap and configuration
2. Dataset validation and shared models
3. User and conversation context
4. Evidence retrieval
5. Multimodal understanding
6. Routing and confidence
7. Output writing and packaging
8. End-to-end validation

## Unit Testing Strategy

- Validate each module independently before integration.
- Favor deterministic fixtures over large integration dependencies.
- Add regression tests for sample rows from `dataset/sample_messages.csv`.
- Verify `output.csv` schema and row count before submission.
- Run end-to-end smoke tests after each major module.

## Common Implementation Mistakes

- Introducing hidden dependencies on files outside `dataset/`.
- Letting the output writer or scorer make up missing evidence.
- Treating multimodal data as optional when the task depends on it.
- Calibrating confidence too aggressively.
- Hardcoding paths or labels.
- Waiting until the end to add tests.

## Dependencies Between Modules

- Bootstrap first.
- Then loader and schemas.
- Then shared models.
- Then user and conversation context.
- Then retrieval.
- Then multimodal processors.
- Then routing and confidence.
- Then output and packaging.
