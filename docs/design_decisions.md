# Engineering Design Decisions

This document details the core technical design choices, architectural rationales, tradeoffs, and limitations of the Message Notification Router.

---

## 1. Core Architecture Decisions

### Deterministic AI vs. Probabilistic Models
*   **Decision**: The routing engine is completely deterministic, utilizing rule matrices and priority score fusions instead of runtime ML models or LLMs.
*   **Rationale**: 
    1. **Reproducibility**: Assures consistent outputs across execution runs, making evaluations and regression testing stable.
    2. **Debugging**: Simplifies root-cause diagnosis. If a routing decision is incorrect, the developer can inspect the `DecisionTrace` to see exactly which score contribution or override rule triggered the path.
    3. **Latency**: Eliminates runtime inference latency, reducing message routing overhead to `<10ms`.

### Rule-Based Priority Scoring
*   **Decision**: Scoring uses segmented linear weights and override matrices.
*   **Rationale**: Notification management is highly personalized but behaves under strict user choices. By defining logical precedence chains (e.g. DND bypass rules, business opt-outs, muted groups), we match user expectations accurately without risking model drift.

### Two-Stage Evidence Retrieval
*   **Decision**: Retrieval utilizes deterministic filtering followed by a recency-decay Jaccard similarity ranker.
*   **Rationale**: High-volume interaction feeds require fast retrieval. Stage 1 filters candidate sets by target user to minimize search space, while Stage 2 evaluates word-token intersections to surface historical precedents instantly.

### Multimodal Provider Abstraction
*   **Decision**: OCR and ASR pipelines are encapsulated behind factory-loaded interface providers.
*   **Rationale**: Decouples the message router from machine-specific OCR (Tesseract) and ASR (Whisper) binary dependencies. In environments lacking GPU/CPU binary libraries, the system falls back to offline JSON caches, ensuring 100% fail-safe executions.

---

## 2. Python Engineering Best Practices

### Frozen Dataclasses (`slots=True`)
*   **Decision**: Domain models are created as frozen dataclasses with `slots=True` enforced (available in Python 3.10+).
*   **Rationale**: 
    *   **Immutability**: Guarantees that context states and feature properties remain immutable after load.
    *   **Memory Efficiency**: Enforcing `slots=True` prevents the instantiation of a mutable `__dict__` for each object. This reduces RAM usage, which is critical when processing thousands of message entities.

### Intermediate Model Boundaries (`ReasonFragments`)
*   **Decision**: Decouple the Decision Scorer from output formatting using a typed boolean flags container `ReasonFragments`.
*   **Rationale**: Prevents score logic from mixing with string parsing or print templates. Module 10 populates simple flags (e.g. `otp_detected=True`), and Module 11 formats natural language reasons from these flags, isolating core logic from presentation modifications.

---

## 3. Tradeoffs & Limitations

### Tradeoffs
*   **Lexical vs. Semantic Similarity**: Jaccard token matching is fast and simple but does not capture synonyms (e.g., matching "invoice" with "bill" requires explicit category keywords). A semantic search (e.g., BERT embeddings) would capture this but introduce heavy GPU dependencies and latency.
*   **Static Cached Fallbacks**: The offline provider caches ensure portability but require cache refreshes if new images or audio notes are appended to the dataset directory.

### Known Limitations
*   **Single-Threaded Batching**: The batch runner executes sequentially. For large-scale enterprise deployments (millions of users), this loop must be distributed across a multiprocessing pool worker pipeline.
*   **Local JSON Cache**: OCR/ASR caches reside on the local disk. Distributed systems would require a centralized, key-value memory database (e.g., Redis) to share media transcripts.
