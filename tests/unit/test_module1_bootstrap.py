"""
tests/unit/test_module1_bootstrap.py
-------------------------------------
Unit tests for Module 1: Project Bootstrap & Runtime Configuration.

Covers:
  - config path resolution (repo root, env var override)
  - writable directory creation
  - dataset file presence validation
  - missing-file failure behaviour
  - logging initialisation (idempotent, no duplicate handlers)
  - types module (allowed values, OUTPUT_COLUMNS contract)
  - file_io helpers (JSON cache, CSV reader, media path resolution)
  - bootstrap() happy path and error path
  - startup summary dict shape

Tests use a temporary directory to avoid touching the real dataset or logs.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ============================================================================
# Helpers
# ============================================================================

def _make_minimal_csv(path: Path, header: str) -> None:
    """Write a minimal valid CSV with the given header to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(header + "\n")
        fh.write("row1_val1,row1_val2\n")


# ============================================================================
# 1. Path resolution
# ============================================================================

class TestPathResolution:
    """src/configs/paths.py"""

    def test_repo_root_is_directory(self) -> None:
        from src.configs.paths import REPO_ROOT
        assert REPO_ROOT.is_dir(), f"REPO_ROOT is not a directory: {REPO_ROOT}"

    def test_dataset_dir_under_repo_root(self) -> None:
        from src.configs.paths import REPO_ROOT, DATASET_DIR
        assert DATASET_DIR == REPO_ROOT / "dataset"

    def test_messages_csv_path(self) -> None:
        from src.configs.paths import DATASET_DIR, MESSAGES_CSV
        assert MESSAGES_CSV == DATASET_DIR / "messages.csv"

    def test_output_csv_path(self) -> None:
        from src.configs.paths import DATASET_DIR, OUTPUT_CSV
        assert OUTPUT_CSV == DATASET_DIR / "output.csv"

    def test_env_override_missing_dir_raises(self, tmp_path: Path) -> None:
        """ROUTER_REPO_ROOT pointing to a non-existent path must raise."""
        fake = tmp_path / "does_not_exist"
        os.environ["ROUTER_REPO_ROOT"] = str(fake)
        try:
            # Force re-import by reloading the module
            import importlib
            import src.configs.paths as paths_mod
            with pytest.raises(EnvironmentError):
                paths_mod._resolve_repo_root()
        finally:
            del os.environ["ROUTER_REPO_ROOT"]

    def test_env_override_valid_dir(self, tmp_path: Path) -> None:
        """ROUTER_REPO_ROOT pointing to an existing directory is accepted."""
        import importlib
        import src.configs.paths as paths_mod
        os.environ["ROUTER_REPO_ROOT"] = str(tmp_path)
        try:
            result = paths_mod._resolve_repo_root()
            assert result == tmp_path.resolve()
        finally:
            del os.environ["ROUTER_REPO_ROOT"]

    def test_required_dataset_files_list_is_non_empty(self) -> None:
        from src.configs.paths import REQUIRED_DATASET_FILES
        assert len(REQUIRED_DATASET_FILES) >= 10

    def test_required_writable_dirs_list_is_non_empty(self) -> None:
        from src.configs.paths import REQUIRED_WRITABLE_DIRS
        assert len(REQUIRED_WRITABLE_DIRS) >= 3


# ============================================================================
# 2. Settings
# ============================================================================

class TestSettings:
    """src/configs/settings.py"""

    def test_routing_thresholds_in_range(self) -> None:
        from src.configs.settings import THRESHOLDS
        assert 0.0 < THRESHOLDS.notify_min_score <= 1.0
        assert 0.0 < THRESHOLDS.digest_min_score < THRESHOLDS.notify_min_score
        assert 0.0 < THRESHOLDS.scam_override_threshold <= 1.0
        assert 0.0 < THRESHOLDS.evidence_min_relevance <= 1.0
        assert THRESHOLDS.evidence_max_count >= 1

    def test_confidence_bounds(self) -> None:
        from src.configs.settings import CONFIDENCE
        assert 0.0 <= CONFIDENCE.min_confidence < CONFIDENCE.max_confidence <= 1.0
        assert 0.0 < CONFIDENCE.degraded_base < 1.0
        assert 0.0 < CONFIDENCE.safety_override_base < 1.0

    def test_batch_settings(self) -> None:
        from src.configs.settings import BATCH
        assert BATCH.csv_encoding == "utf-8"
        assert isinstance(BATCH.fail_on_error, bool)

    def test_logging_level_is_valid(self) -> None:
        from src.configs.settings import LOGGING as _LOG
        assert _LOG.level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    def test_cache_settings(self) -> None:
        from src.configs.settings import CACHE as _CACHE
        assert _CACHE.ext.startswith(".")


