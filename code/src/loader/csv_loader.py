"""
src/loader/csv_loader.py
------------------------
Loads all participant-facing datasets into typed, validated DatasetBundle objects.

Public interface
----------------
    load_all_datasets(strict=True) -> DatasetBundle
        Load, validate, normalise, and return every dataset in one call.

    load_messages(strict=True) -> list[dict]
        Load and normalise dataset/messages.csv only.

DatasetBundle
    A frozen dataclass holding every dataset as a list of normalised dicts,
    plus lookup indexes (dicts keyed by primary/composite keys) for O(1)
    access by downstream context-builder modules.

Design rules
------------
  - Never modifies dataset files.
  - Uses file_io.read_csv_rows() for correct RFC 4180 multi-line field handling.
  - Uses schema_validator to check columns before processing.
  - Uses normalizer to coerce types.
  - Raises DatasetLoadError on missing columns when strict=True.
  - On strict=False, logs warnings and returns partial data so tests can
    run with minimal fixtures.
  - All paths come from src/configs/paths.py — no hardcoded paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.configs import paths as _PATHS
from src.loader import normalizer as _N
from src.loader.schema_validator import ALL_SCHEMAS, DatasetSchema
from src.utils.file_io import get_csv_fieldnames, read_csv_rows
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class DatasetLoadError(RuntimeError):
    """Raised when a required dataset cannot be loaded or fails schema validation."""


# ---------------------------------------------------------------------------
# DatasetBundle — the typed result consumed by all downstream modules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DatasetBundle:
    """
    Holds every loaded dataset as normalised lists and lookup indexes.

    Lists preserve the original file row order.
    Indexes provide O(1) access to individual records by key.
    All fields are immutable after construction.
    """

    # Raw-ordered lists (normalised dicts)
    messages:                    tuple[dict[str, Any], ...]
    users:                       tuple[dict[str, Any], ...]
    groups:                      tuple[dict[str, Any], ...]
    group_members:               tuple[dict[str, Any], ...]
    business_accounts:           tuple[dict[str, Any], ...]
    user_business_history:       tuple[dict[str, Any], ...]
    message_history:             tuple[dict[str, Any], ...]
    message_events:              tuple[dict[str, Any], ...]
    images:                      tuple[dict[str, Any], ...]
    voice_notes:                 tuple[dict[str, Any], ...]
    daily_notification_summary:  tuple[dict[str, Any], ...]

    # ----- Single-key indexes -----
    # user_id → user record
    users_by_id:                    dict[str, dict[str, Any]] = field(compare=False, hash=False)
    # group_id → group record
    groups_by_id:                   dict[str, dict[str, Any]] = field(compare=False, hash=False)
    # business_id → business record
    business_by_id:                 dict[str, dict[str, Any]] = field(compare=False, hash=False)
    # image_id → image record
    images_by_id:                   dict[str, dict[str, Any]] = field(compare=False, hash=False)
    # voice_note_id → voice note record
    voice_notes_by_id:              dict[str, dict[str, Any]] = field(compare=False, hash=False)
    # historical message_id → history record
    history_by_message_id:          dict[str, dict[str, Any]] = field(compare=False, hash=False)

    # ----- Composite / multi-value indexes -----
    # user_id → list of group_member records (all groups this user belongs to)
    group_members_by_user:          dict[str, list[dict[str, Any]]] = field(compare=False, hash=False)
    # group_id → list of group_member records (all members of this group)
    group_members_by_group:         dict[str, list[dict[str, Any]]] = field(compare=False, hash=False)
    # (user_id, group_id) → group_member record
    group_member_by_user_and_group: dict[tuple[str, str], dict[str, Any]] = field(compare=False, hash=False)
    # (user_id, business_id) → user_business_history record
    ubh_by_user_and_business:       dict[tuple[str, str], dict[str, Any]] = field(compare=False, hash=False)
    # user_id → list of user_business_history records
    ubh_by_user:                    dict[str, list[dict[str, Any]]] = field(compare=False, hash=False)
    # message_id (history) → message_event record
    events_by_message_id:           dict[str, dict[str, Any]] = field(compare=False, hash=False)
    # user_id → list of message_history records
    history_by_user:                dict[str, list[dict[str, Any]]] = field(compare=False, hash=False)
    # user_id → list of daily_notification_summary records (ordered by date)
    daily_summary_by_user:          dict[str, list[dict[str, Any]]] = field(compare=False, hash=False)

    # ----- Derived sets for referential integrity checks -----
    known_user_ids:     frozenset[str] = field(compare=False, hash=False)
    known_group_ids:    frozenset[str] = field(compare=False, hash=False)
    known_business_ids: frozenset[str] = field(compare=False, hash=False)

    def __repr__(self) -> str:
        return (
            f"DatasetBundle("
            f"messages={len(self.messages)}, "
            f"history={len(self.message_history)}, "
            f"users={len(self.users)}, "
            f"groups={len(self.groups)}, "
            f"businesses={len(self.business_accounts)})"
        )


# ---------------------------------------------------------------------------
# Internal loader helpers
# ---------------------------------------------------------------------------

def _load_and_validate(
    path: Path,
    schema: DatasetSchema,
    strict: bool,
) -> list[dict[str, str]]:
    """
    Read a CSV file and validate its schema.

    Returns raw string-valued row dicts.
    Raises DatasetLoadError on schema errors when strict=True.
    """
    logger.debug("Loading %s ...", path.name)
    try:
        fieldnames = get_csv_fieldnames(path)
        rows = read_csv_rows(path)
    except FileNotFoundError as exc:
        msg = f"Dataset file not found: {path}"
        if strict:
            raise DatasetLoadError(msg) from exc
        logger.warning(msg)
        return []

    errors = schema.validate(fieldnames, rows, source=str(path))
    if errors:
        for err in errors:
            logger.error(err)
        if strict:
            raise DatasetLoadError(
                f"Schema validation failed for '{path.name}' "
                f"({len(errors)} error(s)). See log for details."
            )
        logger.warning("Proceeding with invalid schema (strict=False).")

    logger.debug("Loaded %d rows from %s", len(rows), path.name)
    return rows


def _build_index(
    records: list[dict[str, Any]],
    *key_fields: str,
) -> dict[Any, Any]:
    """
    Build a dict index from a list of normalised records.

    If one key field is given  → key is the field value (str).
    If multiple key fields are given → key is a tuple of field values.
    Later records overwrite earlier ones on key collision.
    """
    index: dict[Any, Any] = {}
    for rec in records:
        if len(key_fields) == 1:
            key = rec.get(key_fields[0], "")
        else:
            key = tuple(rec.get(kf, "") for kf in key_fields)
        if key:
            index[key] = rec
    return index


def _build_multi_index(
    records: list[dict[str, Any]],
    *key_fields: str,
) -> dict[Any, list[dict[str, Any]]]:
    """Build a dict where each key maps to a list of matching records."""
    index: dict[Any, list[dict[str, Any]]] = {}
    for rec in records:
        if len(key_fields) == 1:
            key = rec.get(key_fields[0], "")
        else:
            key = tuple(rec.get(kf, "") for kf in key_fields)
        if key:
            index.setdefault(key, []).append(rec)
    return index


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_messages(strict: bool = True) -> list[dict[str, Any]]:
    """
    Load and normalise dataset/messages.csv.

    Returns a list of normalised message dicts.
    This is exposed separately so the batch runner can start processing
    before loading all reference tables.
    """
    rows = _load_and_validate(_PATHS.MESSAGES_CSV, ALL_SCHEMAS["messages"], strict)
    return [_N.normalise_message_row(r) for r in rows]


def load_all_datasets(strict: bool = True) -> DatasetBundle:
    """
    Load, validate, and normalise every participant-facing dataset.

    Parameters
    ----------
    strict: If True (default), raise DatasetLoadError on any validation error.
            If False, log warnings and continue with partial data.

    Returns
    -------
    DatasetBundle with fully normalised lists and all indexes built.
    """
    logger.info("Loading all datasets (strict=%s) ...", strict)
    dataset_dir = _PATHS.DATASET_DIR

    # --- Load raw rows ---
    raw_messages    = _load_and_validate(_PATHS.MESSAGES_CSV,                   ALL_SCHEMAS["messages"],                   strict)
    raw_users       = _load_and_validate(_PATHS.USERS_CSV,                      ALL_SCHEMAS["users"],                      strict)
    raw_groups      = _load_and_validate(_PATHS.GROUPS_CSV,                     ALL_SCHEMAS["groups"],                     strict)
    raw_gm          = _load_and_validate(_PATHS.GROUP_MEMBERS_CSV,              ALL_SCHEMAS["group_members"],              strict)
    raw_biz         = _load_and_validate(_PATHS.BUSINESS_ACCOUNTS_CSV,          ALL_SCHEMAS["business_accounts"],          strict)
    raw_ubh         = _load_and_validate(_PATHS.USER_BUSINESS_HISTORY_CSV,      ALL_SCHEMAS["user_business_history"],      strict)
    raw_history     = _load_and_validate(_PATHS.MESSAGE_HISTORY_CSV,            ALL_SCHEMAS["message_history"],            strict)
    raw_events      = _load_and_validate(_PATHS.MESSAGE_EVENTS_CSV,             ALL_SCHEMAS["message_events"],             strict)
    raw_images      = _load_and_validate(_PATHS.IMAGES_CSV,                     ALL_SCHEMAS["images"],                     strict)
    raw_vn          = _load_and_validate(_PATHS.VOICE_NOTES_CSV,                ALL_SCHEMAS["voice_notes"],                strict)
    raw_daily       = _load_and_validate(_PATHS.DAILY_NOTIFICATION_SUMMARY_CSV, ALL_SCHEMAS["daily_notification_summary"], strict)

    # --- Normalise ---
    messages   = [_N.normalise_message_row(r)              for r in raw_messages]
    users      = [_N.normalise_user_row(r)                 for r in raw_users]
    groups     = [_N.normalise_group_row(r)                for r in raw_groups]
    gm         = [_N.normalise_group_member_row(r)         for r in raw_gm]
    biz        = [_N.normalise_business_row(r)             for r in raw_biz]
    ubh        = [_N.normalise_user_business_history_row(r) for r in raw_ubh]
    history    = [_N.normalise_message_row(r)              for r in raw_history]
    events     = [_N.normalise_message_event_row(r)        for r in raw_events]
    images     = [_N.normalise_image_row(r, dataset_dir)   for r in raw_images]
    voice_notes= [_N.normalise_voice_note_row(r, dataset_dir) for r in raw_vn]
    daily      = [_N.normalise_daily_summary_row(r)        for r in raw_daily]

    # Sort daily summaries by date per user (for recent-load calculations in M4)
    daily.sort(key=lambda r: (r["user_id"], r["date"] or date.min))

    # --- Build indexes ---
    users_by_id     = _build_index(users,    "user_id")
    groups_by_id    = _build_index(groups,   "group_id")
    business_by_id  = _build_index(biz,      "business_id")
    images_by_id    = _build_index(images,   "image_id")
    vn_by_id        = _build_index(voice_notes, "voice_note_id")
    hist_by_mid     = _build_index(history,  "message_id")

    gm_by_user      = _build_multi_index(gm, "user_id")
    gm_by_group     = _build_multi_index(gm, "group_id")
    gm_by_ug        = _build_index(gm,       "user_id", "group_id")
    ubh_by_ub       = _build_index(ubh,      "user_id", "business_id")
    ubh_by_user     = _build_multi_index(ubh, "user_id")
    events_by_mid   = _build_index(events,   "message_id")
    hist_by_user    = _build_multi_index(history, "user_id")
    daily_by_user   = _build_multi_index(daily,   "user_id")

    # --- Referential integrity check (warn-only) ---
    known_user_ids     = frozenset(users_by_id)
    known_group_ids    = frozenset(groups_by_id)
    known_business_ids = frozenset(business_by_id)

    _check_referential_integrity(messages, known_user_ids, known_group_ids, known_business_ids)

    logger.info(
        "Datasets loaded: %d messages, %d users, %d groups, %d businesses, "
        "%d history, %d events",
        len(messages), len(users), len(groups), len(biz),
        len(history), len(events),
    )

    return DatasetBundle(
        messages=tuple(messages),
        users=tuple(users),
        groups=tuple(groups),
        group_members=tuple(gm),
        business_accounts=tuple(biz),
        user_business_history=tuple(ubh),
        message_history=tuple(history),
        message_events=tuple(events),
        images=tuple(images),
        voice_notes=tuple(voice_notes),
        daily_notification_summary=tuple(daily),
        users_by_id=users_by_id,
        groups_by_id=groups_by_id,
        business_by_id=business_by_id,
        images_by_id=images_by_id,
        voice_notes_by_id=vn_by_id,
        history_by_message_id=hist_by_mid,
        group_members_by_user=gm_by_user,
        group_members_by_group=gm_by_group,
        group_member_by_user_and_group=gm_by_ug,
        ubh_by_user_and_business=ubh_by_ub,
        ubh_by_user=ubh_by_user,
        events_by_message_id=events_by_mid,
        history_by_user=hist_by_user,
        daily_summary_by_user=daily_by_user,
        known_user_ids=known_user_ids,
        known_group_ids=known_group_ids,
        known_business_ids=known_business_ids,
    )


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------

def _check_referential_integrity(
    messages: list[dict[str, Any]],
    user_ids: frozenset[str],
    group_ids: frozenset[str],
    business_ids: frozenset[str],
) -> None:
    """
    Warn about FK violations in messages.csv (warn-only; never raises).

    Checks:
      - Each message's user_id exists in users.csv.
      - Each message's group_id (if non-empty) exists in groups.csv.
      - Each message's business_id (if non-empty) exists in business_accounts.csv.
    """
    unknown_users = set()
    unknown_groups = set()
    unknown_businesses = set()

    for msg in messages:
        uid = msg["user_id"]
        if uid and uid not in user_ids:
            unknown_users.add(uid)

        gid = msg["group_id"]
        if gid and gid not in group_ids:
            unknown_groups.add(gid)

        bid = msg["business_id"]
        if bid and bid not in business_ids:
            unknown_businesses.add(bid)

    if unknown_users:
        logger.warning("FK warning: %d unknown user_id(s) in messages: %s",
                       len(unknown_users), sorted(unknown_users)[:5])
    if unknown_groups:
        logger.warning("FK warning: %d unknown group_id(s) in messages: %s",
                       len(unknown_groups), sorted(unknown_groups)[:5])
    if unknown_businesses:
        logger.warning("FK warning: %d unknown business_id(s) in messages: %s",
                       len(unknown_businesses), sorted(unknown_businesses)[:5])
