"""
tests/unit/test_module2_loader.py
----------------------------------
Unit tests for Module 2: Dataset Loader & Schema Validator.

Coverage:
  1. Schema validator  — column presence, per-row field constraints
  2. Normalizer        — timestamp parsing, numeric coercion, bool coercion,
                        DND window parsing, media path resolution
  3. CSV Loader        — happy path, missing column, missing file, non-strict
  4. DatasetBundle     — all indexes built correctly, immutability
  5. Referential integrity — unknown FK warns, does not raise
  6. Real dataset smoke — load_all_datasets() against the actual files
"""

from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ===========================================================================
# 1. Schema Validator
# ===========================================================================

class TestSchemaValidator:
    """src/loader/schema_validator.py"""

    def test_messages_schema_accepts_valid_row(self) -> None:
        from src.loader.schema_validator import MESSAGES_SCHEMA
        valid_row = {
            "message_id": "msg_001", "user_id": "u_001",
            "conversation_type": "personal", "group_id": "",
            "business_id": "", "sender_user_id": "u_002",
            "created_at": "2026-07-30 22:19", "message_text": "hello",
            "media_type": "", "media_id": "", "forwarded_count": "0",
        }
        errors = MESSAGES_SCHEMA.validate(list(valid_row.keys()), [valid_row])
        assert errors == []

    def test_messages_schema_rejects_invalid_conversation_type(self) -> None:
        from src.loader.schema_validator import MESSAGES_SCHEMA
        row = {
            "message_id": "msg_001", "user_id": "u_001",
            "conversation_type": "unknown_type", "group_id": "",
            "business_id": "", "sender_user_id": "",
            "created_at": "2026-07-30 10:00", "message_text": "hi",
            "media_type": "", "media_id": "", "forwarded_count": "0",
        }
        errors = MESSAGES_SCHEMA.validate(list(row.keys()), [row])
        assert any("conversation_type" in e for e in errors)

    def test_messages_schema_missing_required_column(self) -> None:
        from src.loader.schema_validator import MESSAGES_SCHEMA
        errors = MESSAGES_SCHEMA.validate(
            ["message_id", "user_id"],  # missing most columns
            [],
        )
        assert any("conversation_type" in e for e in errors)

    def test_users_schema_accepts_valid_row(self) -> None:
        from src.loader.schema_validator import USERS_SCHEMA
        row = {
            "user_id": "u_001", "do_not_disturb_window": "22:00-07:00",
            "messages_opened_30d": "10", "messages_replied_30d": "2",
            "notifications_dismissed_30d": "5", "messages_reported_30d": "0",
        }
        errors = USERS_SCHEMA.validate(list(row.keys()), [row])
        assert errors == []

    def test_users_schema_rejects_negative_count(self) -> None:
        from src.loader.schema_validator import USERS_SCHEMA
        row = {
            "user_id": "u_001", "do_not_disturb_window": "22:00-07:00",
            "messages_opened_30d": "-1", "messages_replied_30d": "2",
            "notifications_dismissed_30d": "5", "messages_reported_30d": "0",
        }
        errors = USERS_SCHEMA.validate(list(row.keys()), [row])
        assert any("messages_opened_30d" in e for e in errors)

    def test_business_schema_bool_verified(self) -> None:
        from src.loader.schema_validator import BUSINESS_ACCOUNTS_SCHEMA
        base_fields = [
            "business_id", "display_name", "brand_name", "category",
            "verified", "official_domain", "domain_used_by_sender",
            "account_age_days", "messages_sent_30d", "user_reports_30d",
            "domain_used_by_sender_age_days",
        ]
        row = dict(zip(base_fields, [
            "biz_001", "Test Co", "Test", "ecommerce", "2",  # invalid verified
            "test.com", "test.com", "100", "50", "1", "200",
        ]))
        errors = BUSINESS_ACCOUNTS_SCHEMA.validate(base_fields, [row])
        assert any("verified" in e for e in errors)

    def test_group_members_schema_muted_is_bool(self) -> None:
        from src.loader.schema_validator import GROUP_MEMBERS_SCHEMA
        fields = ["group_id", "user_id", "role", "joined_at",
                  "messages_sent_30d", "messages_read_30d", "replies_sent_30d",
                  "notifications_dismissed_30d", "group_muted_by_user"]
        row = dict(zip(fields, [
            "g_001", "u_001", "admin", "2023-01-01",
            "0", "0", "0", "0", "yes",  # invalid bool
        ]))
        errors = GROUP_MEMBERS_SCHEMA.validate(fields, [row])
        assert any("group_muted_by_user" in e for e in errors)

    def test_images_schema_accepts_valid(self) -> None:
        from src.loader.schema_validator import IMAGES_SCHEMA
        row = {"image_id": "img_001", "file_path": "media/images/img_001.jpg"}
        errors = IMAGES_SCHEMA.validate(list(row.keys()), [row])
        assert errors == []

    def test_output_schema_allows_empty_action(self) -> None:
        """output.csv template rows have empty action/message_type etc."""
        from src.loader.schema_validator import OUTPUT_SCHEMA
        row = {
            "message_id": "msg_001", "action": "", "message_type": "",
            "reason": "", "confidence": "", "evidence_message_ids": "",
        }
        errors = OUTPUT_SCHEMA.validate(list(row.keys()), [row])
        assert errors == []

    def test_schema_registry_complete(self) -> None:
        from src.loader.schema_validator import ALL_SCHEMAS
        expected_keys = {
            "messages", "users", "groups", "group_members",
            "business_accounts", "user_business_history",
            "message_history", "message_events", "images",
            "voice_notes", "daily_notification_summary", "output",
        }
        assert expected_keys.issubset(set(ALL_SCHEMAS.keys()))


