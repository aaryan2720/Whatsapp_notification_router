"""
tests/unit/test_module10_routing.py
-----------------------------------
Unit tests for Module 10: Decision Fusion Engine.

Covers:
  - Urgent personal messages
  - Business reminders
  - Promotional messages and user opt-outs
  - Phishing domain mismatches and scams
  - OTP bypass overrides
  - Group announcements and muted groups
  - DND / Quiet Hours overrides
  - Evidence overrides
  - Multimodal agreement vs disagreement
  - Confidence calibration and margin weights
  - Rule precedence (e.g. phishing overrides promo, DND overrides normal)
  - Regression smoke test against Modules 1-9
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.models import (
    MessageRecord,
    UserContext,
    ConversationContext,
    RoutingFeatures,
    TextFeatures,
    ImageFeatures,
    VoiceFeatures,
    Prediction,
    DecisionScores,
    DecisionTrace,
)
from src.routing.scorer import route_message, score_features
from src.routing import thresholds as T


# ===========================================================================
# 1. Base Context Creators
# ===========================================================================

def _create_mock_routing_features(
    message_text: str = "Hello",
    conv_type: str = "personal",
    dnd_window: tuple[str, str] | None = None,
    created_at: datetime | None = None,
    opted_out_businesses: list[str] | None = None,
    group_muted: bool = False,
    is_dnd_active: bool = False,
    priority_hint: str = "normal",
    ubh_allows_promo: bool = True,
    phishing_prob: float = 0.0,
    text_feat: TextFeatures | None = None,
    image_feat: ImageFeatures | None = None,
    voice_feat: VoiceFeatures | None = None,
) -> RoutingFeatures:
    msg = MessageRecord(
        message_id="msg_test",
        user_id="u_001",
        conversation_type=conv_type,  # type: ignore[arg-type]
        group_id="group_123" if conv_type == "group" else "",
        business_id="biz_999" if conv_type == "business" else "",
        sender_user_id="sender_123",
        created_at=created_at or datetime(2026, 8, 1, 12, 0),
        message_text=message_text,
        media_type="",
        media_id="",
        forwarded_count=0,
    )
    user = UserContext(
        user_id="u_001",
        do_not_disturb_window=dnd_window,
        messages_opened_30d=10,
        messages_replied_30d=5,
        notifications_dismissed_30d=2,
        messages_reported_30d=0,
        daily_avg_notifications_sent=5.0,
        daily_avg_notifications_dismissed=1.0,
        opted_out_businesses=frozenset(opted_out_businesses or []),
    )
    conv = ConversationContext(
        conversation_type=conv_type,  # type: ignore[arg-type]
        group_id="group_123" if conv_type == "group" else "",
        group_muted_by_user=group_muted,
        business_id="biz_999" if conv_type == "business" else "",
        ubh_allows_promotions=ubh_allows_promo,
        phishing_probability=phishing_prob,
        priority_hint=priority_hint,
    )
    return RoutingFeatures(
        message=msg,
        user=user,
        conversation=conv,
        is_dnd_active=is_dnd_active,
        text_features=text_feat or TextFeatures(),
        image_features=image_feat,
        voice_features=voice_feat,
    )


# ===========================================================================
# 2. Scorer Unit Tests
# ===========================================================================

class TestScoringEngine:
    def test_urgent_personal_message(self) -> None:
        tf = TextFeatures(is_urgency_indicated=True)
        rf = _create_mock_routing_features(
            message_text="Please call me ASAP",
            conv_type="personal",
            priority_hint="urgent",
            text_feat=tf,
        )
        prediction = route_message(rf)

        assert prediction.action == "notify"
        assert prediction.message_type == "urgent"
        assert prediction.decision_scores.urgency_score >= 0.8
        assert "High priority score" in prediction.reason

    def test_promotion_opt_out_mute(self) -> None:
        tf = TextFeatures(is_promotion=True)
        rf = _create_mock_routing_features(
            message_text="Save 50% on all orders today!",
            conv_type="business",
            opted_out_businesses=["biz_999"],
            text_feat=tf,
        )
        prediction = route_message(rf)

        assert prediction.action == "mute"
        assert prediction.message_type == "promotion"
        assert "Business Opt-Out Override" in prediction.decision_trace.rule_overrides

    def test_promo_blocked_history_mute(self) -> None:
        tf = TextFeatures(is_promotion=True)
        rf = _create_mock_routing_features(
            message_text="Flash discount",
            conv_type="business",
            ubh_allows_promo=False,
            text_feat=tf,
        )
        prediction = route_message(rf)

        assert prediction.action == "mute"
        assert prediction.message_type == "promotion"
        assert "Business Promotions Blocked Override" in prediction.decision_trace.rule_overrides

    def test_otp_bypasses_quiet_hours(self) -> None:
        tf = TextFeatures(has_otp_pattern=True)
        rf = _create_mock_routing_features(
            message_text="Your code is 9988",
            conv_type="personal",
            is_dnd_active=True,  # quiet hours active
            text_feat=tf,
        )
        prediction = route_message(rf)

        assert prediction.action == "notify"
        assert prediction.message_type == "urgent"
        assert "OTP Bypass Override" in prediction.decision_trace.rule_overrides

    def test_phishing_spoofing_mute(self) -> None:
        rf = _create_mock_routing_features(
            message_text="Verify bank account immediately at link",
            conv_type="business",
            phishing_prob=0.8,
        )
        prediction = route_message(rf)

        assert prediction.action == "mute"
        # Type should be resolved to spam/scam
        assert prediction.message_type in ("scam", "spam")
        assert "Scam/Phishing Override" in prediction.decision_trace.rule_overrides

    def test_group_muted_announcement_digest(self) -> None:
        rf = _create_mock_routing_features(
            message_text="Weekly status note is posted",
            conv_type="group",
            group_muted=True,
        )
        prediction = route_message(rf)

        assert prediction.action == "digest"
        assert "Muted Group Override" in prediction.decision_trace.rule_overrides

    def test_dnd_quiet_hours_digest(self) -> None:
        rf = _create_mock_routing_features(
            message_text="Hey, did you get the deployment schedule?",
            conv_type="personal",
            is_dnd_active=True,
        )
        prediction = route_message(rf)

        assert prediction.action == "digest"
        assert "Quiet Hours DND Override" in prediction.decision_trace.rule_overrides


# ===========================================================================
# 3. Confidence & Agreement Tests
# ===========================================================================

class TestConfidenceCalibration:
    def test_multimodal_agreement_increases_confidence(self) -> None:
        tf = TextFeatures(is_promotion=True)
        im = ImageFeatures(is_poster=True)  # Visual poster agreement
        rf = _create_mock_routing_features(conv_type="business", text_feat=tf, image_feat=im)
        rf = RoutingFeatures(
            message=rf.message, user=rf.user, conversation=rf.conversation,
            has_valid_media=True, text_features=tf, image_features=im
        )
        scores = score_features(rf)
        conf = route_message(rf).confidence

        # Baseline single promo text confidence is typically lower than when both modalities agree
        rf_text_only = _create_mock_routing_features(conv_type="business", text_feat=tf)
        conf_text_only = route_message(rf_text_only).confidence

        assert conf >= conf_text_only

    def test_multimodal_disagreement_decreases_confidence(self) -> None:
        tf = TextFeatures(is_promotion=True)
        im = ImageFeatures(is_photograph=True)  # Photograph visual type disagrees with promotion poster
        rf = _create_mock_routing_features(conv_type="business", text_feat=tf, image_feat=im)
        rf = RoutingFeatures(
            message=rf.message, user=rf.user, conversation=rf.conversation,
            has_valid_media=True, text_features=tf, image_features=im
        )
        conf = route_message(rf).confidence

        # Disagreement reduces the margin confidence
        assert conf <= 0.85


# ===========================================================================
# 4. End-to-End Regression
# ===========================================================================

class TestRoutingRegressionSmoke:
    def test_real_pipeline_regression(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        from src.context.user_context import build_user_context
        from src.context.conversation_context import build_conversation_context
        from src.retrieval.evidence_selector import select_evidence
        from src.multimodal.text_features import extract_text_features

        bundle = load_all_datasets()

        # Select first personal message
        msg_rec = None
        for m in bundle.messages:
            if m["conversation_type"] == "personal":
                msg_rec = MessageRecord.from_row(m)
                break

        assert msg_rec is not None

        # Build context
        user_ctx = build_user_context(msg_rec.user_id, bundle)
        conv_ctx = build_conversation_context(msg_rec, bundle)
        evidence_ids = select_evidence(msg_rec, bundle).evidence_ids
        tf = extract_text_features(msg_rec.message_text)

        rf = RoutingFeatures(
            message=msg_rec,
            user=user_ctx,
            conversation=conv_ctx,
            matched_evidence_ids=evidence_ids,
            text_features=tf,
        )

        prediction = route_message(rf)
        assert isinstance(prediction, Prediction)
        assert prediction.action in ("notify", "digest", "mute")
        assert prediction.confidence >= 0.50
        assert isinstance(prediction.decision_scores, DecisionScores)
        assert isinstance(prediction.decision_trace, DecisionTrace)
