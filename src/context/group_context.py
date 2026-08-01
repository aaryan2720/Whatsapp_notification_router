"""
src/context/group_context.py
----------------------------
Extracts and computes group-related conversation context fields.
"""

from __future__ import annotations

from typing import Any
from src.loader.csv_loader import DatasetBundle


def build_group_context_fields(
    user_id: str,
    group_id: str,
    bundle: DatasetBundle,
) -> dict[str, Any]:
    """
    Extract group metadata and user-group relationship signals.

    Calculates:
      - member/admin count
      - group activity score (normalized messages per member)
      - group muted by user
      - user's role in the group
    """
    fields: dict[str, Any] = {
        "group_id": group_id,
        "group_name": "Unknown Group",
        "group_type": "generic",
        "group_member_count": 0,
        "group_admin_count": 0,
        "group_muted_by_user": False,
        "user_role_in_group": "",
        "group_activity_score": 0.0,
    }

    if not group_id:
        return fields

    # 1. Resolve raw group metadata
    group = bundle.groups_by_id.get(group_id)
    if group:
        fields["group_name"] = group["group_name"]
        fields["group_type"] = group["group_type"]
        fields["group_member_count"] = group["member_count"]
        fields["group_admin_count"] = group["admin_count"]
        # Normalized activity score: messages sent in group in past 30d per member
        mc = group["member_count"]
        if mc > 0:
            fields["group_activity_score"] = float(group["messages_30d"] / mc)

    # 2. Resolve user's relationship to the group
    member_record = bundle.group_member_by_user_and_group.get((user_id, group_id))
    if member_record:
        fields["group_muted_by_user"] = member_record["group_muted_by_user"]
        fields["user_role_in_group"] = member_record["role"]

    return fields
