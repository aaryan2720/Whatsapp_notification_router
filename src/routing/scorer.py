"""
src/routing/scorer.py
---------------------
The core Feature Scoring Engine and Scorer orchestration layer.

Computes DecisionScores, executes Decision Matrix and Rule Overrides,
and generates debuggable DecisionTrace and calibrated Predictions.
"""

from __future__ import annotations

import math
from typing import Any
from src.models import RoutingFeatures, DecisionScores, DecisionTrace, Prediction, ReasonFragments
from src.routing.decision_rules import evaluate_decision_matrix
from src.routing import thresholds as T
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def score_features(features: RoutingFeatures) -> DecisionScores:
    """
    Independently score every major feature family based on RoutingFeatures.

    Returns:
        DecisionScores populated with intermediate engineering signals.
    """
    # 1. Urgency Score
    urgency = 0.0
    if features.text_features and features.text_features.is_urgency_indicated:
        urgency = 0.90
    if features.text_features and features.text_features.has_otp_pattern:
        urgency = 1.0
    if features.conversation.priority_hint == "urgent":
        urgency = max(urgency, 0.80)
    # Check ASR/OCR text for urgency triggers
    media_lower = (features.ocr_text + " " + features.asr_transcript).lower()
    if any(w in media_lower for w in ["urgent", "immediately", "asap", "emergency", "deadline", "midnight"]):
        urgency = max(urgency, 0.75)
    urgency = min(1.0, max(0.0, urgency))

    # 2. Relationship Score
    relationship = 0.0
    if features.conversation.conversation_type == "personal":
        relationship = 0.60
    if features.conversation.relationship_strength > 0.0:
        relationship = max(relationship, features.conversation.relationship_strength)
    # If contact is known/trusted
    if features.conversation.sender_trust > 0.7:
        relationship = min(1.0, relationship + 0.20)
    relationship = min(1.0, max(0.0, relationship))

    # 3. Trust Score
    trust = features.conversation.sender_trust
    if features.conversation.business_verified:
        trust = max(trust, 0.90)
    if features.conversation.phishing_probability > 0.5:
        trust = 0.0
    trust = min(1.0, max(0.0, trust))

    # 4. Business Score
    business = 0.0
    if features.conversation.conversation_type == "business":
        business = 0.50
        if features.conversation.business_verified:
            business = 0.80
        # If user explicitly opted out
        if features.conversation.business_id in features.user.opted_out_businesses:
            business = 0.0
    business = min(1.0, max(0.0, business))

    # 5. Promotion Score
    promo = 0.0
    if features.text_features and features.text_features.is_promotion:
        promo = 0.85
    # If media OCR indicates discount/sale or it is a poster
    if features.image_features and features.image_features.is_poster:
        promo = max(promo, 0.70)
    if any(w in media_lower for w in ["offer", "sale", "discount", "coupon", "save", "rs", "win"]):
        promo = max(promo, 0.65)
    promo = min(1.0, max(0.0, promo))

    # 6. Spam Score
    spam = 0.0
    if features.text_features and features.text_features.is_scam_signal:
        spam = 0.60
    if features.conversation.business_user_reports_30d > 10:
        spam = max(spam, 0.75)
    if features.conversation.sender_trust < 0.2:
        spam = max(spam, 0.50)
    if features.historical_report_rate > 0.1:
        spam = max(spam, 0.80)
    spam = min(1.0, max(0.0, spam))

    # 7. Scam Score
    scam = 0.0
    if features.text_features and features.text_features.is_scam_signal:
        scam = 0.80
    if features.text_features and features.text_features.has_suspicious_link:
        scam = 1.0
    if features.conversation.phishing_probability > 0.5:
        scam = max(scam, 0.90)
    scam = min(1.0, max(0.0, scam))

    # 8. Evidence Score
    evidence = 0.0
    if features.matched_evidence_ids:
        # Check historical rates to assign evidence score
        evidence = features.historical_open_rate * 0.5 + features.historical_reply_rate * 0.8
        # Subtract dismiss/report weights
        evidence -= features.historical_dismiss_rate * 0.6 + features.historical_report_rate * 1.0
    evidence = min(1.0, max(-1.0, evidence))

    # 9. Multimodal Score
    multimodal = 0.0
    if features.has_valid_media:
        multimodal = 0.50
        if features.image_features:
            if features.image_features.is_screenshot or features.image_features.is_receipt:
                multimodal = 0.80
            elif features.image_features.is_poster:
                multimodal = 0.60
        if features.voice_features and features.voice_features.speech_detected:
            multimodal = max(multimodal, 0.70)
    multimodal = min(1.0, max(0.0, multimodal))

    # 10. Conversation Score
    conv = 0.0
    if features.conversation.conversation_type == "personal":
        conv = 0.60
    elif features.conversation.conversation_type == "group":
        conv = 0.30
        if features.conversation.user_role_in_group == "admin":
            conv += 0.20
        if features.conversation.group_muted_by_user:
            conv = -0.80
    conv = min(1.0, max(-1.0, conv))

    # 11. Personalization Score
    personalization = features.historical_reply_rate - features.historical_dismiss_rate
    personalization = min(1.0, max(-1.0, personalization))

    # 12. Notification Fatigue Score
    fatigue = 0.0
    if features.user.daily_avg_notifications_sent > 20:
        fatigue = min(1.0, features.user.daily_avg_notifications_sent / 50.0)
    fatigue = min(1.0, max(0.0, fatigue))

    # 13. Quiet Hours Score
    quiet_hours = 1.0 if features.is_dnd_active else 0.0

    # 14. Final Priority Score (Weighted fusion)
    priority = (
        (urgency * 2.5)
        + (relationship * 1.5)
        + (trust * 1.0)
        + (evidence * 1.0)
        + (personalization * 0.8)
        - (spam * 2.5)
        - (scam * 3.5)
        - (fatigue * 0.5)
    )
    if quiet_hours > 0.5:
        priority -= 2.0

    return DecisionScores(
        urgency_score=urgency,
        relationship_score=relationship,
        trust_score=trust,
        business_score=business,
        promotion_score=promo,
        spam_score=spam,
        scam_score=scam,
        evidence_score=evidence,
        multimodal_score=multimodal,
        conversation_score=conv,
        personalization_score=personalization,
        notification_fatigue_score=fatigue,
        quiet_hours_score=quiet_hours,
        final_priority_score=priority,
    )


