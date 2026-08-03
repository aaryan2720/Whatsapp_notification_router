# System Architecture

The WhatsApp Message Notification Router is designed as a decoupled, top-down sequential pipeline to process incoming multimodal messages, resolve historical and relationship contexts, and determine routing priorities deterministically.

---

## 1. Overall System Architecture

The system utilizes modular pipeline components, separating state ingestion, feature extraction, scoring, and output generation.

```mermaid
graph TD
    %% Source datasets
    M_CSV["messages.csv"] --> Ingest["Loader & Schema Validator"]
    U_CSV["users.csv"] --> Ingest
    G_CSV["groups.csv"] --> Ingest
    B_CSV["business_accounts.csv"] --> Ingest
    
    %% Processing layers
    Ingest --> Bundle["Dataset Bundle (In-Memory Index)"]
    Bundle --> UserCtx["User Context Builder"]
    Bundle --> ConvCtx["Conversation Context Builder"]
    Bundle --> Retrieval["Two-Stage Evidence Retriever"]
    
    %% Multimodal layer
    M_CSV --> TextExt["Text Feature Extractor"]
    M_CSV --> Media["Multimodal Media Pipeline"]
    Media --> OCR["OCR Provider (Tesseract/Cache)"]
    Media --> ASR["ASR Provider (Whisper/Cache)"]
    
    %% Scoring & presentation
    UserCtx --> Scorer["Decision Fusion Scorer"]
    ConvCtx --> Scorer
    Retrieval --> Scorer
    TextExt --> Scorer
    OCR --> Scorer
    ASR --> Scorer
    
    Scorer --> ScTrace["DecisionTrace & Scores"]
    ScTrace --> Builder["Reason & Confidence Builder"]
    Builder --> Output["CSV Writer & Output Validator"]
    Output --> Out_CSV["output.csv"]
```

---

## 2. Dynamic Data Flow

For every processed message, data flows sequentially through isolation boundaries. Context builders and retrievers populate immutable models, leaving the decision fusion scorer completely stateless.

```mermaid
sequenceDiagram
    autonumber
    participant CLI as Launcher (main.py)
    participant Loader as Ingest Loader
    participant Context as Context Builders
    participant Search as Retriever
    participant Scorer as Decision Fusion Scorer
    participant Formatter as Presentation Formatter
    
    CLI->>Loader: load_all_datasets()
    Loader->>CLI: DatasetBundle (Indexed Tuple structures)
    
    loop for each message
        CLI->>Context: build_user_context() & build_conversation_context()
        Context->>CLI: UserContext & ConversationContext (Immutable)
        
        CLI->>Search: select_evidence()
        Search->>CLI: EvidenceBundle (Deduplicated, Jaccard-ranked matches)
        
        CLI->>Scorer: route_message()
        Note over Scorer: Executes sequential override matrix<br/>and priority scoring fusion.
        Scorer->>CLI: Preliminary Prediction (DecisionScores, DecisionTrace)
        
        CLI->>Formatter: build_final_prediction()
        Note over Formatter: Normalizes confidence (clamped [0.50, 1.00]),<br/>formats evidence IDs, maps templates.
        Formatter->>CLI: Presentation Prediction
    end
    
    CLI->>CLI: write_csv() & validate_submission()
```

---

## 3. Decision Override Pipeline

Priorities and override rules are evaluated sequentially in step boundaries to bypass priority scoring for high-certainty indicators.

```mermaid
graph TD
    Start["Evaluate Overrides (evaluate_decision_matrix)"] --> Phish{"Step 1: Phishing Score >= T.SCAM_HIGH?"}
    
    Phish -- Yes --> MutePhish["Action: mute <br/> Type: scam <br/> Override: Phishing Override"]
    Phish -- No --> BizOpt{"Step 2: Business Opt-Out or Promo Block?"}
    
    BizOpt -- Yes --> MuteBiz["Action: mute <br/> Type: promotion <br/> Override: Business Opt-Out"]
    BizOpt -- No --> OTP{"Step 3: OTP Verification Code present?"}
    
    OTP -- Yes --> NotifyOTP["Action: notify <br/> Type: urgent <br/> Override: OTP Bypass (DND Ignored)"]
    OTP -- No --> GroupMute{"Step 4: Chat in Muted Group?"}
    
    GroupMute -- Yes --> CheckUrgent{"Urgency >= T.URGENCY_HIGH?"}
    CheckUrgent -- No --> MuteGroup["Action: mute / digest <br/> Override: Muted Group"]
    CheckUrgent -- Yes --> ActiveDND
    
    GroupMute -- No --> ActiveDND{"Step 5: Active DND (Quiet Hours)?"}
    ActiveDND -- Yes --> CheckBypass{"Bypass Allowed? <br/> (Urgent personal contact)"}
    CheckBypass -- No --> DigestDND["Action: digest / mute <br/> Override: Quiet Hours Override"]
    CheckBypass -- Yes --> PriorityScore
    
    ActiveDND -- No --> PriorityScore["Step 6: Priority Score Fusion (Weighted)"]
    
    PriorityScore --> ScoreCheck{"Score >= T.FINAL_PRIORITY_NOTIFY?"}
    ScoreCheck -- Yes --> Notify["Action: notify"]
    ScoreCheck -- No --> DigestCheck{"Score >= T.FINAL_PRIORITY_DIGEST?"}
    DigestCheck -- Yes --> Digest["Action: digest"]
    DigestCheck -- No --> Mute["Action: mute"]
```

---

## 4. Module Interaction Overview

Module boundaries isolate domains:

*   **Ingestion Layer (`src/loader/`)**: Loads CSV entries and validates data structures against column-level type maps. Coerces timestamps, formats, and handles RFC 4180 parsing.
*   **Context Layer (`src/context/`)**: Computes DND windows, sender trusts, opt-ins, and group membership summaries, returning immutable dataclasses.
*   **Retrieval Layer (`src/retrieval/`)**: Filters historical logs relative to receiving user identifiers and ranks candidate history via recency-decay Jaccard index similarity.
*   **Multimodal Layer (`src/multimodal/`)**: Exposes OCR and ASR providers, falling back to offline ground-truth JSON files.
*   **Scoring & Routing Engine (`src/routing/`)**: Runs overrides and calculates final scores.
*   **Presentation Layer (`src/output/`)**: Formats predictions and runs the final `SubmissionValidator`.
