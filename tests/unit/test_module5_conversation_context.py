"""
tests/unit/test_module5_conversation_context.py
----------------------------------------------
Unit tests for Module 5: Conversation Context Builder.

Covers:
  - Personal conversations (known sender vs unknown sender)
  - Group conversations (role in group, muted state, priority hints)
  - Business conversations (verified, categories, DND/phishing impact)
  - Domain mismatch & spoofing/phishing detection (mismatch = 0.95 phishing probability)
  - Short domain ages suspiciousness
  - Sparse metadata fallbacks
  - Determinism of outputs
  - Regression check: verifying full dataset loading & context builders
"""

from __future__ import annotations

import sys
from datetime import datetime, date
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.loader.csv_loader import DatasetBundle
from src.models import MessageRecord, ConversationContext
from src.context.conversation_context import build_conversation_context


# ===========================================================================
# 1. Mock Helper
# ===========================================================================

def _create_mock_bundle(
    groups: list[dict] | None = None,
    members: list[dict] | None = None,
    businesses: list[dict] | None = None,
    ubh: list[dict] | None = None,
    history: list[dict] | None = None,
    events: list[dict] | None = None,
) -> DatasetBundle:
    """Create a mock DatasetBundle specifically for conversation context testing."""
    from src.loader.csv_loader import _build_index, _build_multi_index

    g_list = groups or []
    m_list = members or []
    b_list = businesses or []
    ubh_list = ubh or []
    h_list = history or []
    e_list = events or []

    return DatasetBundle(
        messages=(),
        users=(),
        groups=tuple(g_list),
        group_members=tuple(m_list),
        business_accounts=tuple(b_list),
        user_business_history=tuple(ubh_list),
        message_history=tuple(h_list),
        message_events=tuple(e_list),
        images=(),
        voice_notes=(),
        daily_notification_summary=(),
        users_by_id={},
        groups_by_id=_build_index(g_list, "group_id"),
        business_by_id=_build_index(b_list, "business_id"),
        images_by_id={},
        voice_notes_by_id={},
        history_by_message_id=_build_index(h_list, "message_id"),
        group_members_by_user=_build_multi_index(m_list, "user_id"),
        group_members_by_group=_build_multi_index(m_list, "group_id"),
        group_member_by_user_and_group=_build_index(m_list, "user_id", "group_id"),
        ubh_by_user_and_business=_build_index(ubh_list, "user_id", "business_id"),
        ubh_by_user=_build_multi_index(ubh_list, "user_id"),
        events_by_message_id=_build_index(e_list, "message_id"),
        history_by_user=_build_multi_index(h_list, "user_id"),
        daily_summary_by_user={},
        known_user_ids=frozenset(),
        known_group_ids=frozenset(g["group_id"] for g in g_list),
        known_business_ids=frozenset(b["business_id"] for b in b_list),
    )


# ===========================================================================
# 2. Test Cases
# ===========================================================================