def calculate_confidence(
    features: RoutingFeatures,
    scores: DecisionScores,
    chosen_action: str,
    overrides: list[str],
) -> float:
    """
    Compute calibrated decision confidence using multiple factors:
      - score margin from thresholds
      - multimodal agreement (OCR/ASR vs text category)
      - evidence consistency
      - override certainty
    """
    # 1. Base confidence
    confidence = 0.70

    # 2. Score Margin Factor
    priority = scores.final_priority_score
    if chosen_action == "notify":
        margin = priority - T.FINAL_PRIORITY_NOTIFY
    elif chosen_action == "digest":
        margin = min(priority - T.FINAL_PRIORITY_DIGEST, T.FINAL_PRIORITY_NOTIFY - priority)
    else:
        margin = T.FINAL_PRIORITY_DIGEST - priority

    # Larger margins increase confidence
    confidence += min(0.15, max(-0.15, margin * 0.10))

    # 3. Multimodal Agreement
    if features.has_valid_media:
        is_promo_text = features.text_features and features.text_features.is_promotion
        is_promo_img = features.image_features and features.image_features.is_poster
        if is_promo_text and is_promo_img:
            confidence += 0.08  # Modalities agree on marketing intent
        elif is_promo_text != is_promo_img:
            confidence -= 0.05  # Modalities disagree on marketing intent

    # 4. Evidence consistency
    if features.matched_evidence_ids:
        # Strong agreement with history
        if chosen_action == "notify" and (features.historical_open_rate > 0.7 or features.historical_reply_rate > 0.4):
            confidence += 0.08
        elif chosen_action == "mute" and (features.historical_dismiss_rate > 0.7 or features.historical_report_rate > 0.2):
            confidence += 0.08
    else:
        confidence -= 0.03  # No history context decreases confidence slightly

    # 5. Rule Certainty overrides
    if "OTP Bypass Override" in overrides:
        # OTP routing is highly certain
        return 0.95
    if "Scam/Phishing Override" in overrides:
        # Phishing detection is highly certain
        return 0.95
    if "Business Opt-Out Override" in overrides:
        return 0.90

    # Clamp confidence strictly between 0.50 and 1.00
    return min(1.0, max(0.50, confidence))


