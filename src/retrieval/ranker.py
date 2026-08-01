"""
src/retrieval/ranker.py
-----------------------
Stage 2: Candidate Ranking.

Ranks evidence candidates using a hybrid deterministic strategy:
  1. Lexical text similarity (token-based Jaccard overlap)
  2. Recency decay (exponential/fractional time decay)
  3. Action outcome weights (prioritizing history with replies/reports)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from src.loader.csv_loader import DatasetBundle
from src.models.message import MessageRecord

# Pre-compile regex for word tokenisation
_WORD_RE = re.compile(r"\w+")


def _tokenize(text: str) -> set[str]:
    """Tokenise text into a set of lowercased alphanumeric words."""
    if not text:
        return set()
    return set(_WORD_RE.findall(text.lower()))


def _compute_jaccard_similarity(text_a: str, text_b: str) -> float:
    """Calculate Jaccard similarity between two texts."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a and not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union


def rank_candidates(
    message: MessageRecord,
    candidates: list[dict[str, Any]],
    bundle: DatasetBundle,
) -> list[tuple[dict[str, Any], float, str]]:
    """
    Score and rank candidate messages for the current incoming message.

    Returns:
        List of tuples: (candidate_dict, score, selection_explanation)
        ordered by score descending.
    """
    ranked_results: list[tuple[dict[str, Any], float, str]] = []
    current_time = message.created_at or datetime.now()

    for cand in candidates:
        cand_id = cand["message_id"]
        cand_text = cand.get("message_text", "")
        cand_time = cand.get("created_at")
        reason = cand.get("candidate_generation_reason", "unknown")

        # 1. Lexical Similarity (Jaccard)
        lexical_score = _compute_jaccard_similarity(message.message_text, cand_text)

        # 2. Recency Decay (scale over 30 days)
        recency_decay = 1.0
        if cand_time and current_time:
            days_diff = abs((current_time - cand_time).total_seconds()) / 86400.0
            recency_decay = 1.0 / (1.0 + (days_diff / 30.0))

        # 3. Reaction Outcomes (reported or replied are highly relevant evidence)
        reaction_bonus = 0.0
        event = bundle.events_by_message_id.get(cand_id)
        explanation_tags = []
        if event:
            if event.get("message_reported"):
                reaction_bonus += 0.5
                explanation_tags.append("previously reported by user")
            if event.get("message_replied"):
                reaction_bonus += 0.4
                explanation_tags.append("user replied to this message")
            if event.get("muted_after_message"):
                reaction_bonus += 0.3
                explanation_tags.append("user muted sender after this message")
            if event.get("message_opened") and not event.get("notification_dismissed"):
                reaction_bonus += 0.1
                explanation_tags.append("user read this message")

        # 4. Base generation source weighting
        base_weight = 0.1
        if reason == "same_sender":
            base_weight = 0.3
            explanation_tags.append("sent by same contact")
        elif reason == "same_group":
            base_weight = 0.3
            explanation_tags.append("from same group")
        elif reason == "same_business":
            base_weight = 0.3
            explanation_tags.append("from same business")
        elif reason == "same_sender_in_other_chat":
            base_weight = 0.2
            explanation_tags.append("sender active in other chat")

        # Combine scores using hybrid weights
        # Max theoretical score: (1.0 * 0.35) + (1.0 * 0.25) + (0.5 * 0.3) + (0.3 * 0.1) = 0.78
        # We normalize and cap the score between 0.0 and 1.0.
        raw_score = (
            (lexical_score * 0.35)
            + (recency_decay * 0.25)
            + (reaction_bonus * 0.30)
            + (base_weight * 0.10)
        )
        final_score = min(1.0, max(0.0, raw_score))

        # Generate explanatory string
        if not explanation_tags:
            explanation_tags.append("historical contact")
        explanation = ", ".join(explanation_tags)

        ranked_results.append((cand, final_score, explanation))

    # Sort candidates descending by final relevance score
    ranked_results.sort(key=lambda x: x[1], reverse=True)
    return ranked_results
