# Evaluation Strategy

## Expected Evaluation Criteria

The submission will likely be judged on:

- Correctness of `action`
- Correctness of `message_type`
- Usefulness and consistency of `reason`
- Relevance of `evidence_message_ids`
- Confidence calibration
- Personalization quality
- Multimodal reasoning quality
- Output formatting correctness
- Determinism and reproducibility
- Packaging correctness

## Accuracy Strategy

The intended strategy is a hybrid deterministic system:

- Use structured metadata first.
- Use history and evidence retrieval second.
- Use text, image, and voice processing to enrich the signal.
- Apply explicit safety overrides for scam-like or clearly unsafe messages.

This is the best trade-off for the hackathon because it is interpretable, fast to iterate on, and reproducible.

## Evidence Retrieval Strategy

Evidence should be selected from historical messages and message events using a ranked pipeline:

1. Filter by user, sender, group, or business relationship.
2. Prefer recent and outcome-relevant historical messages.
3. Rank by lexical similarity and structural match.
4. Return only the strongest evidence IDs.
5. Use `none` when no useful evidence exists.

The goal is to support the decision, not to force evidence into every row.

## Confidence Calibration

Confidence should be derived from a combination of:

- Score margin between competing actions
- Strength of evidence
- Certainty of modality signals
- Presence of explicit risk indicators

Avoid constant or arbitrary confidence values. Lower confidence should appear on ambiguous or sparse-history cases.

## Personalization Strategy

Personalization should use:

- Quiet hours
- Recent opens, replies, dismissals, and reports
- Group membership and mute state
- Business opt-in / opt-out state
- Recent business activity
- Historical sender relationship

The same message may deserve different routing for different recipients.

## Multimodal Processing Strategy

- Text should be parsed directly.
- Images should go through OCR and lightweight visual classification.
- Voice notes should go through transcription before routing.
- The routing engine should receive normalized features rather than raw media.

## Potential Score Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Wrong action label | Major score loss | Use explicit action thresholds and safety overrides |
| Wrong message_type | Partial score loss | Separate action scoring from type classification |
| Weak evidence selection | Lower explanation quality | Use ranked retrieval with history and event context |
| Poor confidence calibration | Reduced trust in predictions | Calibrate confidence from score margin and evidence strength |
| Missing multimodal reasoning | Bad handling of image/audio messages | Ensure OCR and ASR are integrated before scoring |
| Lack of personalization | Same decision for all users | Build per-user and per-conversation context first |
| Formatting errors | Submission failure or score loss | Validate output schema and row counts before writing |
| Non-reproducibility | Inconsistent results | Use deterministic ranking, thresholds, and caching |
| Packaging drift | Broken code.zip | Verify the packaged `code/` folder runs independently |

## Evaluation Mindset

A HackerRank evaluator will reward systems that are:

- Correct on obvious urgent, business, and scam patterns
- Conservative when uncertain
- Backed by relevant evidence
- Stable across repeated runs
- Fully aligned with the output contract