def route_message(features: RoutingFeatures, bundle: Any = None) -> Prediction:
    """
    Main entry point for Module 10. Runs scoring, overrides matrix,
    calculates confidence, and outputs the Prediction contract.
    """
    logger.info("Routing message: %s", features.message.message_id)

    # 1. Compute individual feature scores
    scores = score_features(features)

    # 2. Run Decision Matrix & Overrides
    trace_log: dict[str, Any] = {}
    action, resolved_type, overrides, reason_path = evaluate_decision_matrix(features, scores, trace_log)

    # 3. Calibrate confidence
    confidence = calculate_confidence(features, scores, action, overrides)

    # 4. Create ReasonFragments
    is_payment = (features.text_features and features.text_features.is_payment_indicated) or False
    media_lower = (features.ocr_text + " " + features.asr_transcript).lower()
    has_otp = (
        (features.text_features and features.text_features.has_otp_pattern)
        or "otp" in media_lower
    )
    is_promo_text = (features.text_features and features.text_features.is_promotion) or False
    is_promo_img = (features.image_features and features.image_features.is_poster) or False
    is_promo_voice = "offer" in media_lower or "sale" in media_lower
    promo_detected = is_promo_text or is_promo_img or is_promo_voice

    fragments = ReasonFragments(
        verified_business=features.conversation.business_verified,
        trusted_sender=features.conversation.sender_trust >= T.TRUST_HIGH,
        payment_due=is_payment,
        otp_detected=has_otp,
        recent_similar_message=len(features.matched_evidence_ids) > 0,
        user_usually_opens=features.historical_open_rate >= 0.60,
        promotion_detected=promo_detected,
        phishing_detected=scores.scam_score >= T.SCAM_HIGH or features.conversation.phishing_probability >= T.PHISHING_HIGH,
        muted_group=features.conversation.group_muted_by_user if features.conversation.conversation_type == "group" else False,
        quiet_hours=scores.quiet_hours_score > 0.5,
        multimodal_agreement=features.has_valid_media and (is_promo_text == is_promo_img),
        strong_historical_evidence=features.historical_open_rate >= 0.70 or features.historical_reply_rate >= 0.40,
        weak_evidence=len(features.matched_evidence_ids) == 0,
    )

    # 5. Create Decision Trace for debugging
    contributions = {
        "urgency": scores.urgency_score,
        "relationship": scores.relationship_score,
        "trust": scores.trust_score,
        "evidence": scores.evidence_score,
        "scam": scores.scam_score,
        "spam": scores.spam_score,
        "quiet_hours": scores.quiet_hours_score,
        "priority": scores.final_priority_score,
    }
    trace = DecisionTrace(
        contributions=contributions,
        rule_overrides=overrides,
        thresholds_crossed=[
            f"urgency_high" if scores.urgency_score >= T.URGENCY_HIGH else "urgency_normal",
            f"scam_flagged" if scores.scam_score >= T.SCAM_HIGH else "scam_clear",
        ],
        final_reasoning_path=reason_path,
    )

    return Prediction(
        message_id=features.message.message_id,
        action=action,
        message_type=resolved_type,
        reason=reason_path,
        confidence=confidence,
        evidence_message_ids=features.matched_evidence_ids,
        decision_scores=scores,
        decision_trace=trace,
        reason_fragments=fragments,
    )
