"""
src/loader/normalizer.py
------------------------
Data normalization for raw CSV row dicts before they are converted into
typed domain objects.

Responsibilities:
  - Parse and normalise timestamps into a consistent format.
  - Coerce numeric strings to int/float.
  - Normalise boolean fields (0/1 strings → bool).
  - Strip and lowercase identifier fields.
  - Resolve relative media file paths against DATASET_DIR.
  - Produce normalised dicts; never mutate input dicts.

No schema validation happens here — that is schema_validator's job.
No domain objects are created here — that is csv_loader's job.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

# Formats observed in the dataset (ordered: try most specific first)
_DATETIME_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d %H:%M:%S",  # 2026-07-30 22:19:45
    "%Y-%m-%d %H:%M",     # 2026-07-30 22:19  ← most common
    "%Y-%m-%dT%H:%M:%S",  # ISO with T separator
    "%Y-%m-%dT%H:%M",
)

_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",  # 2023-02-11
)


def parse_datetime(raw: str) -> datetime | None:
    """
    Parse a datetime string into a datetime object.

    Returns None for empty strings or unrecognised formats so the caller
    can handle missing timestamps gracefully.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_date(raw: str) -> date | None:
    """
    Parse a date-only string into a date object.

    Returns None for empty or unrecognised strings.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# DND window parsing
# ---------------------------------------------------------------------------

_DND_RE = re.compile(r"^(\d{1,2}:\d{2})-(\d{1,2}:\d{2})$")


def parse_dnd_window(raw: str) -> tuple[str, str] | None:
    """
    Parse a do-not-disturb window like "22:00-07:00".

    Returns (start_hhmm, end_hhmm) or None if empty / malformed.
    """
    if not raw or not raw.strip():
        return None
    m = _DND_RE.match(raw.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# Numeric coercions
# ---------------------------------------------------------------------------

def to_int(raw: str, default: int = 0) -> int:
    """Convert a string to int, falling back to default on failure."""
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return default


def to_float(raw: str, default: float = 0.0) -> float:
    """Convert a string to float, falling back to default on failure."""
    try:
        return float(raw.strip())
    except (ValueError, AttributeError):
        return default


def to_bool(raw: str, default: bool = False) -> bool:
    """Convert a "0"/"1" string to bool, falling back to default."""
    s = raw.strip() if raw else ""
    if s == "1":
        return True
    if s == "0":
        return False
    return default


# ---------------------------------------------------------------------------
# String normalisation
# ---------------------------------------------------------------------------

def normalise_id(raw: str) -> str:
    """Strip and return an identifier string; return '' for empty input."""
    return raw.strip() if raw else ""


def normalise_text(raw: str) -> str:
    """Strip leading/trailing whitespace from free text; return '' for None."""
    return raw.strip() if raw else ""


# ---------------------------------------------------------------------------
# Media path resolution
# ---------------------------------------------------------------------------

def resolve_file_path(raw_path: str, dataset_dir: Path) -> Path | None:
    """
    Resolve a relative file path from the CSV (e.g. 'media/images/img_001.jpg')
    to an absolute Path relative to dataset_dir.

    Returns None if the raw_path is empty or the resolved file does not exist.
    Non-existence is not an error — the multimodal module handles it gracefully.
    """
    if not raw_path or not raw_path.strip():
        return None
    candidate = dataset_dir / raw_path.strip()
    return candidate if candidate.is_file() else None


# ---------------------------------------------------------------------------
# Row-level normalisation helpers
# ---------------------------------------------------------------------------

def normalise_message_row(row: dict[str, str]) -> dict[str, Any]:
    """
    Normalise a raw messages.csv row dict.

    Returns a new dict with typed values; does not mutate input.
    """
    return {
        "message_id":        normalise_id(row.get("message_id", "")),
        "user_id":           normalise_id(row.get("user_id", "")),
        "conversation_type": normalise_id(row.get("conversation_type", "")),
        "group_id":          normalise_id(row.get("group_id", "")),
        "business_id":       normalise_id(row.get("business_id", "")),
        "sender_user_id":    normalise_id(row.get("sender_user_id", "")),
        "created_at":        parse_datetime(row.get("created_at", "")),
        "message_text":      normalise_text(row.get("message_text", "")),
        "media_type":        normalise_id(row.get("media_type", "")),
        "media_id":          normalise_id(row.get("media_id", "")),
        "forwarded_count":   to_int(row.get("forwarded_count", "0")),
    }


def normalise_user_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "user_id":                     normalise_id(row.get("user_id", "")),
        "do_not_disturb_window":       parse_dnd_window(row.get("do_not_disturb_window", "")),
        "messages_opened_30d":         to_int(row.get("messages_opened_30d", "0")),
        "messages_replied_30d":        to_int(row.get("messages_replied_30d", "0")),
        "notifications_dismissed_30d": to_int(row.get("notifications_dismissed_30d", "0")),
        "messages_reported_30d":       to_int(row.get("messages_reported_30d", "0")),
    }


def normalise_group_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "group_id":     normalise_id(row.get("group_id", "")),
        "group_name":   normalise_text(row.get("group_name", "")),
        "group_type":   normalise_id(row.get("group_type", "")),
        "member_count": to_int(row.get("member_count", "0")),
        "admin_count":  to_int(row.get("admin_count", "0")),
        "created_at":   parse_date(row.get("created_at", "")),
        "messages_30d": to_int(row.get("messages_30d", "0")),
    }


def normalise_group_member_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "group_id":                    normalise_id(row.get("group_id", "")),
        "user_id":                     normalise_id(row.get("user_id", "")),
        "role":                        normalise_id(row.get("role", "")),
        "joined_at":                   parse_date(row.get("joined_at", "")),
        "messages_sent_30d":           to_int(row.get("messages_sent_30d", "0")),
        "messages_read_30d":           to_int(row.get("messages_read_30d", "0")),
        "replies_sent_30d":            to_int(row.get("replies_sent_30d", "0")),
        "notifications_dismissed_30d": to_int(row.get("notifications_dismissed_30d", "0")),
        "group_muted_by_user":         to_bool(row.get("group_muted_by_user", "0")),
    }


def normalise_business_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "business_id":                    normalise_id(row.get("business_id", "")),
        "display_name":                   normalise_text(row.get("display_name", "")),
        "brand_name":                     normalise_text(row.get("brand_name", "")),
        "category":                       normalise_id(row.get("category", "")),
        "verified":                       to_bool(row.get("verified", "0")),
        "official_domain":                normalise_id(row.get("official_domain", "")),
        "domain_used_by_sender":          normalise_id(row.get("domain_used_by_sender", "")),
        "account_age_days":               to_int(row.get("account_age_days", "0")),
        "messages_sent_30d":              to_int(row.get("messages_sent_30d", "0")),
        "user_reports_30d":               to_int(row.get("user_reports_30d", "0")),
        "domain_used_by_sender_age_days": to_int(row.get("domain_used_by_sender_age_days", "0")),
    }


def normalise_user_business_history_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "user_id":                normalise_id(row.get("user_id", "")),
        "business_id":            normalise_id(row.get("business_id", "")),
        "why_user_knows_account": normalise_text(row.get("why_user_knows_account", "")),
        "last_activity_at":       parse_datetime(row.get("last_activity_at", "")),
        "allows_promotions":      to_bool(row.get("allows_promotions", "0")),
        "promotions_opted_out_at": parse_datetime(row.get("promotions_opted_out_at", "")),
        "activity_count_180d":    to_int(row.get("activity_count_180d", "0")),
        "messages_opened_30d":    to_int(row.get("messages_opened_30d", "0")),
        "messages_dismissed_30d": to_int(row.get("messages_dismissed_30d", "0")),
        "messages_replied_30d":   to_int(row.get("messages_replied_30d", "0")),
        "last_reply_at":          parse_datetime(row.get("last_reply_at", "")),
    }


def normalise_message_event_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "user_id":               normalise_id(row.get("user_id", "")),
        "message_id":            normalise_id(row.get("message_id", "")),
        "message_opened":        to_bool(row.get("message_opened", "0")),
        "message_replied":       to_bool(row.get("message_replied", "0")),
        "reaction_time_minutes": to_float(row.get("reaction_time_minutes", "0")),
        "notification_dismissed": to_bool(row.get("notification_dismissed", "0")),
        "muted_after_message":   to_bool(row.get("muted_after_message", "0")),
        "message_reported":      to_bool(row.get("message_reported", "0")),
    }


def normalise_image_row(row: dict[str, str], dataset_dir: Path) -> dict[str, Any]:
    raw_path = row.get("file_path", "")
    return {
        "image_id":  normalise_id(row.get("image_id", "")),
        "file_path": raw_path.strip(),
        "resolved_path": resolve_file_path(raw_path, dataset_dir),
    }


def normalise_voice_note_row(row: dict[str, str], dataset_dir: Path) -> dict[str, Any]:
    raw_path = row.get("file_path", "")
    return {
        "voice_note_id": normalise_id(row.get("voice_note_id", "")),
        "file_path":     raw_path.strip(),
        "resolved_path": resolve_file_path(raw_path, dataset_dir),
    }


def normalise_daily_summary_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "user_id":                normalise_id(row.get("user_id", "")),
        "date":                   parse_date(row.get("date", "")),
        "notifications_sent":     to_int(row.get("notifications_sent", "0")),
        "notifications_dismissed": to_int(row.get("notifications_dismissed", "0")),
    }
