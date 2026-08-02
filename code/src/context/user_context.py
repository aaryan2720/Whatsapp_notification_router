"""
src/context/user_context.py
---------------------------
Constructs personalized UserContext domain models from the loaded DatasetBundle.

Provides the primary builder function:
    build_user_context(user_id: str, bundle: DatasetBundle) -> UserContext

Handles:
  - Retrieval of raw user metrics from the bundle.
  - Aggregation of daily notification loads to compute averages.
  - Resolution of business preferences (opt-outs, allowed promos).
  - Graceful fallback for new/sparse-history users using global dataset averages.
"""

from __future__ import annotations

from src.loader.csv_loader import DatasetBundle
from src.models.context import UserContext
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# Module-level cache to store computed averages per DatasetBundle instance id
_GLOBAL_AVERAGES_CACHE: dict[int, dict[str, float]] = {}


def _compute_global_averages(bundle: DatasetBundle) -> dict[str, float]:
    """
    Compute average user metrics over the entire dataset for fallback purposes.
    Caches results by bundle ID to prevent redundant scans.
    """
    bundle_id = id(bundle)
    if bundle_id in _GLOBAL_AVERAGES_CACHE:
        return _GLOBAL_AVERAGES_CACHE[bundle_id]

    users = bundle.users
    summaries = bundle.daily_notification_summary

    avg_opened = 0.0
    avg_replied = 0.0
    avg_dismissed = 0.0
    avg_reported = 0.0

    if users:
        avg_opened = sum(u["messages_opened_30d"] for u in users) / len(users)
        avg_replied = sum(u["messages_replied_30d"] for u in users) / len(users)
        avg_dismissed = sum(u["notifications_dismissed_30d"] for u in users) / len(users)
        avg_reported = sum(u["messages_reported_30d"] for u in users) / len(users)

    avg_sent_daily = 0.0
    avg_dismiss_daily = 0.0
    if summaries:
        avg_sent_daily = sum(s["notifications_sent"] for s in summaries) / len(summaries)
        avg_dismiss_daily = sum(s["notifications_dismissed"] for s in summaries) / len(summaries)

    averages = {
        "messages_opened_30d": avg_opened,
        "messages_replied_30d": avg_replied,
        "notifications_dismissed_30d": avg_dismissed,
        "messages_reported_30d": avg_reported,
        "daily_avg_notifications_sent": avg_sent_daily,
        "daily_avg_notifications_dismissed": avg_dismiss_daily,
    }
    _GLOBAL_AVERAGES_CACHE[bundle_id] = averages
    return averages


def build_user_context(user_id: str, bundle: DatasetBundle) -> UserContext:
    """
    Build a UserContext object for the specified user_id.

    Reuses indexes in the DatasetBundle for O(1) retrieval.
    If the user does not exist in the dataset (sparse-history fallback),
    global averages are computed and filled in to ensure robust downstream decisions.
    """
    # 1. Resolve raw user stats
    raw_user = bundle.users_by_id.get(user_id)
    
    if raw_user:
        dnd = raw_user.get("do_not_disturb_window")
        opened = raw_user["messages_opened_30d"]
        replied = raw_user["messages_replied_30d"]
        dismissed = raw_user["notifications_dismissed_30d"]
        reported = raw_user["messages_reported_30d"]
    else:
        # Fallback for new / unknown user
        logger.debug("Sparse/unknown user %s; calculating fallback averages", user_id)
        averages = _compute_global_averages(bundle)
        dnd = None
        opened = int(averages["messages_opened_30d"])
        replied = int(averages["messages_replied_30d"])
        dismissed = int(averages["notifications_dismissed_30d"])
        reported = int(averages["messages_reported_30d"])

    # 2. Compute daily notification summary averages
    user_summaries = bundle.daily_summary_by_user.get(user_id, [])
    if user_summaries:
        daily_sent = sum(s["notifications_sent"] for s in user_summaries) / len(user_summaries)
        daily_dismissed = sum(s["notifications_dismissed"] for s in user_summaries) / len(user_summaries)
    else:
        # Fallback to global average if user has no daily summaries
        averages = _compute_global_averages(bundle)
        daily_sent = averages["daily_avg_notifications_sent"]
        daily_dismissed = averages["daily_avg_notifications_dismissed"]

    # 3. Resolve business opt-in/opt-out preferences
    opted_out = set()
    allows_promo = set()

    # Get user business histories from bundle O(1) index
    user_ubh = bundle.ubh_by_user.get(user_id, [])
    for ub in user_ubh:
        bid = ub["business_id"]
        # Explicit opt-out logic
        if not ub["allows_promotions"] or ub["promotions_opted_out_at"] is not None:
            opted_out.add(bid)
        else:
            allows_promo.add(bid)

    return UserContext(
        user_id=user_id,
        do_not_disturb_window=dnd,
        messages_opened_30d=opened,
        messages_replied_30d=replied,
        notifications_dismissed_30d=dismissed,
        messages_reported_30d=reported,
        daily_avg_notifications_sent=daily_sent,
        daily_avg_notifications_dismissed=daily_dismissed,
        opted_out_businesses=frozenset(opted_out),
        allows_promo_businesses=frozenset(allows_promo),
    )
