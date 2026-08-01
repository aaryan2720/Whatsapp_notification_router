"""
tests/unit/test_module3_models.py
---------------------------------
Unit tests for Module 3: Core Domain Models and Shared Data Contracts.

Covers:
  - MessageRecord (equality, slots, immutability, serialization/deserialization)
  - UserContext (DND helper, defaults, serialization/deserialization)
  - ConversationContext (helper properties, defaults, serialization/deserialization)
  - RoutingFeatures (composite properties, serialization/deserialization)
  - EvidenceRecord (equality, serialization/deserialization)
  - DecisionExplanation (rendering logic)
  - Prediction (equality, CSV formatting output, serialization/deserialization)
"""

from __future__ import annotations

import sys
from datetime import datetime, date, time
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
    EvidenceRecord,
    DecisionExplanation,
    Prediction,
)


# ===========================================================================
# 1. MessageRecord
# ===========================================================================

class TestMessageRecord:
    def test_slots_and_immutability(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_002",
            created_at=datetime(2026, 7, 30, 22, 19),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        # Verify slots: slots-based classes do not have __dict__
        assert not hasattr(msg, "__dict__")

        # Verify immutability (frozen=True)
        with pytest.raises(AttributeError):
            msg.message_id = "msg_002"  # type: ignore[misc]

    def test_equality(self) -> None:
        m1 = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_002",
            created_at=datetime(2026, 7, 30, 22, 19),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        m2 = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_002",
            created_at=datetime(2026, 7, 30, 22, 19),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        m3 = MessageRecord(
            message_id="msg_002",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_002",
            created_at=datetime(2026, 7, 30, 22, 19),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        assert m1 == m2
        assert m1 != m3

    def test_serialization_roundtrip(self) -> None:
        raw_row = {
            "message_id": "msg_023",
            "user_id": "u_002",
            "conversation_type": "business",
            "group_id": "",
            "business_id": "business_002",
            "sender_user_id": "",
            "created_at": datetime(2026, 7, 30, 22, 19),
            "message_text": "Important Information",
            "media_type": "",
            "media_id": "",
            "forwarded_count": 0,
        }
        msg = MessageRecord.from_row(raw_row)
        serialized = msg.to_dict()
        assert serialized["message_id"] == "msg_023"
        assert serialized["created_at"] == datetime(2026, 7, 30, 22, 19)

        deserialized = MessageRecord.from_row(serialized)
        assert msg == deserialized


# ===========================================================================
# 2. UserContext
# ===========================================================================

class TestUserContext:
    def test_dnd_window_logic(self) -> None:
        # User DND is active overnight from 22:00 to 07:00
        user = UserContext(
            user_id="u_001",
            do_not_disturb_window=("22:00", "07:00"),
            messages_opened_30d=5,
            messages_replied_30d=1,
            notifications_dismissed_30d=2,
            messages_reported_30d=0,
            daily_avg_notifications_sent=3.5,
            daily_avg_notifications_dismissed=1.2,
        )
        # Inside DND: 23:00, 06:59
        assert user.is_in_dnd(datetime(2026, 7, 30, 23, 0)) is True
        assert user.is_in_dnd(datetime(2026, 7, 30, 6, 59)) is True
        # Outside DND: 07:01, 21:59
        assert user.is_in_dnd(datetime(2026, 7, 30, 7, 1)) is False
        assert user.is_in_dnd(datetime(2026, 7, 30, 21, 59)) is False

        # Daytime DND: 13:00 to 15:00
        user_midday = UserContext(
            user_id="u_001",
            do_not_disturb_window=("13:00", "15:00"),
            messages_opened_30d=5,
            messages_replied_30d=1,
            notifications_dismissed_30d=2,
            messages_reported_30d=0,
            daily_avg_notifications_sent=3.5,
            daily_avg_notifications_dismissed=1.2,
        )
        assert user_midday.is_in_dnd(datetime(2026, 7, 30, 14, 0)) is True
        assert user_midday.is_in_dnd(datetime(2026, 7, 30, 12, 59)) is False
        assert user_midday.is_in_dnd(datetime(2026, 7, 30, 15, 1)) is False

        # No DND window
        user_no_dnd = UserContext(
            user_id="u_001",
            do_not_disturb_window=None,
            messages_opened_30d=5,
            messages_replied_30d=1,
            notifications_dismissed_30d=2,
            messages_reported_30d=0,
            daily_avg_notifications_sent=3.5,
            daily_avg_notifications_dismissed=1.2,
        )
        assert user_no_dnd.is_in_dnd(datetime(2026, 7, 30, 23, 0)) is False

    def test_serialization_roundtrip(self) -> None:
        user = UserContext(
            user_id="u_001",
            do_not_disturb_window=("22:00", "07:00"),
            messages_opened_30d=5,
            messages_replied_30d=1,
            notifications_dismissed_30d=2,
            messages_reported_30d=0,
            daily_avg_notifications_sent=3.5,
            daily_avg_notifications_dismissed=1.2,
            opted_out_businesses=frozenset({"business_001"}),
            allows_promo_businesses=frozenset({"business_002"}),
        )
        serialized = user.to_dict()
        assert serialized["opted_out_businesses"] == ["business_001"]
        
        deserialized = UserContext.from_dict(serialized)
        assert user == deserialized


# ===========================================================================
# 3. ConversationContext
# ===========================================================================

class TestConversationContext:
    def test_helper_properties(self) -> None:
        # Group admin
        g_ctx = ConversationContext(
            conversation_type="group",
            group_id="g_001",
            group_name="Family",
            group_type="family",
            user_role_in_group="admin",
            group_muted_by_user=True,
        )
        assert g_ctx.is_group_admin is True
        assert g_ctx.is_verified_business is False

        # Verified Business
        b_ctx = ConversationContext(
            conversation_type="business",
            business_id="biz_001",
            business_verified=True,
            business_official_domain="whatsapp.com",
            business_domain_used_by_sender="whatsapp.com",
        )
        assert b_ctx.is_verified_business is True
        assert b_ctx.domain_matches is True

        # Unmatched domain business
        b_bad_domain = ConversationContext(
            conversation_type="business",
            business_id="biz_002",
            business_verified=False,
            business_official_domain="whatsapp.com",
            business_domain_used_by_sender="suspicious.com",
        )
        assert b_bad_domain.domain_matches is False

    def test_serialization_roundtrip(self) -> None:
        b_ctx = ConversationContext(
            conversation_type="business",
            business_id="biz_001",
            business_verified=True,
            business_official_domain="whatsapp.com",
            business_domain_used_by_sender="whatsapp.com",
            ubh_why_user_knows_account="order",
            ubh_last_activity_at=datetime(2026, 7, 25, 12, 0),
            ubh_allows_promotions=False,
        )
        serialized = b_ctx.to_dict()
        assert serialized["ubh_last_activity_at"] == "2026-07-25T12:00:00"

        deserialized = ConversationContext.from_dict(serialized)
        assert b_ctx == deserialized


# ===========================================================================
# 4. RoutingFeatures
# ===========================================================================

class TestRoutingFeatures:
    def test_serialization_roundtrip(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_002",
            created_at=datetime(2026, 7, 30, 22, 19),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        user = UserContext(
            user_id="u_001",
            do_not_disturb_window=None,
            messages_opened_30d=5,
            messages_replied_30d=1,
            notifications_dismissed_30d=2,
            messages_reported_30d=0,
            daily_avg_notifications_sent=3.5,
            daily_avg_notifications_dismissed=1.2,
        )
        conv = ConversationContext(conversation_type="personal", sender_user_id="u_002")
        
        features = RoutingFeatures(
            message=msg,
            user=user,
            conversation=conv,
            ocr_text="SALE POSTER",
            asr_transcript="",
            resolved_media_path="/path/to/media.jpg",
            has_valid_media=True,
            matched_evidence_ids=("msg_0001", "msg_0002"),
            is_dnd_active=False,
            historical_open_rate=0.85,
        )

        serialized = features.to_dict()
        deserialized = RoutingFeatures.from_dict(serialized)
        assert features == deserialized


# ===========================================================================
# 5. EvidenceRecord
# ===========================================================================

class TestEvidenceRecord:
    def test_serialization_roundtrip(self) -> None:
        ev = EvidenceRecord(
            message_id="message_0001",
            relevance_score=0.92,
            matching_criteria="content_similarity",
            created_at=datetime(2026, 7, 29, 10, 0),
            message_text="headsup Tower B valve is open",
        )
        serialized = ev.to_dict()
        assert serialized["message_id"] == "message_0001"
        assert serialized["relevance_score"] == 0.92

        deserialized = EvidenceRecord.from_dict(serialized)
        assert ev == deserialized


# ===========================================================================
# 6. DecisionExplanation
# ===========================================================================

class TestDecisionExplanation:
    def test_rendered_reason(self) -> None:
        # Happy path rendering
        exp = DecisionExplanation(
            reason_template="A trusted admin sent an update to {group_name}.",
            template_variables={"group_name": "Mehra Family"},
        )
        assert exp.rendered_reason == "A trusted admin sent an update to Mehra Family."

        # Template variables missing (fails gracefully to template string)
        exp_bad = DecisionExplanation(
            reason_template="A trusted admin sent an update to {group_name}.",
            template_variables={},
        )
        assert exp_bad.rendered_reason == "A trusted admin sent an update to {group_name}."


# ===========================================================================
# 7. Prediction
# ===========================================================================

class TestPrediction:
    def test_serialization_roundtrip(self) -> None:
        pred = Prediction(
            message_id="msg_001",
            action="notify",
            message_type="urgent",
            reason="A trusted admin update",
            confidence=0.89234,
            evidence_message_ids=("message_0001", "message_0002"),
        )
        serialized = pred.to_dict()
        deserialized = Prediction.from_dict(serialized)
        assert pred == deserialized

    def test_csv_formatting(self) -> None:
        pred = Prediction(
            message_id="msg_001",
            action="notify",
            message_type="urgent",
            reason="A trusted admin update",
            confidence=0.89234,
            evidence_message_ids=("message_0001", "message_0002"),
        )
        csv_row = pred.to_csv_row()
        assert csv_row["message_id"] == "msg_001"
        assert csv_row["action"] == "notify"
        # Verify confidence rounded to 2 decimal places string
        assert csv_row["confidence"] == "0.89"
        # Verify evidence joined with semicolons
        assert csv_row["evidence_message_ids"] == "message_0001;message_0002"

        # None evidence
        pred_no_ev = Prediction(
            message_id="msg_002",
            action="mute",
            message_type="spam",
            reason="Repeated spam",
            confidence=0.95,
            evidence_message_ids=(),
        )
        csv_row_no_ev = pred_no_ev.to_csv_row()
        assert csv_row_no_ev["evidence_message_ids"] == "none"