# ===========================================================================
# 2. Normalizer
# ===========================================================================

class TestNormalizer:
    """src/loader/normalizer.py"""

    def test_parse_datetime_hhmm(self) -> None:
        from src.loader.normalizer import parse_datetime
        result = parse_datetime("2026-07-30 22:19")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.hour == 22
        assert result.minute == 19

    def test_parse_datetime_hhmmss(self) -> None:
        from src.loader.normalizer import parse_datetime
        result = parse_datetime("2026-07-30 22:19:45")
        assert result is not None
        assert result.second == 45

    def test_parse_datetime_empty(self) -> None:
        from src.loader.normalizer import parse_datetime
        assert parse_datetime("") is None
        assert parse_datetime("   ") is None

    def test_parse_datetime_invalid(self) -> None:
        from src.loader.normalizer import parse_datetime
        assert parse_datetime("not-a-date") is None

    def test_parse_date(self) -> None:
        from src.loader.normalizer import parse_date
        result = parse_date("2023-02-11")
        assert isinstance(result, date)
        assert result.year == 2023 and result.month == 2 and result.day == 11

    def test_parse_date_empty(self) -> None:
        from src.loader.normalizer import parse_date
        assert parse_date("") is None

    def test_parse_dnd_window_valid(self) -> None:
        from src.loader.normalizer import parse_dnd_window
        result = parse_dnd_window("22:00-07:00")
        assert result == ("22:00", "07:00")

    def test_parse_dnd_window_empty(self) -> None:
        from src.loader.normalizer import parse_dnd_window
        assert parse_dnd_window("") is None
        assert parse_dnd_window("   ") is None

    def test_parse_dnd_window_malformed(self) -> None:
        from src.loader.normalizer import parse_dnd_window
        assert parse_dnd_window("invalid") is None

    def test_to_int(self) -> None:
        from src.loader.normalizer import to_int
        assert to_int("42") == 42
        assert to_int("0") == 0
        assert to_int("") == 0
        assert to_int("bad") == 0
        assert to_int("bad", default=-1) == -1

    def test_to_float(self) -> None:
        from src.loader.normalizer import to_float
        assert to_float("3.14") == pytest.approx(3.14)
        assert to_float("") == 0.0
        assert to_float("nope") == 0.0

    def test_to_bool(self) -> None:
        from src.loader.normalizer import to_bool
        assert to_bool("1") is True
        assert to_bool("0") is False
        assert to_bool("") is False
        assert to_bool("yes") is False  # invalid → default

    def test_normalise_id_strips(self) -> None:
        from src.loader.normalizer import normalise_id
        assert normalise_id("  u_001  ") == "u_001"
        assert normalise_id("") == ""

    def test_normalise_message_row_types(self) -> None:
        from src.loader.normalizer import normalise_message_row
        raw = {
            "message_id": "msg_001", "user_id": "u_001",
            "conversation_type": "personal", "group_id": "",
            "business_id": "", "sender_user_id": "u_002",
            "created_at": "2026-07-30 22:19", "message_text": "hello",
            "media_type": "", "media_id": "", "forwarded_count": "3",
        }
        result = normalise_message_row(raw)
        assert result["forwarded_count"] == 3
        assert isinstance(result["created_at"], datetime)
        assert result["message_id"] == "msg_001"

    def test_normalise_user_row_types(self) -> None:
        from src.loader.normalizer import normalise_user_row
        raw = {
            "user_id": "u_001", "do_not_disturb_window": "22:00-07:00",
            "messages_opened_30d": "10", "messages_replied_30d": "2",
            "notifications_dismissed_30d": "5", "messages_reported_30d": "1",
        }
        result = normalise_user_row(raw)
        assert result["do_not_disturb_window"] == ("22:00", "07:00")
        assert result["messages_opened_30d"] == 10
        assert isinstance(result["messages_replied_30d"], int)

    def test_normalise_group_member_row_bool(self) -> None:
        from src.loader.normalizer import normalise_group_member_row
        raw = {
            "group_id": "g_001", "user_id": "u_001", "role": "admin",
            "joined_at": "2023-01-01", "messages_sent_30d": "5",
            "messages_read_30d": "10", "replies_sent_30d": "2",
            "notifications_dismissed_30d": "0", "group_muted_by_user": "1",
        }
        result = normalise_group_member_row(raw)
        assert result["group_muted_by_user"] is True
        assert isinstance(result["joined_at"], date)

    def test_resolve_file_path_exists(self, tmp_path: Path) -> None:
        from src.loader.normalizer import resolve_file_path
        img = tmp_path / "media" / "images" / "test.jpg"
        img.parent.mkdir(parents=True)
        img.write_bytes(b"\xff\xd8")
        result = resolve_file_path("media/images/test.jpg", tmp_path)
        assert result == img

    def test_resolve_file_path_missing(self, tmp_path: Path) -> None:
        from src.loader.normalizer import resolve_file_path
        result = resolve_file_path("media/images/ghost.jpg", tmp_path)
        assert result is None

    def test_resolve_file_path_empty(self, tmp_path: Path) -> None:
        from src.loader.normalizer import resolve_file_path
        assert resolve_file_path("", tmp_path) is None

    def test_normalise_daily_summary_row(self) -> None:
        from src.loader.normalizer import normalise_daily_summary_row
        raw = {
            "user_id": "u_001", "date": "2026-07-04",
            "notifications_sent": "2", "notifications_dismissed": "1",
        }
        result = normalise_daily_summary_row(raw)
        assert isinstance(result["date"], date)
        assert result["notifications_sent"] == 2


