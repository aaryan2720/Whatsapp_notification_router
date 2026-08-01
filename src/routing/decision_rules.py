"""
src/routing/decision_rules.py
-----------------------------
Defines the Rule Override system and the Decision Matrix logic.

Translates DecisionScores into final Action and MessageType predictions
using deterministic rule priorities.
"""

from __future__ import annotations

from typing import Any
from src.models import RoutingFeatures, DecisionScores, DecisionTrace
from src.utils.types import Action, MessageType
from src.routing import thresholds as T


def evaluate_decision_matrix(
    features: RoutingFeatures,
    scores: DecisionScores,
    trace_log: dict[str, Any],
) -> tuple[Action, MessageType, list[str], str]:
    """
    Execute rule overrides and threshold assessments to produce final routing action.

    Priority:
      1. Phishing & Scam Override -> MUTE
      2. Business Opt-Out Override -> MUTE / DIGEST
      3. OTP Bypass Override -> NOTIFY (Bypasses DND)
      4. Group Muted Override -> MUTE / DIGEST
      5. Active DND Override -> DIGEST (Bypasses regular notify)
      6. Decision Matrix Thresholds (Final Priority Score) -> NOTIFY/DIGEST/MUTE

    Returns:
        tuple (Action, MessageType, rule_overrides_list, final_reasoning_path)
    """
    overrides: list[str] = []
    reason_path: str = ""

    # Determine base message type categorization first
    resolved_type = resolve_message_type(features, scores)

    # 1. PHISHING & SCAM OVERRIDE
    if scores.scam_score >= T.SCAM_HIGH or features.conversation.phishing_probability >= T.PHISHING_HIGH:
        overrides.append("Scam/Phishing Override")
        reason_path = "Phishing/scam indicator or sender spoofing detected; message suppressed."
        return "mute", "scam" if scores.scam_score > 0.8 else "spam", overrides, reason_path

    # 2. BUSINESS OPT-OUT OVERRIDE
    if features.conversation.conversation_type == "business":
        biz_id = features.conversation.business_id
        if biz_id in features.user.opted_out_businesses:
            overrides.append("Business Opt-Out Override")
            reason_path = "User has explicitly opted out of notifications from this business."
            return "mute", resolved_type, overrides, reason_path

        # If promotional text and promotions are not allowed by user for this business
        if scores.promotion_score >= T.PROMOTION_HIGH and not features.conversation.ubh_allows_promotions:
            overrides.append("Business Promotions Blocked Override")
            reason_path = "User blocked promotional messages from this business history."
            return "mute", "promotion", overrides, reason_path

    # 3. OTP BYPASS OVERRIDE
    has_otp = (
        (features.text_features and features.text_features.has_otp_pattern)
        or (features.image_features and "otp" in features.ocr_text.lower())
        or (features.voice_features and "otp" in features.voice_features.transcript.lower())
    )
    if has_otp:
        overrides.append("OTP Bypass Override")
        reason_path = "Critical verification code (OTP) bypasses quiet hours and notification filters."
        return "notify", "urgent", overrides, reason_path

    # 4. GROUP MUTED OVERRIDE
    if features.conversation.conversation_type == "group" and features.conversation.group_muted_by_user:
        # Emergency/Critical can bypass, otherwise mute group
        if scores.urgency_score < T.URGENCY_HIGH:
            overrides.append("Muted Group Override")
            reason_path = "Message belongs to a group muted by the user."
            # If it's a promotion or spam, mute; otherwise digest
            act: Action = "mute" if (scores.promotion_score >= T.PROMOTION_HIGH or scores.spam_score >= T.SPAM_HIGH) else "digest"
            return act, resolved_type, overrides, reason_path

    # 5. ACTIVE DND OVERRIDE (QUIET HOURS)
    if scores.quiet_hours_score > 0.5:
        # High urgency personal messages or emergency contact can bypass
        is_bypass = (
            features.conversation.conversation_type == "personal"
            and scores.urgency_score >= T.URGENCY_HIGH
            and scores.relationship_score >= T.RELATIONSHIP_STRONG
        )
        if not is_bypass:
            overrides.append("Quiet Hours DND Override")
            reason_path = "Message received within user's quiet hours window; postponed to digest."
            act: Action = "mute" if (scores.promotion_score >= T.PROMOTION_HIGH or scores.spam_score >= T.SPAM_HIGH) else "digest"
            return act, resolved_type, overrides, reason_path

    # 6. DECISION MATRIX THRESHOLDS (STANDARD SCORE FUSION)
    priority = scores.final_priority_score
    if priority >= T.FINAL_PRIORITY_NOTIFY:
        action = "notify"
        reason_path = f"High priority score ({priority:.2f}) determined by relationship and urgency signals."
    elif priority >= T.FINAL_PRIORITY_DIGEST:
        action = "digest"
        reason_path = f"Moderate priority score ({priority:.2f}) routed to digest."
    else:
        action = "mute"
        reason_path = f"Low priority score ({priority:.2f}) suppressed."

    return action, resolved_type, overrides, reason_path


def resolve_message_type(features: RoutingFeatures, scores: DecisionScores) -> MessageType:
    """Resolve the MessageType category based on textual and visual scores."""
    # Order of evaluation for message type classification:
    # Scam/phishing, OTP/Urgent, Payment, Event, Promotion, Greeting, personal/business_update, forward
    
    if scores.scam_score >= T.SCAM_HIGH:
        return "scam"
    if scores.spam_score >= T.SPAM_HIGH:
        return "spam"

    has_otp = (
        (features.text_features and features.text_features.has_otp_pattern)
        or "otp" in features.ocr_text.lower()
        or "otp" in features.asr_transcript.lower()
    )
    if has_otp or scores.urgency_score >= T.URGENCY_HIGH:
        return "urgent"

    if features.text_features:
        if features.text_features.is_payment_indicated:
            return "payment"
        if features.text_features.is_promotion:
            return "promotion"
        if features.text_features.is_event_announcement:
            return "event"
        if features.text_features.is_greeting:
            return "greeting"
        if features.text_features.has_forwarded_cues:
            return "forward"

    if features.conversation.conversation_type == "business":
        return "business_update"
    if features.conversation.conversation_type == "personal":
        return "personal"
    
    return "unknown"
