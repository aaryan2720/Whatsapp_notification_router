"""
src/retrieval/index.py
----------------------
Stage 1: Candidate Generation.

Filters historical messages from the DatasetBundle to identify a small,
high-recall candidate set of relevant messages for the incoming message.
"""

from __future__ import annotations

from typing import Any
from src.loader.csv_loader import DatasetBundle
from src.models.message import MessageRecord


def generate_candidates(
    message: MessageRecord,
    bundle: DatasetBundle,
) -> list[dict[str, Any]]:
    """
    Identify candidate historical messages relevant to the incoming message.

    Applies deterministic filters on user_id, conversation_type, group_id,
    business_id, and sender_user_id. Deduplicates candidates by message_id.
    """
    user_id = message.user_id
    ctype = message.conversation_type
    
    # Target only the history of the receiving user
    user_history = bundle.history_by_user.get(user_id, [])
    if not user_history:
        return []

    candidates: dict[str, dict[str, Any]] = {}

    for hist in user_history:
        mid = hist["message_id"]
        if mid == message.message_id:
            continue  # Do not retrieve the current incoming message as evidence

        match_reason = ""

        # 1. Match by specific channel/sender
        if ctype == "group" and message.group_id:
            if hist.get("group_id") == message.group_id:
                match_reason = "same_group"
            elif hist.get("sender_user_id") == message.sender_user_id and message.sender_user_id:
                match_reason = "same_sender_in_other_chat"

        elif ctype == "business" and message.business_id:
            if hist.get("business_id") == message.business_id:
                match_reason = "same_business"

        elif ctype == "personal" and message.sender_user_id:
            if hist.get("sender_user_id") == message.sender_user_id:
                match_reason = "same_sender"

        # 2. General backup matches: same sender across any conversation
        if not match_reason and message.sender_user_id and hist.get("sender_user_id") == message.sender_user_id:
            match_reason = "same_sender_cross_channel"

        # If a deterministic link exists, add candidate
        if match_reason:
            # Add match_reason to record copy to aid ranking/explanation stage
            cand_copy = dict(hist)
            cand_copy["candidate_generation_reason"] = match_reason
            candidates[mid] = cand_copy

    return list(candidates.values())
