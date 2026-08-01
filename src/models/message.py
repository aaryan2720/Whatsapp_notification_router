"""
src/models/message.py
---------------------
Defines the MessageRecord domain model.

This model is a strongly typed, immutable representation of a single message,
reusing the raw values normalized by Module 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.utils.types import ConversationType, MediaType


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """
    Canonical internal model representing a single WhatsApp message.

    This covers both incoming messages (messages.csv) and historical
    messages (message_history.csv).
    """

    message_id: str
    user_id: str
    conversation_type: ConversationType
    group_id: str
    business_id: str
    sender_user_id: str
    created_at: datetime | None
    message_text: str
    media_type: MediaType
    media_id: str
    forwarded_count: int

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MessageRecord:
        """
        Create a MessageRecord from a normalized dictionary.

        Raises KeyError if a required field is missing.
        """
        return cls(
            message_id=row["message_id"],
            user_id=row["user_id"],
            conversation_type=row["conversation_type"],
            group_id=row.get("group_id", ""),
            business_id=row.get("business_id", ""),
            sender_user_id=row.get("sender_user_id", ""),
            created_at=row["created_at"],
            message_text=row.get("message_text", ""),
            media_type=row.get("media_type", ""),
            media_id=row.get("media_id", ""),
            forwarded_count=row.get("forwarded_count", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize MessageRecord back to a dictionary."""
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "conversation_type": self.conversation_type,
            "group_id": self.group_id,
            "business_id": self.business_id,
            "sender_user_id": self.sender_user_id,
            "created_at": self.created_at,
            "message_text": self.message_text,
            "media_type": self.media_type,
            "media_id": self.media_id,
            "forwarded_count": self.forwarded_count,
        }