# ===========================================================================
# 3. CSV Loader — unit tests with synthetic CSVs
# ===========================================================================

def _write_csv(path: Path, header: str, *rows: str) -> None:
    """Write a minimal CSV file for testing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header.split(","))
        for r in rows:
            w.writerow(r.split(","))


class TestCSVLoader:
    """src/loader/csv_loader.py — unit tests with patched paths."""

    def _patch_paths(self, monkeypatch, tmp_path: Path, files: dict[str, Path]) -> None:
        """Monkeypatch PATHS constants used by csv_loader."""
        import src.configs.paths as _paths
        for attr, fpath in files.items():
            monkeypatch.setattr(_paths, attr, fpath)

    def test_load_messages_happy_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.loader.csv_loader import load_messages
        import src.configs.paths as _paths

        csv_path = tmp_path / "messages.csv"
        _write_csv(
            csv_path,
            "message_id,user_id,conversation_type,group_id,business_id,"
            "sender_user_id,created_at,message_text,media_type,media_id,forwarded_count",
            "msg_001,u_001,personal,,,u_002,2026-07-30 10:00,hello,,, 0",
        )
        monkeypatch.setattr(_paths, "MESSAGES_CSV", csv_path)
        result = load_messages(strict=True)
        assert len(result) == 1
        assert result[0]["message_id"] == "msg_001"
        assert result[0]["forwarded_count"] == 0
        assert isinstance(result[0]["created_at"], datetime)

    def test_load_messages_missing_file_strict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.loader.csv_loader import load_messages, DatasetLoadError
        import src.configs.paths as _paths
        monkeypatch.setattr(_paths, "MESSAGES_CSV", tmp_path / "ghost.csv")
        with pytest.raises(DatasetLoadError):
            load_messages(strict=True)

    def test_load_messages_missing_file_non_strict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.loader.csv_loader import load_messages
        import src.configs.paths as _paths
        monkeypatch.setattr(_paths, "MESSAGES_CSV", tmp_path / "ghost.csv")
        result = load_messages(strict=False)
        assert result == []

    def test_load_messages_missing_column_strict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.loader.csv_loader import load_messages, DatasetLoadError
        import src.configs.paths as _paths
        csv_path = tmp_path / "messages.csv"
        _write_csv(csv_path, "message_id,user_id", "msg_001,u_001")
        monkeypatch.setattr(_paths, "MESSAGES_CSV", csv_path)
        with pytest.raises(DatasetLoadError):
            load_messages(strict=True)

    def test_load_messages_missing_column_non_strict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.loader.csv_loader import load_messages
        import src.configs.paths as _paths
        csv_path = tmp_path / "messages.csv"
        _write_csv(csv_path, "message_id,user_id", "msg_001,u_001")
        monkeypatch.setattr(_paths, "MESSAGES_CSV", csv_path)
        result = load_messages(strict=False)  # must not raise
        assert isinstance(result, list)

    def test_multiline_message_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multi-line text inside quotes must parse as a single message row."""
        from src.loader.csv_loader import load_messages
        import src.configs.paths as _paths
        csv_path = tmp_path / "messages.csv"
        content = (
            "message_id,user_id,conversation_type,group_id,business_id,"
            "sender_user_id,created_at,message_text,media_type,media_id,forwarded_count\n"
            'msg_001,u_001,personal,,,u_002,2026-07-30 10:00,"line one\nline two",,, 0\n'
        )
        csv_path.write_text(content, encoding="utf-8")
        monkeypatch.setattr(_paths, "MESSAGES_CSV", csv_path)
        result = load_messages(strict=False)
        assert len(result) == 1
        assert "line one" in result[0]["message_text"]


