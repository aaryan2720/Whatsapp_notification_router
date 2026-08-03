# System Evaluation & Testing

The Message Notification Router has a comprehensive test suite to ensure correctness, reliability, determinism, and schema conformity.

---

## 1. Regression Test Suite

The test suite contains **191 unit and integration tests** executing in `< 1.5 seconds` on standard environments.

### Test Coverage Breakdown

| Module | Test File | Coverage Focus |
|---|---|---|
| **Module 1** | `test_module1_bootstrap.py` | Config initialization, directory creations, validation paths. |
| **Module 2** | `test_module2_loader.py` | CSV parsing, RFC 4180 parsing, schema type validation. |
| **Module 3** | `test_module3_models.py` | Domain object comparisons, immutability checks, serialization. |
| **Module 4** | `test_module4_user_context.py` | DND calculations, user opt-outs, fallback global averages. |
| **Module 5** | `test_module5_conversation_context.py` | Trusted sender calculations, phishing domain matches, group metadata. |
| **Module 6** | `test_module6_retrieval.py` | Evidence filtering, recency decays, Jaccard rankings. |
| **Module 7** | `test_module7_text_features.py` | Lexical statistics, domain parsing, keyword triggers, OTP codes. |
| **Module 8** | `test_module8_multimodal.py` | Image metadata parsing, OCR fallback caches, aspect classifications. |
| **Module 9** | `test_module9_voice.py` | ASR transcript mapping, duration calculations, fallback providers. |
| **Module 10** | `test_module10_routing.py` | Scorer priority fusion, decision matrix override validations. |
| **Module 11** | `test_module11_output.py` | Natural reason templating, confidence rounding, evidence cleaning. |
| **Module 12** | `test_module12_batch.py` | CLI execution paths, output schema validator, sandbox isolation. |

---

## 2. Integrated Schema Validator

A post-write execution checker (`src/output/submission_validator.py`) inspects output predictions, guaranteeing compliance with production submission contracts:

*   **Row Matching**: Exactly 110 predictions written matching the exact sequence of `messages.csv`.
*   **Unique Keys**: No skipped rows or duplicate prediction targets.
*   **Column Headers**: Verifies columns exist in the exact required order:
    `message_id,action,message_type,reason,confidence,evidence_message_ids`
*   **Allowed Domain Values**:
    - `action` is one of: `['notify', 'digest', 'mute']`
    - `message_type` is one of: `['personal', 'urgent', 'event', 'payment', 'business_update', 'promotion', 'greeting', 'forward', 'spam', 'scam', 'unknown']`
*   **Confidence Format**: Floats formatted strictly to 2 decimals, clamped to `[0.50, 1.00]`.
*   **Evidence Format**: Joined by a semicolon (e.g. `msg_001;msg_002`) or set to `"none"`.

---

## 3. Execution Commands

### Running Tests
Execute the pytest suite from the repository root:
```bash
python3 -m pytest tests/ -v
```

### Running Batch Inference
Process the default dataset and validate predictions:
```bash
python main.py
```
This generates `dataset/output.csv` and outputs:
`[OK] Submission Validator: Output conforms perfectly to contract (110 predictions validated).`