# ============================================================================
# 3. Writable directory creation
# ============================================================================

class TestEnsureWritableDirs:
    """ensure_writable_dirs() creates directories without touching dataset/."""

    def test_creates_cache_dir(self, tmp_path: Path) -> None:
        from src.utils.file_io import ensure_dir
        target = tmp_path / "cache" / "ocr"
        result = ensure_dir(target)
        assert result.is_dir()
        assert result == target

    def test_idempotent(self, tmp_path: Path) -> None:
        from src.utils.file_io import ensure_dir
        target = tmp_path / "a" / "b"
        ensure_dir(target)
        ensure_dir(target)  # must not raise
        assert target.is_dir()


# ============================================================================
# 4. Dataset file validation
# ============================================================================

class TestValidateDatasetFiles:
    """validate_dataset_files() returns errors for missing files."""

    def test_real_dataset_files_present(self) -> None:
        """All required files must exist in the actual dataset/."""
        from src.configs.paths import validate_dataset_files
        errors = validate_dataset_files()
        assert errors == [], f"Missing dataset files: {errors}"

    def test_missing_file_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Inject a non-existent path and confirm it is reported."""
        from src.configs import paths as _paths
        fake_path = tmp_path / "ghost.csv"
        original = _paths.REQUIRED_DATASET_FILES[:]
        monkeypatch.setattr(_paths, "REQUIRED_DATASET_FILES", [fake_path])
        errors = _paths.validate_dataset_files()
        assert len(errors) == 1
        assert "ghost.csv" in errors[0]
        monkeypatch.setattr(_paths, "REQUIRED_DATASET_FILES", original)


# ============================================================================
# 5. Logging initialisation
# ============================================================================

class TestLoggingSetup:
    """src/utils/logging_utils.py"""

    def setup_method(self) -> None:
        from src.utils.logging_utils import reset_logging
        reset_logging()

    def teardown_method(self) -> None:
        from src.utils.logging_utils import reset_logging
        reset_logging()

    def test_setup_creates_log_file(self, tmp_path: Path) -> None:
        from src.utils.logging_utils import setup_logging
        setup_logging(level="DEBUG", log_dir=tmp_path, filename="test.log")
        log_file = tmp_path / "test.log"
        assert log_file.is_file()

    def test_setup_is_idempotent(self, tmp_path: Path) -> None:
        from src.utils.logging_utils import setup_logging
        setup_logging(level="INFO", log_dir=tmp_path, filename="test.log")
        root_before = len(logging.getLogger().handlers)
        setup_logging(level="INFO", log_dir=tmp_path, filename="test.log")
        root_after = len(logging.getLogger().handlers)
        assert root_before == root_after

    def test_get_logger_returns_logger(self) -> None:
        from src.utils.logging_utils import get_logger
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_log_message_written_to_file(self, tmp_path: Path) -> None:
        from src.utils.logging_utils import setup_logging, get_logger
        import logging
        setup_logging(level="DEBUG", log_dir=tmp_path, filename="check.log")
        logger = get_logger("test_check")
        logger.info("hello from test")
        # Flush all handlers so the file write is complete before we read it.
        for h in logging.getLogger().handlers:
            h.flush()
        log_content = (tmp_path / "check.log").read_text(encoding="utf-8")
        assert "hello from test" in log_content


# ============================================================================
# 6. Types module
# ============================================================================

class TestTypes:
    """src/utils/types.py"""

    def test_output_columns_order(self) -> None:
        from src.utils.types import OUTPUT_COLUMNS
        assert OUTPUT_COLUMNS == (
            "message_id",
            "action",
            "message_type",
            "reason",
            "confidence",
            "evidence_message_ids",
        )

    def test_allowed_actions(self) -> None:
        from src.utils.types import ALLOWED_ACTIONS, is_valid_action
        assert is_valid_action("notify")
        assert is_valid_action("digest")
        assert is_valid_action("mute")
        assert not is_valid_action("ignore")
        assert not is_valid_action("")

    def test_allowed_message_types(self) -> None:
        from src.utils.types import ALLOWED_MESSAGE_TYPES, is_valid_message_type
        for mt in ("personal", "urgent", "event", "payment", "business_update",
                   "promotion", "greeting", "forward", "spam", "scam", "unknown"):
            assert is_valid_message_type(mt), f"{mt!r} should be valid"
        assert not is_valid_message_type("other")

    def test_confidence_validation(self) -> None:
        from src.utils.types import is_valid_confidence
        assert is_valid_confidence(0.0)
        assert is_valid_confidence(1.0)
        assert is_valid_confidence(0.75)
        assert not is_valid_confidence(-0.1)
        assert not is_valid_confidence(1.01)

    def test_no_evidence_sentinel(self) -> None:
        from src.utils.types import NO_EVIDENCE
        assert NO_EVIDENCE == "none"


# ============================================================================
# 7. file_io helpers
# ============================================================================

class TestFileIO:
    """src/utils/file_io.py"""

    def test_require_file_ok(self, tmp_path: Path) -> None:
        from src.utils.file_io import require_file
        f = tmp_path / "existing.txt"
        f.write_text("data")
        assert require_file(f) == f

    def test_require_file_missing(self, tmp_path: Path) -> None:
        from src.utils.file_io import require_file
        with pytest.raises(FileNotFoundError, match="missing.txt"):
            require_file(tmp_path / "missing.txt")

    def test_json_cache_roundtrip(self, tmp_path: Path) -> None:
        from src.utils.file_io import read_json_cache, write_json_cache
        path = tmp_path / "sub" / "cache.json"
        data = {"key": [1, 2, 3], "flag": True}
        write_json_cache(path, data)
        assert path.is_file()
        loaded = read_json_cache(path)
        assert loaded == data

    def test_json_cache_missing_returns_none(self, tmp_path: Path) -> None:
        from src.utils.file_io import read_json_cache
        result = read_json_cache(tmp_path / "nonexistent.json")
        assert result is None

    def test_json_cache_corrupt_returns_none(self, tmp_path: Path) -> None:
        from src.utils.file_io import read_json_cache
        bad = tmp_path / "bad.json"
        bad.write_text("{ not valid json !!!}", encoding="utf-8")
        result = read_json_cache(bad)
        assert result is None

    def test_read_csv_rows_basic(self, tmp_path: Path) -> None:
        from src.utils.file_io import read_csv_rows
        p = tmp_path / "test.csv"
        p.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
        rows = read_csv_rows(p)
        assert len(rows) == 2
        assert rows[0] == {"a": "1", "b": "2", "c": "3"}

    def test_read_csv_rows_multiline_quoted_field(self, tmp_path: Path) -> None:
        """Quoted fields with embedded newlines must parse as a single row."""
        from src.utils.file_io import read_csv_rows
        p = tmp_path / "multiline.csv"
        content = 'id,text\n1,"line one\nline two"\n2,"simple"\n'
        p.write_text(content, encoding="utf-8")
        rows = read_csv_rows(p)
        assert len(rows) == 2
        assert "line one" in rows[0]["text"]

    def test_read_csv_rows_missing_file(self, tmp_path: Path) -> None:
        from src.utils.file_io import read_csv_rows
        with pytest.raises(FileNotFoundError):
            read_csv_rows(tmp_path / "ghost.csv")

    def test_resolve_media_path_exists(self, tmp_path: Path) -> None:
        from src.utils.file_io import resolve_media_path
        img = tmp_path / "img_001.jpg"
        img.write_bytes(b"\xff\xd8")
        result = resolve_media_path("img_001.jpg", tmp_path)
        assert result == img

    def test_resolve_media_path_missing(self, tmp_path: Path) -> None:
        from src.utils.file_io import resolve_media_path
        result = resolve_media_path("img_999.jpg", tmp_path)
        assert result is None

    def test_resolve_media_path_empty(self, tmp_path: Path) -> None:
        from src.utils.file_io import resolve_media_path
        result = resolve_media_path("", tmp_path)
        assert result is None

    def test_get_csv_fieldnames(self, tmp_path: Path) -> None:
        from src.utils.file_io import get_csv_fieldnames
        p = tmp_path / "hdr.csv"
        p.write_text("x,y,z\n1,2,3\n", encoding="utf-8")
        names = get_csv_fieldnames(p)
        assert names == ["x", "y", "z"]


# ============================================================================
# 8. Bootstrap
# ============================================================================

class TestBootstrap:
    """src/bootstrap.py"""

    def setup_method(self) -> None:
        from src.utils.logging_utils import reset_logging
        reset_logging()

    def teardown_method(self) -> None:
        from src.utils.logging_utils import reset_logging
        reset_logging()

    def test_bootstrap_happy_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """bootstrap() completes without error on a valid dataset."""
        from src.configs import paths as _paths
        monkeypatch.setattr(_paths, "LOG_DIR", tmp_path / "logs")
        monkeypatch.setattr(_paths, "CACHE_DIR", tmp_path / "cache")
        monkeypatch.setattr(_paths, "OUTPUT_DIR", tmp_path / "outputs")
        monkeypatch.setattr(_paths, "OCR_CACHE_DIR", tmp_path / "cache" / "ocr")
        monkeypatch.setattr(_paths, "ASR_CACHE_DIR", tmp_path / "cache" / "asr")
        monkeypatch.setattr(_paths, "INDEX_CACHE_DIR", tmp_path / "cache" / "indexes")
        monkeypatch.setattr(_paths, "REQUIRED_WRITABLE_DIRS", [
            tmp_path / "logs", tmp_path / "cache", tmp_path / "outputs"
        ])

        import src.bootstrap as _boot
        monkeypatch.setattr(_boot, "ensure_writable_dirs", lambda: None)

        # Should not raise
        _boot.bootstrap(strict=False, log_level="WARNING")

    def test_bootstrap_missing_file_strict_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing required file with strict=True raises BootstrapError."""
        from src.configs import paths as _paths
        import src.bootstrap as _boot

        monkeypatch.setattr(_boot, "ensure_writable_dirs", lambda: None)
        monkeypatch.setattr(
            _paths, "REQUIRED_DATASET_FILES", [tmp_path / "nonexistent.csv"]
        )

        from src.utils.logging_utils import reset_logging
        reset_logging()
        with pytest.raises(_boot.BootstrapError):
            _boot.bootstrap(strict=True, log_level="WARNING")

    def test_bootstrap_missing_file_non_strict_no_raise(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing required file with strict=False is tolerated."""
        from src.configs import paths as _paths
        import src.bootstrap as _boot

        monkeypatch.setattr(_boot, "ensure_writable_dirs", lambda: None)
        monkeypatch.setattr(
            _paths, "REQUIRED_DATASET_FILES", [tmp_path / "nonexistent.csv"]
        )

        from src.utils.logging_utils import reset_logging
        reset_logging()
        _boot.bootstrap(strict=False, log_level="WARNING")  # must not raise

    def test_startup_summary_shape(self) -> None:
        from src.bootstrap import get_startup_summary
        summary = get_startup_summary()
        assert "env" in summary
        assert "repo_root" in summary
        assert "messages_csv_exists" in summary
        assert "features" in summary
        assert isinstance(summary["features"], dict)


# ============================================================================
# 9. Smoke test — bootstrap on real repo
# ============================================================================

class TestBootstrapSmoke:
    """End-to-end smoke test against the real dataset directory."""

    def setup_method(self) -> None:
        from src.utils.logging_utils import reset_logging
        reset_logging()

    def teardown_method(self) -> None:
        from src.utils.logging_utils import reset_logging
        reset_logging()

    def test_real_bootstrap(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        End-to-end smoke test: run bootstrap() against the real dataset/.
        Verifies that all required files pass validation and that the startup
        summary reports expected values.  Log file writing is covered by
        TestLoggingSetup above; we skip log file assertions here to avoid
        pytest handler ordering issues.
        """
        import src.bootstrap as _boot
        from src.configs import paths as _paths

        # Redirect writable dirs so the test does not pollute src/logs
        monkeypatch.setattr(_boot, "ensure_writable_dirs", lambda: None)

        # Redirect setup_logging to a no-op so log file location is irrelevant
        monkeypatch.setattr(_boot, "setup_logging", lambda **kw: None)

        # bootstrap() must not raise with the real dataset
        _boot.bootstrap(strict=True, log_level="WARNING")

        # Verify startup summary reports real repo paths
        summary = _boot.get_startup_summary()
        assert summary["messages_csv_exists"] is True, "messages.csv must exist"
        assert summary["output_csv_exists"] is True, "output.csv must exist"
        assert "repo_root" in summary

        # Verify all required dataset files pass validation independently
        errors = _paths.validate_dataset_files()
        assert errors == [], f"Dataset validation errors: {errors}"