class TestConversationContextBuilder:
    def test_personal_conversation_unknown_sender(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_unknown",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        bundle = _create_mock_bundle()

        ctx = build_conversation_context(msg, bundle)

        assert ctx.conversation_type == "personal"
        assert ctx.sender_user_id == "u_unknown"
        assert ctx.sender_trust == 0.5  # neutral default
        assert ctx.relationship_strength == 0.0
        assert ctx.priority_hint == "normal"

    def test_personal_conversation_known_sender(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        history = [
            {"message_id": "h_1", "user_id": "u_001", "sender_user_id": "u_friend", "conversation_type": "personal"},
            {"message_id": "h_2", "user_id": "u_001", "sender_user_id": "u_friend", "conversation_type": "personal"},
        ]
        events = [
            {"message_id": "h_1", "user_id": "u_001", "message_opened": True, "message_replied": True},
            {"message_id": "h_2", "user_id": "u_001", "message_opened": True, "message_replied": False},
        ]
        bundle = _create_mock_bundle(history=history, events=events)

        ctx = build_conversation_context(msg, bundle)

        assert ctx.sender_trust == 1.0  # 2 opened out of 2
        assert ctx.relationship_strength == 0.5  # 1 replied out of 2
        assert ctx.priority_hint == "normal"  # normal priority (strength <= 0.50)

    def test_group_conversation_muted_vs_admin(self) -> None:
        # 1. Muted group
        msg_muted = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="group",
            group_id="g_001",
            business_id="",
            sender_user_id="u_sender",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        groups = [
            {"group_id": "g_001", "group_name": "Classmates", "group_type": "friends", "member_count": 20, "admin_count": 1, "messages_30d": 100}
        ]
        members = [
            {"group_id": "g_001", "user_id": "u_001", "role": "member", "group_muted_by_user": True}
        ]
        bundle = _create_mock_bundle(groups=groups, members=members)

        ctx_muted = build_conversation_context(msg_muted, bundle)
        assert ctx_muted.group_muted_by_user is True
        assert ctx_muted.priority_hint == "low"  # muted groups get low priority hint

        # 2. Administrative work group (unmuted)
        members_admin = [
            {"group_id": "g_001", "user_id": "u_001", "role": "admin", "group_muted_by_user": False}
        ]
        groups_work = [
            {"group_id": "g_001", "group_name": "Work Board", "group_type": "work", "member_count": 10, "admin_count": 2, "messages_30d": 200}
        ]
        bundle_admin = _create_mock_bundle(groups=groups_work, members=members_admin)

        ctx_admin = build_conversation_context(msg_muted, bundle_admin)
        assert ctx_admin.is_group_admin is True
        assert ctx_admin.priority_hint == "urgent"  # work admin is urgent
        assert ctx_admin.group_activity_score == 20.0  # 200 messages / 10 members

    def test_business_conversation_verified_clean(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="business",
            group_id="",
            business_id="biz_verified",
            sender_user_id="",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="your delivery is here",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        businesses = [
            {
                "business_id": "biz_verified",
                "display_name": "Amazon",
                "brand_name": "Amazon",
                "category": "ecommerce_delivery",
                "verified": True,
                "official_domain": "amazon.com",
                "domain_used_by_sender": "amazon.com",
                "account_age_days": 1000,
                "messages_sent_30d": 5000,
                "user_reports_30d": 0,
                "domain_used_by_sender_age_days": 1000,
            }
        ]
        bundle = _create_mock_bundle(businesses=businesses)

        ctx = build_conversation_context(msg, bundle)

        assert ctx.is_verified_business is True
        assert ctx.domain_matches is True
        assert ctx.phishing_probability == 0.0
        assert ctx.sender_trust == 0.70  # default verified trust
        assert ctx.priority_hint == "urgent"  # verified ecommerce_delivery is urgent

    def test_business_conversation_domain_mismatch_phishing(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="business",
            group_id="",
            business_id="biz_sus",
            sender_user_id="",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="enter your OTP at this link",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        businesses = [
            {
                "business_id": "biz_sus",
                "display_name": "Netflix India",
                "brand_name": "Netflix",
                "category": "entertainment",
                "verified": False,
                "official_domain": "netflix.com",
                "domain_used_by_sender": "netflix-update.in",  # suspicious mismatch!
                "account_age_days": 100,
                "messages_sent_30d": 5000,
                "user_reports_30d": 5,
                "domain_used_by_sender_age_days": 10,  # brand new sender domain
            }
        ]
        bundle = _create_mock_bundle(businesses=businesses)

        ctx = build_conversation_context(msg, bundle)

        assert ctx.domain_matches is False
        assert ctx.phishing_probability == 0.95  # critical mismatch indicator
        assert ctx.sender_trust == 0.05
        assert ctx.priority_hint == "low"  # high phishing score sets priority to low

    def test_business_conversation_short_domain_age_suspicious(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="business",
            group_id="",
            business_id="biz_new_domain",
            sender_user_id="",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        businesses = [
            {
                "business_id": "biz_new_domain",
                "display_name": "Brand New Shop",
                "brand_name": "Shop",
                "category": "shopping",
                "verified": False,
                "official_domain": "shop.com",
                "domain_used_by_sender": "shop.com",  # domain matches official
                "account_age_days": 15,
                "messages_sent_30d": 20,
                "user_reports_30d": 0,
                "domain_used_by_sender_age_days": 15,  # sender domain only 15 days old
            }
        ]
        bundle = _create_mock_bundle(businesses=businesses)

        ctx = build_conversation_context(msg, bundle)

        # Domain matches, but age is very young (< 30 days)
        assert ctx.domain_matches is True
        assert ctx.phishing_probability == 0.80  # age triggers alert
        assert ctx.sender_trust == 0.20

    def test_sparse_metadata_fallbacks(self) -> None:
        # Message has business_id but business is not in business_accounts.csv
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="business",
            group_id="",
            business_id="biz_ghost",
            sender_user_id="",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        bundle = _create_mock_bundle()

        ctx = build_conversation_context(msg, bundle)

        assert ctx.business_id == "biz_ghost"
        assert ctx.business_display_name == "Unknown Business"
        assert ctx.business_verified is False
        assert ctx.phishing_probability == 0.0
        assert ctx.sender_trust == 0.5  # neutral default

    def test_determinism(self) -> None:
        msg = MessageRecord(
            message_id="msg_001",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        bundle = _create_mock_bundle()
        
        ctx1 = build_conversation_context(msg, bundle)
        ctx2 = build_conversation_context(msg, bundle)
        
        assert ctx1 == ctx2


# ===========================================================================
# 3. Regression test / Full Dataset load check
# ===========================================================================

class TestRealConversationContextSmoke:
    def test_real_messages_context_generation(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        
        # Pull real messages
        real_msgs = bundle.messages
        assert len(real_msgs) > 0
        
        # Test context construction for first 10 messages
        for m_row in real_msgs[:10]:
            msg = MessageRecord.from_row(m_row)
            ctx = build_conversation_context(msg, bundle)
            assert isinstance(ctx, ConversationContext)
            assert ctx.conversation_type == msg.conversation_type
            assert ctx.sender_trust >= 0.0