# ===========================================================================
# 4. DatasetBundle — index correctness
# ===========================================================================

class TestDatasetBundle:
    """Verify index construction from synthetic data."""

    def _make_bundle_from_lists(self, **kwargs):
        """Build a minimal DatasetBundle using the loader's index helpers."""
        from src.loader.csv_loader import (
            DatasetBundle, _build_index, _build_multi_index
        )
        from datetime import date

        users = kwargs.get("users", [{"user_id": "u_001", "do_not_disturb_window": None,
                                       "messages_opened_30d": 5, "messages_replied_30d": 1,
                                       "notifications_dismissed_30d": 2, "messages_reported_30d": 0}])
        groups = kwargs.get("groups", [])
        gm = kwargs.get("gm", [])
        biz = kwargs.get("biz", [])
        ubh = kwargs.get("ubh", [])
        history = kwargs.get("history", [])
        events = kwargs.get("events", [])
        images = kwargs.get("images", [])
        vn = kwargs.get("vn", [])
        daily = kwargs.get("daily", [])
        messages = kwargs.get("messages", [])

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
            voice_notes=tuple(vn),
            daily_notification_summary=tuple(daily),
            users_by_id=_build_index(users, "user_id"),
            groups_by_id=_build_index(groups, "group_id"),
            business_by_id=_build_index(biz, "business_id"),
            images_by_id=_build_index(images, "image_id"),
            voice_notes_by_id=_build_index(vn, "voice_note_id"),
            history_by_message_id=_build_index(history, "message_id"),
            group_members_by_user=_build_multi_index(gm, "user_id"),
            group_members_by_group=_build_multi_index(gm, "group_id"),
            group_member_by_user_and_group=_build_index(gm, "user_id", "group_id"),
            ubh_by_user_and_business=_build_index(ubh, "user_id", "business_id"),
            ubh_by_user=_build_multi_index(ubh, "user_id"),
            events_by_message_id=_build_index(events, "message_id"),
            history_by_user=_build_multi_index(history, "user_id"),
            daily_summary_by_user=_build_multi_index(daily, "user_id"),
            known_user_ids=frozenset(u["user_id"] for u in users),
            known_group_ids=frozenset(g["group_id"] for g in groups),
            known_business_ids=frozenset(b["business_id"] for b in biz),
        )

    def test_users_by_id_lookup(self) -> None:
        bundle = self._make_bundle_from_lists()
        assert "u_001" in bundle.users_by_id
        assert bundle.users_by_id["u_001"]["messages_opened_30d"] == 5

    def test_group_members_by_user_multi(self) -> None:
        gm = [
            {"group_id": "g_001", "user_id": "u_001", "role": "admin",
             "joined_at": None, "messages_sent_30d": 0, "messages_read_30d": 0,
             "replies_sent_30d": 0, "notifications_dismissed_30d": 0, "group_muted_by_user": False},
            {"group_id": "g_002", "user_id": "u_001", "role": "member",
             "joined_at": None, "messages_sent_30d": 0, "messages_read_30d": 0,
             "replies_sent_30d": 0, "notifications_dismissed_30d": 0, "group_muted_by_user": False},
        ]
        bundle = self._make_bundle_from_lists(gm=gm)
        entries = bundle.group_members_by_user["u_001"]
        assert len(entries) == 2
        group_ids = {e["group_id"] for e in entries}
        assert group_ids == {"g_001", "g_002"}

    def test_group_member_by_user_and_group(self) -> None:
        gm = [{"group_id": "g_001", "user_id": "u_001", "role": "admin",
               "joined_at": None, "messages_sent_30d": 0, "messages_read_30d": 0,
               "replies_sent_30d": 0, "notifications_dismissed_30d": 0, "group_muted_by_user": True}]
        bundle = self._make_bundle_from_lists(gm=gm)
        key = ("u_001", "g_001")
        assert key in bundle.group_member_by_user_and_group
        assert bundle.group_member_by_user_and_group[key]["group_muted_by_user"] is True

    def test_ubh_by_user_and_business(self) -> None:
        ubh = [{"user_id": "u_001", "business_id": "biz_001",
                "why_user_knows_account": "order", "last_activity_at": None,
                "allows_promotions": True, "promotions_opted_out_at": None,
                "activity_count_180d": 3, "messages_opened_30d": 2,
                "messages_dismissed_30d": 1, "messages_replied_30d": 0,
                "last_reply_at": None}]
        bundle = self._make_bundle_from_lists(ubh=ubh)
        key = ("u_001", "biz_001")
        assert key in bundle.ubh_by_user_and_business
        assert bundle.ubh_by_user_and_business[key]["allows_promotions"] is True

    def test_bundle_is_immutable(self) -> None:
        bundle = self._make_bundle_from_lists()
        with pytest.raises((AttributeError, TypeError)):
            bundle.messages = ()  # type: ignore[misc]

    def test_bundle_repr(self) -> None:
        bundle = self._make_bundle_from_lists()
        r = repr(bundle)
        assert "DatasetBundle" in r

    def test_known_ids_are_frozensets(self) -> None:
        bundle = self._make_bundle_from_lists()
        assert isinstance(bundle.known_user_ids, frozenset)
        assert isinstance(bundle.known_group_ids, frozenset)
        assert isinstance(bundle.known_business_ids, frozenset)


