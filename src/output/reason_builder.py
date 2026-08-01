"""
src/output/reason_builder.py
----------------------------
Presentation and explanation layer (Module 11).

Formulates natural, template-based reasons, finalizes/normalizes confidence scores,
and formats evidence IDs without re-running routing logic.
"""

from __future__ import annotations

from src.models import Prediction, ReasonFragments
from src.utils.types import Action, MessageType
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def build_deterministic_reason(
    action: Action,
    msg_type: MessageType,
    overrides: list[str],
    fragments: ReasonFragments,
) -> str:
    """
    Construct a concise explanation template based on ReasonFragments and overrides.
    """
    # 1. Check rule overrides first
    if "Scam/Phishing Override" in overrides or fragments.phishing_detected:
        return "Potential phishing attempt detected from an untrusted sender."

    if "Business Opt-Out Override" in overrides or "Business Promotions Blocked Override" in overrides:
        return "Muted promotional message from an opted-out business."

    if "OTP Bypass Override" in overrides or fragments.otp_detected:
        return "Urgent verification code requiring immediate attention."

    if "Quiet Hours DND Override" in overrides:
        return "Message buffered during user quiet hours."

    if "Muted Group Override" in overrides:
        return "Message muted because it belongs to a muted group."

    # 2. Check fragment combinations
    if fragments.payment_due and fragments.verified_business:
        return "Verified business payment reminder."

    if fragments.strong_historical_evidence and fragments.user_usually_opens and action == "notify":
        return "Similar messages were previously opened by the user."

    if fragments.trusted_sender and fragments.verified_business and action == "notify":
        return "Notification allowed from a verified official business."

    if fragments.trusted_sender and action == "notify":
        return "Notification allowed from a trusted contact."

    # 3. Fallback based on Action + MessageType
    if action == "notify":
        if msg_type == "urgent":
            return "Urgent notification allowed requiring immediate attention."
        return "Notification allowed based on relationship and urgency signals."

    if action == "digest":
        if fragments.promotion_detected:
            return "Promotional message routed to digest."
        return "Message routed to digest based on user preference."

    # action == "mute"
    if fragments.promotion_detected:
        return "Promotional message muted based on user history."
    return "Low priority message muted."


def finalize_confidence(preliminary_confidence: float) -> float:
    """Normalize and clamp confidence to [0.50, 1.00]."""
    clamped = max(0.50, min(1.00, preliminary_confidence))
    return round(clamped, 2)


def format_evidence_message_ids(evidence_ids: tuple[str, ...]) -> tuple[str, ...]:
    """
    Deduplicate and format evidence message IDs, maintaining deterministic order.
    Returns ("none",) if empty.
    """
    seen: set[str] = set()
    deduped: list[str] = []

    for eid in evidence_ids:
        clean_id = eid.strip() if eid else ""
        if clean_id and clean_id.lower() != "none" and clean_id not in seen:
            seen.add(clean_id)
            deduped.append(clean_id)

    if not deduped:
        return ("none",)

    return tuple(deduped)


def build_final_prediction(prediction: Prediction) -> Prediction:
    """
    Consume the preliminary Prediction, update the reason via template-rendering,
    normalize confidence, and clean up evidence IDs.
    """
    # 1. Resolve reason text
    overrides = prediction.decision_trace.rule_overrides if prediction.decision_trace else []
    fragments = prediction.reason_fragments or ReasonFragments()

    reason = build_deterministic_reason(
        action=prediction.action,
        msg_type=prediction.message_type,
        overrides=overrides,
        fragments=fragments,
    )

    # 2. Finalize confidence
    final_conf = finalize_confidence(prediction.confidence)

    # 3. Format evidence IDs
    final_evidence_ids = format_evidence_message_ids(prediction.evidence_message_ids)

    # 4. Construct presentation Prediction
    return Prediction(
        message_id=prediction.message_id,
        action=prediction.action,
        message_type=prediction.message_type,
        reason=reason,
        confidence=final_conf,
        evidence_message_ids=final_evidence_ids,
        decision_scores=prediction.decision_scores,
        decision_trace=prediction.decision_trace,
        reason_fragments=prediction.reason_fragments,
    )
