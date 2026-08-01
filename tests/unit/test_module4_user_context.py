"""
tests/unit/test_module4_user_context.py
----------------------------------------
Unit tests for Module 4: User Context Builder.

Covers:
  - UserContext computed metrics (reply ratio, dismiss rate, report tendency)
  - build_user_context with active user (heavy user, normal DND, business preferences)
  - build_user_context fallback for sparse-history users
  - compute_user_historical_rates with various history and reactions
  - compute_user_historical_rates fallback for no history
  - Determinism of outputs
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
from src.models.context import UserContext
from src.context.user_context import build_user_context
from src.context.user_aggregates import compute_user_historical_rates


# ===========================================================================
# 1. Test Setup / Fixture Builders
# ===========================================================================

def _create_mock_bundle(
    users: list[dict] | None = None,
    daily: list[dict] | None = None,
    ubh: list[dict] | None = None,
    history: list[dict] | None = None,
    events: list[dict] | None = None,
) -> DatasetBundle:
    """Create a minimal mock DatasetBundle with populated indexes."""
    from src.loader.csv_loader import _build_index, _build_multi_index

    # Use defaults if None
    u_list = users or []
    d_list = daily or []
    ubh_list = ubh or []
    h_list = history or []
    e_list = events or []

    # Sort daily summaries by date per user (as done in load_all_datasets)
    d_list.sort(key=lambda r: (r["user_id"], r["date"] or date.min))

    return DatasetBundle(
        messages=(),
        users=tuple(u_list),
        groups=(),
        group_members=(),
        business_accounts=(),
        user_business_history=tuple(ubh_list),
        message_history=tuple(h_list),
        message_events=tuple(e_list),
        images=(),
        voice_notes=(),
        daily_notification_summary=tuple(d_list),
        users_by_id=_build_index(u_list, "user_id"),
        groups_by_id={},
        business_by_id={},
        images_by_id={},
        voice_notes_by_id={},
        history_by_message_id=_build_index(h_list, "message_id"),
        group_members_by_user={},
        group_members_by_group={},
        group_member_by_user_and_group={},
        ubh_by_user_and_business=_build_index(ubh_list, "user_id", "business_id"),
        ubh_by_user=_build_multi_index(ubh_list, "user_id"),
        events_by_message_id=_build_index(e_list, "message_id"),
        history_by_user=_build_multi_index(h_list, "user_id"),
        daily_summary_by_user=_build_multi_index(d_list, "user_id"),
        known_user_ids=frozenset(u["user_id"] for u in u_list),
        known_group_ids=frozenset(),
        known_business_ids=frozenset(),
    )


# ===========================================================================
# 2. Test UserContext Computed Metrics
# ===========================================================================

class TestUserContextMetrics:
    def test_computed_properties_happy_path(self) -> None:
        user = UserContext(
            user_id="u_001",
            do_not_disturb_window=None,
            messages_opened_30d=10,
            messages_replied_30d=4,
            notifications_dismissed_30d=5,
            messages_reported_30d=1,
            daily_avg_notifications_sent=2.0,
            daily_avg_notifications_dismissed=0.5,
        )
        assert user.reply_to_open_ratio == 0.4  # 4 / 10
        assert user.notification_dismiss_rate == pytest.approx(0.3333333)  # 5 / 15
        assert user.report_tendency == pytest.approx(0.06666667)  # 1 / 15

    def test_computed_properties_zero_division(self) -> None:
        user = UserContext(
            user_id="u_empty",
            do_not_disturb_window=None,
            messages_opened_30d=0,
            messages_replied_30d=0,
            notifications_dismissed_30d=0,
            messages_reported_30d=0,
            daily_avg_notifications_sent=0.0,
            daily_avg_notifications_dismissed=0.0,
        )
        assert user.reply_to_open_ratio == 0.0
        assert user.notification_dismiss_rate == 0.0
        assert user.report_tendency == 0.0


# ===========================================================================
# 3. Test User Context Builder
# ===========================================================================

class TestUserContextBuilder:
    def test_build_active_user(self) -> None:
        users = [
            {
                "user_id": "u_001",
                "do_not_disturb_window": ("23:00", "06:00"),
                "messages_opened_30d": 40,
                "messages_replied_30d": 20,
                "notifications_dismissed_30d": 10,
                "messages_reported_30d": 2,
            }
        ]
        daily = [
            {"user_id": "u_001", "date": date(2026, 7, 1), "notifications_sent": 10, "notifications_dismissed": 3},
            {"user_id": "u_001", "date": date(2026, 7, 2), "notifications_sent": 20, "notifications_dismissed": 7},
        ]
        ubh = [
            {"user_id": "u_001", "business_id": "biz_allowed", "allows_promotions": True, "promotions_opted_out_at": None},
            {"user_id": "u_001", "business_id": "biz_opted_out", "allows_promotions": False, "promotions_opted_out_at": datetime(2026, 7, 1)},
        ]
        bundle = _create_mock_bundle(users=users, daily=daily, ubh=ubh)

        user_ctx = build_user_context("u_001", bundle)

        assert user_ctx.user_id == "u_001"
        assert user_ctx.do_not_disturb_window == ("23:00", "06:00")
        assert user_ctx.messages_opened_30d == 40
        assert user_ctx.daily_avg_notifications_sent == 15.0  # (10 + 20) / 2
        assert user_ctx.daily_avg_notifications_dismissed == 5.0  # (3 + 7) / 2
        assert user_ctx.opted_out_businesses == frozenset({"biz_opted_out"})
        assert user_ctx.allows_promo_businesses == frozenset({"biz_allowed"})

    def test_build_sparse_history_user_fallback(self) -> None:
        # A bundle with other users to calculate global averages
        users = [
            {
                "user_id": "u_other1",
                "do_not_disturb_window": None,
                "messages_opened_30d": 10,
                "messages_replied_30d": 2,
                "notifications_dismissed_30d": 5,
                "messages_reported_30d": 0,
            },
            {
                "user_id": "u_other2",
                "do_not_disturb_window": None,
                "messages_opened_30d": 20,
                "messages_replied_30d": 4,
                "notifications_dismissed_30d": 5,
                "messages_reported_30d": 2,
            },
        ]
        daily = [
            {"user_id": "u_other1", "date": date(2026, 7, 1), "notifications_sent": 5, "notifications_dismissed": 2},
            {"user_id": "u_other2", "date": date(2026, 7, 1), "notifications_sent": 15, "notifications_dismissed": 8},
        ]
        bundle = _create_mock_bundle(users=users, daily=daily)

        # Build context for an unknown user_id
        user_ctx = build_user_context("u_unknown", bundle)

        # Assert values fall back to global averages
        assert user_ctx.user_id == "u_unknown"
        assert user_ctx.do_not_disturb_window is None
        assert user_ctx.messages_opened_30d == 15  # (10 + 20) / 2
        assert user_ctx.messages_replied_30d == 3  # (2 + 4) / 2
        assert user_ctx.daily_avg_notifications_sent == 10.0  # (5 + 15) / 2
        assert user_ctx.daily_avg_notifications_dismissed == 5.0  # (2 + 8) / 2
        assert len(user_ctx.opted_out_businesses) == 0
        assert len(user_ctx.allows_promo_businesses) == 0

    def test_determinism(self) -> None:
        users = [
            {
                "user_id": "u_001",
                "do_not_disturb_window": ("22:00", "07:00"),
                "messages_opened_30d": 15,
                "messages_replied_30d": 5,
                "notifications_dismissed_30d": 10,
                "messages_reported_30d": 1,
            }
        ]
        bundle = _create_mock_bundle(users=users)
        
        ctx1 = build_user_context("u_001", bundle)
        ctx2 = build_user_context("u_001", bundle)
        
        # Verify two builds on same data return identical objects
        assert ctx1 == ctx2


# ===========================================================================
# 4. Test User Historical Rates
# ===========================================================================

class TestUserHistoricalRates:
    def test_rates_calculation(self) -> None:
        history = [
            {"message_id": "h_01", "user_id": "u_001", "created_at": datetime(2026, 7, 20, 10, 0)},
            {"message_id": "h_02", "user_id": "u_001", "created_at": datetime(2026, 7, 21, 10, 0)},
            {"message_id": "h_03", "user_id": "u_001", "created_at": datetime(2026, 7, 22, 10, 0)},
            {"message_id": "h_04", "user_id": "u_001", "created_at": datetime(2026, 7, 23, 10, 0)},
        ]
        events = [
            {"message_id": "h_01", "user_id": "u_001", "message_opened": True, "message_replied": True, "notification_dismissed": False, "message_reported": False},
            {"message_id": "h_02", "user_id": "u_001", "message_opened": True, "message_replied": False, "notification_dismissed": False, "message_reported": False},
            {"message_id": "h_03", "user_id": "u_001", "message_opened": False, "message_replied": False, "notification_dismissed": True, "message_reported": False},
            {"message_id": "h_04", "user_id": "u_001", "message_opened": False, "message_replied": False, "notification_dismissed": False, "message_reported": True},
        ]
        bundle = _create_mock_bundle(history=history, events=events)

        rates = compute_user_historical_rates("u_001", bundle)

        assert rates["history_count"] == 4.0
        assert rates["historical_open_rate"] == 0.5  # 2 opened out of 4
        assert rates["historical_reply_rate"] == 0.25  # 1 replied out of 4
        assert rates["historical_dismiss_rate"] == 0.25  # 1 dismissed out of 4
        assert rates["historical_report_rate"] == 0.25  # 1 reported out of 4

    def test_no_history_fallback(self) -> None:
        bundle = _create_mock_bundle()
        rates = compute_user_historical_rates("u_no_history", bundle)

        assert rates["history_count"] == 0.0
        assert rates["historical_open_rate"] == 0.0
        assert rates["historical_reply_rate"] == 0.0
        assert rates["historical_dismiss_rate"] == 0.0
        assert rates["historical_report_rate"] == 0.0


# ===========================================================================
# 5. Real dataset smoke test for User Context Builders
# ===========================================================================

class TestRealUserContextSmoke:
    def test_real_users_load(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        
        # Pull a real user_id from the bundle
        real_users = list(bundle.users_by_id.keys())
        assert len(real_users) > 0, "No real users loaded!"
        
        for uid in real_users[:5]:
            user_ctx = build_user_context(uid, bundle)
            assert isinstance(user_ctx, UserContext)
            assert user_ctx.user_id == uid
            
            # Check rates
            rates = compute_user_historical_rates(uid, bundle)
            assert "historical_open_rate" in rates
            assert rates["history_count"] >= 0.0
