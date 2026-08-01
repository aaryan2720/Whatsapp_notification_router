"""
src/context/conversation_context.py
-----------------------------------
Orchestrates construction of the ConversationContext domain model.

Public API:
    build_conversation_context(message: MessageRecord, bundle: DatasetBundle) -> ConversationContext
"""

from __future__ import annotations

from typing import Any
from src.loader.csv_loader import DatasetBundle
from src.models.message import MessageRecord
from src.models.context import ConversationContext
from src.context.group_context import build_group_context_fields
from src.context.business_context import build_business_context_fields


def build_conversation_context(
    message: MessageRecord,
    bundle: DatasetBundle,
) -> ConversationContext:
    """
    Construct a complete ConversationContext for an incoming message.

    Extracts details for the conversation type (group, business, or personal)
    and computes sender trust, relationship strength, phishing markers, and
    routing priority hints.
    """
    user_id = message.user_id
    ctype = message.conversation_type

    # Start with base default properties
    fields: dict[str, Any] = {
        "conversation_type": ctype,
        "sender_user_id": message.sender_user_id,
        "sender_trust": 0.5,
        "relationship_strength": 0.0,
        "group_activity_score": 0.0,
        "phishing_probability": 0.0,
        "priority_hint": "normal",
    }

    # -----------------------------------------------------------------------
    # 1. Group Conversations
    # -----------------------------------------------------------------------
    if ctype == "group":
        group_fields = build_group_context_fields(user_id, message.group_id, bundle)
        fields.update(group_fields)

        # Priority Hints for Groups
        if fields["group_muted_by_user"]:
            fields["priority_hint"] = "low"
        else:
            gtype = fields["group_type"]
            # Higher priority for work or administrative groups
            if gtype in {"work", "school_parents", "society"}:
                fields["priority_hint"] = "urgent" if fields["user_role_in_group"] == "admin" else "normal"
            else:
                fields["priority_hint"] = "normal"

        # Sender trust inside group (sender relative to user history)
        sender = message.sender_user_id
        if sender:
            hist_rates = _get_sender_history_rates(user_id, sender, bundle)
            fields["sender_trust"] = hist_rates["sender_trust"]
            fields["relationship_strength"] = hist_rates["relationship_strength"]

    # -----------------------------------------------------------------------
    # 2. Business Senders
    # -----------------------------------------------------------------------
    elif ctype == "business":
        biz_fields = build_business_context_fields(user_id, message.business_id, bundle)
        fields.update(biz_fields)

        # Priority Hints for Businesses
        if fields["phishing_probability"] > 0.70 or not fields["ubh_allows_promotions"]:
            fields["priority_hint"] = "low"
        elif fields["business_verified"]:
            cat = fields["business_category"]
            if cat in {"ecommerce_delivery", "banking", "finance"}:
                fields["priority_hint"] = "urgent"
            else:
                fields["priority_hint"] = "normal"
        else:
            fields["priority_hint"] = "normal"

    # -----------------------------------------------------------------------
    # 3. Personal Conversations
    # -----------------------------------------------------------------------
    elif ctype == "personal":
        sender = message.sender_user_id
        if sender:
            hist_rates = _get_sender_history_rates(user_id, sender, bundle)
            fields["sender_trust"] = hist_rates["sender_trust"]
            fields["relationship_strength"] = hist_rates["relationship_strength"]

            # Priority Hints for Personal Chats
            if hist_rates["history_count"] == 0:
                fields["priority_hint"] = "normal"  # Unknown sender
            elif hist_rates["relationship_strength"] > 0.50:
                fields["priority_hint"] = "urgent"  # Strong relationship
            elif hist_rates["sender_open_rate"] < 0.20:
                fields["priority_hint"] = "low"  # Almost always ignored
            else:
                fields["priority_hint"] = "normal"

    return ConversationContext(
        conversation_type=fields["conversation_type"],
        group_id=fields.get("group_id", ""),
        group_name=fields.get("group_name", ""),
        group_type=fields.get("group_type", ""),
        group_member_count=fields.get("group_member_count", 0),
        group_admin_count=fields.get("group_admin_count", 0),
        group_muted_by_user=fields.get("group_muted_by_user", False),
        user_role_in_group=fields.get("user_role_in_group", ""),
        business_id=fields.get("business_id", ""),
        business_display_name=fields.get("business_display_name", ""),
        business_brand_name=fields.get("business_brand_name", ""),
        business_category=fields.get("business_category", ""),
        business_verified=fields.get("business_verified", False),
        business_official_domain=fields.get("business_official_domain", ""),
        business_domain_used_by_sender=fields.get("business_domain_used_by_sender", ""),
        business_account_age_days=fields.get("business_account_age_days", 0),
        business_messages_sent_30d=fields.get("business_messages_sent_30d", 0),
        business_user_reports_30d=fields.get("business_user_reports_30d", 0),
        business_domain_used_by_sender_age_days=fields.get("business_domain_used_by_sender_age_days", 0),
        ubh_why_user_knows_account=fields.get("ubh_why_user_knows_account", ""),
        ubh_last_activity_at=fields.get("ubh_last_activity_at"),
        ubh_allows_promotions=fields.get("ubh_allows_promotions", True),
        ubh_activity_count_180d=fields.get("ubh_activity_count_180d", 0),
        ubh_messages_opened_30d=fields.get("ubh_messages_opened_30d", 0),
        ubh_messages_dismissed_30d=fields.get("ubh_messages_dismissed_30d", 0),
        ubh_messages_replied_30d=fields.get("ubh_messages_replied_30d", 0),
        sender_user_id=fields.get("sender_user_id", ""),
        sender_trust=fields.get("sender_trust", 0.5),
        relationship_strength=fields.get("relationship_strength", 0.0),
        group_activity_score=fields.get("group_activity_score", 0.0),
        phishing_probability=fields.get("phishing_probability", 0.0),
        priority_hint=fields.get("priority_hint", "normal"),
    )


def _get_sender_history_rates(
    user_id: str,
    sender_id: str,
    bundle: DatasetBundle,
) -> dict[str, Any]:
    """
    Calculate interaction rates between a user and a personal sender using historical logs.
    """
    history = bundle.history_by_user.get(user_id, [])
    # Filter messages received from this sender
    sender_msgs = [m for m in history if m["sender_user_id"] == sender_id]
    count = len(sender_msgs)

    if count == 0:
        return {
            "history_count": 0,
            "sender_open_rate": 0.0,
            "sender_trust": 0.5,  # neutral default
            "relationship_strength": 0.0,
        }

    opened = 0
    replied = 0

    for msg in sender_msgs:
        ev = bundle.events_by_message_id.get(msg["message_id"])
        if ev:
            if ev.get("message_opened"):
                opened += 1
            if ev.get("message_replied"):
                replied += 1

    open_rate = opened / count
    reply_rate = replied / count

    return {
        "history_count": count,
        "sender_open_rate": open_rate,
        # Trust is open rate; if they report the sender, it goes down.
        # Check if the user has reported any message from this sender.
        "sender_trust": open_rate,
        "relationship_strength": reply_rate,
    }
