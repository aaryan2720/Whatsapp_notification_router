"""
src/utils/types.py
------------------
Shared type aliases and lightweight sentinel values used across all modules.

Keeps type annotations consistent without pulling in heavy data model imports.
These are pure Python — no third-party dependencies.
"""

from __future__ import annotations

from typing import Literal, TypeAlias


# ---------------------------------------------------------------------------
# Core domain literals
# ---------------------------------------------------------------------------

Action: TypeAlias = Literal["notify", "digest", "mute"]
"""The three allowed routing decisions."""

MessageType: TypeAlias = Literal[
    "personal",
    "urgent",
    "event",
    "payment",
    "business_update",
    "promotion",
    "greeting",
    "forward",
    "spam",
    "scam",
    "unknown",
]
"""The eleven allowed message categories."""

ConversationType: TypeAlias = Literal["personal", "group", "business"]
"""WhatsApp conversation type."""

MediaType: TypeAlias = Literal["image", "voice", ""]
"""Supported media types. Empty string means text-only."""


# ---------------------------------------------------------------------------
# Allowed value sets (for validation at runtime)
# ---------------------------------------------------------------------------

ALLOWED_ACTIONS: frozenset[str] = frozenset({"notify", "digest", "mute"})

ALLOWED_MESSAGE_TYPES: frozenset[str] = frozenset(
    {
        "personal",
        "urgent",
        "event",
        "payment",
        "business_update",
        "promotion",
        "greeting",
        "forward",
        "spam",
        "scam",
        "unknown",
    }
)

ALLOWED_CONVERSATION_TYPES: frozenset[str] = frozenset({"personal", "group", "business"})

ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset({"image", "voice", ""})


# ---------------------------------------------------------------------------
# Output column contract
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS: tuple[str, ...] = (
    "message_id",
    "action",
    "message_type",
    "reason",
    "confidence",
    "evidence_message_ids",
)
"""Exact required column order for output.csv. Must not be changed."""

NO_EVIDENCE: str = "none"
"""Sentinel value written to evidence_message_ids when no history exists."""


# ---------------------------------------------------------------------------
# Confidence bounds
# ---------------------------------------------------------------------------

CONFIDENCE_MIN: float = 0.0
CONFIDENCE_MAX: float = 1.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_valid_action(value: str) -> bool:
    return value in ALLOWED_ACTIONS


def is_valid_message_type(value: str) -> bool:
    return value in ALLOWED_MESSAGE_TYPES


def is_valid_confidence(value: float) -> bool:
    return CONFIDENCE_MIN <= value <= CONFIDENCE_MAX
