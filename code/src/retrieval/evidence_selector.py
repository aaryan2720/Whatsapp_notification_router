"""
src/retrieval/evidence_selector.py
----------------------------------
Ties Stage 1 (generation) and Stage 2 (ranking) together.
Produces the canonical EvidenceBundle domain model for downstream routing.
"""

from __future__ import annotations

from typing import Any
from src.configs import settings as _SETTINGS
from src.loader.csv_loader import DatasetBundle
from src.models.message import MessageRecord
from src.models.evidence import EvidenceRecord, EvidenceBundle
from src.retrieval.index import generate_candidates
from src.retrieval.ranker import rank_candidates


def select_evidence(
    message: MessageRecord,
    bundle: DatasetBundle,
    top_k: int | None = None,
) -> EvidenceBundle:
    """
    Generate, rank, filter, and compile historical evidence for an incoming message.

    Parameters
    ----------
    message: Current incoming MessageRecord.
    bundle:  DatasetBundle inputs.
    top_k:   Maximum evidence records to return (defaults to settings.THRESHOLDS.evidence_max_count).

    Returns
    -------
    An EvidenceBundle containing sorted EvidenceRecords.
    """
    if top_k is None:
        top_k = _SETTINGS.THRESHOLDS.evidence_max_count

    # Stage 1: Candidate Generation (O(H_u) where H_u is user history volume)
    candidates = generate_candidates(message, bundle)
    if not candidates:
        return EvidenceBundle(ranked_evidence=())

    # Stage 2: Candidate Ranking
    ranked_results = rank_candidates(message, candidates, bundle)

    # 3. Filtering and Selector logic
    min_relevance = _SETTINGS.THRESHOLDS.evidence_min_relevance
    
    selected_records: list[EvidenceRecord] = []
    scores_dict: dict[str, float] = {}
    explanations_dict: dict[str, str] = {}
    metadata: dict[str, Any] = {
        "total_candidates_found": len(candidates),
        "source_conversation_type": message.conversation_type,
    }

    for cand, score, explanation in ranked_results:
        if len(selected_records) >= top_k:
            break
        
        # Discard low-relevance candidates to avoid noise
        if score < min_relevance:
            continue

        mid = cand["message_id"]
        record = EvidenceRecord(
            message_id=mid,
            relevance_score=score,
            matching_criteria=cand.get("candidate_generation_reason", "unknown"),
            created_at=cand.get("created_at"),
            message_text=cand.get("message_text", ""),
        )
        selected_records.append(record)
        scores_dict[mid] = score
        explanations_dict[mid] = explanation

    # Compute overall retrieval confidence as the score of the top candidate
    # (or 0.0 if no evidence matches)
    confidence = selected_records[0].relevance_score if selected_records else 0.0

    return EvidenceBundle(
        ranked_evidence=tuple(selected_records),
        ranking_scores=scores_dict,
        retrieval_metadata=metadata,
        retrieval_confidence=confidence,
        retrieval_explanation=explanations_dict,
    )
