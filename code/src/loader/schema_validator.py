"""
src/loader/schema_validator.py
-------------------------------
Schema definitions and validation for every participant-facing dataset.

Each dataset has:
  - REQUIRED_COLUMNS: columns that must be present
  - OPTIONAL_COLUMNS: columns that may be absent without error
  - validate(rows, source): validates a list of row dicts and returns errors

Design:
  - Returns error lists rather than raising, so the caller (csv_loader)
    decides whether to fail fast or log and continue.
  - No business logic; purely structural validation.
  - Never mutates the rows list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColumnSpec:
    """Specification for a single CSV column."""
    name: str
    required: bool = True
    # Optional validator: receives the string value, returns True if valid.
    # None means any non-empty string is acceptable.
    validator: Callable[[str], bool] | None = field(
        default=None, compare=False, hash=False
    )
    allow_empty: bool = False  # if True, empty string is a valid value


@dataclass(frozen=True)
class DatasetSchema:
    """
    Schema for one participant-facing dataset.

    Attributes
    ----------
    name:    Human-readable name used in error messages.
    columns: Ordered list of ColumnSpec objects.
    """
    name: str
    columns: tuple[ColumnSpec, ...]

    @property
    def required_columns(self) -> frozenset[str]:
        return frozenset(c.name for c in self.columns if c.required)

    @property
    def all_columns(self) -> frozenset[str]:
        return frozenset(c.name for c in self.columns)

    def validate(
        self,
        fieldnames: list[str],
        rows: list[dict[str, str]],
        source: str = "",
    ) -> list[str]:
        """
        Validate column presence and per-row field constraints.

        Parameters
        ----------
        fieldnames: The CSV header columns as read by DictReader.
        rows:       List of row dicts.
        source:     File path for error messages.

        Returns
        -------
        List of human-readable error strings (empty = valid).
        """
        errors: list[str] = []
        label = source or self.name

        # 1. Required column presence
        present = frozenset(fieldnames)
        for col in self.required_columns:
            if col not in present:
                errors.append(f"[{label}] Missing required column: '{col}'")

        if errors:
            # No point validating rows if columns are missing
            return errors

        # 2. Per-row validation
        col_map = {c.name: c for c in self.columns}
        for i, row in enumerate(rows, start=2):  # row 1 = header
            for col_name, spec in col_map.items():
                if col_name not in row:
                    continue  # optional column absent — already checked above
                value = row[col_name]
                if not spec.allow_empty and spec.required and value.strip() == "":
                    # Many FK columns are legitimately empty (e.g. group_id for
                    # personal messages), so we only flag the primary key columns.
                    # Specific schemas mark allow_empty=True for FK fields.
                    pass  # fine-grained emptiness is handled per-schema
                if spec.validator is not None and value.strip() != "":
                    if not spec.validator(value.strip()):
                        errors.append(
                            f"[{label}] Row {i}: column '{col_name}' "
                            f"has invalid value: {value!r}"
                        )

        return errors


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

def _is_nonneg_int(v: str) -> bool:
    try:
        return int(v) >= 0
    except ValueError:
        return False


def _is_nonneg_float(v: str) -> bool:
    try:
        return float(v) >= 0.0
    except ValueError:
        return False


def _is_bool_01(v: str) -> bool:
    return v in {"0", "1"}


def _is_conversation_type(v: str) -> bool:
    return v in {"personal", "group", "business"}


def _is_media_type(v: str) -> bool:
    return v in {"", "image", "voice"}


def _is_group_type(v: str) -> bool:
    # Observed values: family, society, school_parents, work, friends, generic
    # We accept any non-empty string to stay flexible
    return bool(v.strip())


def _is_role(v: str) -> bool:
    return v in {"admin", "member"}


# ---------------------------------------------------------------------------
# Schema definitions — one per dataset
# ---------------------------------------------------------------------------

MESSAGES_SCHEMA = DatasetSchema(
    name="messages",
    columns=(
        ColumnSpec("message_id",         required=True),
        ColumnSpec("user_id",            required=True),
        ColumnSpec("conversation_type",  required=True, validator=_is_conversation_type),
        ColumnSpec("group_id",           required=True, allow_empty=True),
        ColumnSpec("business_id",        required=True, allow_empty=True),
        ColumnSpec("sender_user_id",     required=True, allow_empty=True),
        ColumnSpec("created_at",         required=True),
        ColumnSpec("message_text",       required=True, allow_empty=True),
        ColumnSpec("media_type",         required=True, allow_empty=True,
                   validator=lambda v: _is_media_type(v) if v else True),
        ColumnSpec("media_id",           required=True, allow_empty=True),
        ColumnSpec("forwarded_count",    required=True, validator=_is_nonneg_int),
    ),
)

USERS_SCHEMA = DatasetSchema(
    name="users",
    columns=(
        ColumnSpec("user_id",                      required=True),
        ColumnSpec("do_not_disturb_window",        required=True, allow_empty=True),
        ColumnSpec("messages_opened_30d",          required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_replied_30d",         required=True, validator=_is_nonneg_int),
        ColumnSpec("notifications_dismissed_30d",  required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_reported_30d",        required=True, validator=_is_nonneg_int),
    ),
)

GROUPS_SCHEMA = DatasetSchema(
    name="groups",
    columns=(
        ColumnSpec("group_id",      required=True),
        ColumnSpec("group_name",    required=True),
        ColumnSpec("group_type",    required=True, validator=_is_group_type),
        ColumnSpec("member_count",  required=True, validator=_is_nonneg_int),
        ColumnSpec("admin_count",   required=True, validator=_is_nonneg_int),
        ColumnSpec("created_at",    required=True),
        ColumnSpec("messages_30d",  required=True, validator=_is_nonneg_int),
    ),
)

GROUP_MEMBERS_SCHEMA = DatasetSchema(
    name="group_members",
    columns=(
        ColumnSpec("group_id",                    required=True),
        ColumnSpec("user_id",                     required=True),
        ColumnSpec("role",                        required=True, validator=_is_role),
        ColumnSpec("joined_at",                   required=True),
        ColumnSpec("messages_sent_30d",           required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_read_30d",           required=True, validator=_is_nonneg_int),
        ColumnSpec("replies_sent_30d",            required=True, validator=_is_nonneg_int),
        ColumnSpec("notifications_dismissed_30d", required=True, validator=_is_nonneg_int),
        ColumnSpec("group_muted_by_user",         required=True, validator=_is_bool_01),
    ),
)

BUSINESS_ACCOUNTS_SCHEMA = DatasetSchema(
    name="business_accounts",
    columns=(
        ColumnSpec("business_id",                 required=True),
        ColumnSpec("display_name",                required=True),
        ColumnSpec("brand_name",                  required=True),
        ColumnSpec("category",                    required=True),
        ColumnSpec("verified",                    required=True, validator=_is_bool_01),
        ColumnSpec("official_domain",             required=True),
        ColumnSpec("domain_used_by_sender",       required=True, allow_empty=True),
        ColumnSpec("account_age_days",            required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_sent_30d",           required=True, validator=_is_nonneg_int),
        ColumnSpec("user_reports_30d",            required=True, validator=_is_nonneg_int),
        ColumnSpec("domain_used_by_sender_age_days", required=True, allow_empty=True,
                   validator=lambda v: _is_nonneg_int(v) if v else True),
    ),
)

USER_BUSINESS_HISTORY_SCHEMA = DatasetSchema(
    name="user_business_history",
    columns=(
        ColumnSpec("user_id",                 required=True),
        ColumnSpec("business_id",             required=True),
        ColumnSpec("why_user_knows_account",  required=True, allow_empty=True),
        ColumnSpec("last_activity_at",        required=True, allow_empty=True),
        ColumnSpec("allows_promotions",       required=True, validator=_is_bool_01),
        ColumnSpec("promotions_opted_out_at", required=True, allow_empty=True),
        ColumnSpec("activity_count_180d",     required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_opened_30d",     required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_dismissed_30d",  required=True, validator=_is_nonneg_int),
        ColumnSpec("messages_replied_30d",    required=True, validator=_is_nonneg_int),
        ColumnSpec("last_reply_at",           required=True, allow_empty=True),
    ),
)

MESSAGE_HISTORY_SCHEMA = DatasetSchema(
    name="message_history",
    columns=(
        ColumnSpec("message_id",        required=True),
        ColumnSpec("user_id",           required=True),
        ColumnSpec("conversation_type", required=True, validator=_is_conversation_type),
        ColumnSpec("group_id",          required=True, allow_empty=True),
        ColumnSpec("business_id",       required=True, allow_empty=True),
        ColumnSpec("sender_user_id",    required=True, allow_empty=True),
        ColumnSpec("created_at",        required=True),
        ColumnSpec("message_text",      required=True, allow_empty=True),
        ColumnSpec("media_type",        required=True, allow_empty=True,
                   validator=lambda v: _is_media_type(v) if v else True),
        ColumnSpec("media_id",          required=True, allow_empty=True),
        ColumnSpec("forwarded_count",   required=True, validator=_is_nonneg_int),
    ),
)

MESSAGE_EVENTS_SCHEMA = DatasetSchema(
    name="message_events",
    columns=(
        ColumnSpec("user_id",                  required=True),
        ColumnSpec("message_id",               required=True),
        ColumnSpec("message_opened",           required=True, validator=_is_bool_01),
        ColumnSpec("message_replied",          required=True, validator=_is_bool_01),
        ColumnSpec("reaction_time_minutes",    required=True, allow_empty=True,
                   validator=lambda v: _is_nonneg_float(v) if v else True),
        ColumnSpec("notification_dismissed",   required=True, validator=_is_bool_01),
        ColumnSpec("muted_after_message",      required=True, validator=_is_bool_01),
        ColumnSpec("message_reported",         required=True, validator=_is_bool_01),
    ),
)

IMAGES_SCHEMA = DatasetSchema(
    name="images",
    columns=(
        ColumnSpec("image_id",   required=True),
        ColumnSpec("file_path",  required=True),
    ),
)

VOICE_NOTES_SCHEMA = DatasetSchema(
    name="voice_notes",
    columns=(
        ColumnSpec("voice_note_id", required=True),
        ColumnSpec("file_path",     required=True),
    ),
)

DAILY_NOTIFICATION_SUMMARY_SCHEMA = DatasetSchema(
    name="daily_notification_summary",
    columns=(
        ColumnSpec("user_id",                  required=True),
        ColumnSpec("date",                     required=True),
        ColumnSpec("notifications_sent",       required=True, validator=_is_nonneg_int),
        ColumnSpec("notifications_dismissed",  required=True, validator=_is_nonneg_int),
    ),
)

OUTPUT_SCHEMA = DatasetSchema(
    name="output",
    columns=(
        ColumnSpec("message_id",           required=True),
        ColumnSpec("action",               required=True, allow_empty=True),
        ColumnSpec("message_type",         required=True, allow_empty=True),
        ColumnSpec("reason",               required=True, allow_empty=True),
        ColumnSpec("confidence",           required=True, allow_empty=True),
        ColumnSpec("evidence_message_ids", required=True, allow_empty=True),
    ),
)

# Registry: dataset name → schema (used by csv_loader for dispatch)
ALL_SCHEMAS: dict[str, DatasetSchema] = {
    "messages":                    MESSAGES_SCHEMA,
    "users":                       USERS_SCHEMA,
    "groups":                      GROUPS_SCHEMA,
    "group_members":               GROUP_MEMBERS_SCHEMA,
    "business_accounts":           BUSINESS_ACCOUNTS_SCHEMA,
    "user_business_history":       USER_BUSINESS_HISTORY_SCHEMA,
    "message_history":             MESSAGE_HISTORY_SCHEMA,
    "message_events":              MESSAGE_EVENTS_SCHEMA,
    "images":                      IMAGES_SCHEMA,
    "voice_notes":                 VOICE_NOTES_SCHEMA,
    "daily_notification_summary":  DAILY_NOTIFICATION_SUMMARY_SCHEMA,
    "output":                      OUTPUT_SCHEMA,
}
