# Engineering Decisions

## Summary

This document records the concrete engineering decisions agreed during architecture and implementation planning for the Message Notification Router.

## Decisions

| Area | Decision | Why It Was Chosen | Alternatives Considered | Trade-Offs | Risks and Mitigations |
|---|---|---|---|---|---|
| Development source of truth | Develop in `src/`, package into `code/` later | Keeps work-in-progress separate from submission artifact | Implement directly in `code/` | Requires a packaging sync step | Mitigate by making `code/` self-contained before submission |
| Core approach | Hybrid deterministic system with heuristics and retrieval | Best balance for hackathon speed, interpretability, and reproducibility | Pure LLM, pure ML classifier, or rule-only system | More components to wire together | Keep modules narrow and test independently |
| User personalization | Use user behavior, quiet hours, engagement, and business history | Message value is user-specific | Global routing rules only | More feature engineering | Precompute user aggregates and reuse them |
| Conversation awareness | Use group and business metadata for trust and urgency | Conversation type strongly affects notification value | Sender-only scoring | More context joins | Normalize all entity lookups in one layer |
| Evidence selection | Retrieval-based ranking over historical messages and events | The evaluator expects explicit evidence IDs | No evidence or random history selection | Retrieval adds complexity | Cache indexes and rank by recency, similarity, and outcomes |
| Text understanding | Rule-based plus retrieval-assisted lexical scoring | Fast, deterministic, and strong for common message patterns | Large LLM for every message | Less flexible than generative reasoning | Add fallback to unknown with low confidence |
| Image understanding | OCR-first multimodal parsing | Posters and screenshots often contain the key text | Vision LLM or ignore images | OCR may fail on low-quality images | Cache OCR and fall back gracefully |
| Voice understanding | Offline speech-to-text before routing | Converts voice notes into the same text feature space | Manual heuristics on audio metadata only | ASR adds runtime cost | Cache transcripts and fall back to low-confidence metadata |
| Routing engine | Deterministic weighted scorer with safety overrides | Reproducible and easy to tune during hackathon | End-to-end learned model | Less adaptive than ML | Use explicit overrides for scam/safety cases |
| Message type assignment | Separate from action decision | Action and category are different judgments | Single combined label | More logic to maintain | Test action and message_type independently |
| Confidence output | Score-margin-based calibration | Produces stable, explainable confidence values | Fixed constants or random confidence | Requires tuned thresholds | Use evidence strength and modality certainty to calibrate |
| Reason generation | Structured templates from internal signals | Safe, consistent, and format-friendly | Free-form LLM text | Less expressive | Keep reasons short and tied to evidence |
| Packaging strategy | Final bundle must be self-contained in `code/` | Submission should not depend on outer workspace state | Rely on top-level `src/` at runtime | Requires sync discipline | Verify `code.zip` runs from terminal alone |
| Logging strategy | Append-only shared transcript plus runtime logs | Supports submission requirements and debugging | No logs or rewriteable logs | Extra bookkeeping | Never delete or rewrite the transcript |

## Alternatives Rejected

- Pure LLM reasoning for every message: too costly, less deterministic, and harder to debug.
- Pure classification without retrieval: weak evidence support and worse explanation quality.
- Pure rule system only: likely brittle on multimodal and personalized cases.

## Risks and Mitigations

- **Overconfident outputs**: calibrate confidence from score margin and evidence strength.
- **Weak OCR/ASR**: cache results, degrade gracefully, and keep routing conservative when uncertain.
- **Personalization gaps**: precompute user and group aggregates before scoring.
- **Packaging drift**: sync `src/` into `code/` only when the implementation is stable.
- **Formatting errors**: validate output schema before writing the submission CSV.