# ===========================================================================
# 5. Referential integrity
# ===========================================================================

class TestReferentialIntegrity:
    """_check_referential_integrity warns but never raises."""

    def test_unknown_user_id_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        from src.loader.csv_loader import _check_referential_integrity
        import logging
        messages = [{"user_id": "ghost_user", "group_id": "", "business_id": ""}]
        with caplog.at_level(logging.WARNING):
            _check_referential_integrity(
                messages,
                frozenset({"u_001"}),
                frozenset(),
                frozenset(),
            )
        assert any("ghost_user" in r.message for r in caplog.records)

    def test_all_known_ids_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        from src.loader.csv_loader import _check_referential_integrity
        import logging
        messages = [{"user_id": "u_001", "group_id": "g_001", "business_id": ""}]
        with caplog.at_level(logging.WARNING):
            _check_referential_integrity(
                messages,
                frozenset({"u_001"}),
                frozenset({"g_001"}),
                frozenset(),
            )
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings == []


# ===========================================================================
# 6. Real dataset smoke test
# ===========================================================================

class TestRealDatasetSmoke:
    """End-to-end: load_all_datasets() against the actual dataset/."""

    def test_load_all_datasets_strict(self) -> None:
        from src.loader.csv_loader import load_all_datasets, DatasetBundle
        bundle = load_all_datasets(strict=True)
        assert isinstance(bundle, DatasetBundle)

    def test_message_count(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        assert len(bundle.messages) == 110, (
            f"Expected 110 messages, got {len(bundle.messages)}"
        )

    def test_all_message_ids_unique(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        ids = [m["message_id"] for m in bundle.messages]
        assert len(ids) == len(set(ids)), "Duplicate message IDs found"

    def test_users_by_id_non_empty(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        assert len(bundle.users_by_id) > 0

    def test_all_messages_have_parsed_timestamp(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        for msg in bundle.messages:
            assert isinstance(msg["created_at"], datetime), (
                f"message {msg['message_id']} has unparsed created_at: "
                f"{msg['created_at']!r}"
            )

    def test_all_messages_have_int_forwarded_count(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        for msg in bundle.messages:
            assert isinstance(msg["forwarded_count"], int)

    def test_history_indexed_by_message_id(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        # Every history row must be addressable by its message_id
        for hist in bundle.message_history:
            mid = hist["message_id"]
            assert mid in bundle.history_by_message_id

    def test_group_members_by_user_non_empty(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        assert len(bundle.group_members_by_user) > 0

    def test_output_template_message_ids_in_messages(self) -> None:
        """Every message_id in output.csv must exist in messages.csv."""
        from src.loader.csv_loader import load_all_datasets
        from src.utils.file_io import read_csv_rows
        from src.configs.paths import OUTPUT_CSV
        bundle = load_all_datasets()
        out_rows = read_csv_rows(OUTPUT_CSV)
        msg_ids = {m["message_id"] for m in bundle.messages}
        for row in out_rows:
            assert row["message_id"] in msg_ids, (
                f"output.csv has unknown message_id: {row['message_id']!r}"
            )

    def test_images_resolved_paths(self) -> None:
        """Non-None resolved_path values must point to existing files."""
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        for img in bundle.images:
            if img["resolved_path"] is not None:
                assert Path(img["resolved_path"]).is_file(), (
                    f"Image path does not exist: {img['resolved_path']}"
                )

    def test_voice_notes_resolved_paths(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        for vn in bundle.voice_notes:
            if vn["resolved_path"] is not None:
                assert Path(vn["resolved_path"]).is_file()

    def test_bundle_repr_contains_counts(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        r = repr(bundle)
        assert "110" in r  # message count
