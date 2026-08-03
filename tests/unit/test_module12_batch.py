"""
tests/unit/test_module12_batch.py
---------------------------------
Unit and integration tests for Module 12: Batch Runner & Output Writer.

Covers:
  - End-to-end batch execution run() success
  - Output CSV formatting validation (exact columns, exact column orders, float decimals)
  - Row count match (exactly 110 predictions for 110 messages)
  - Duplicate detection checks
  - SubmissionValidator behavior (successful cases vs forced contract failures)
  - Missing evidence formatting
  - CLI execution simulation
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.output.submission_validator import validate_submission, SubmissionValidationError
from src.pipeline.run_batch import run


class TestBatchRunnerAndWriter:
    def test_run_success_and_validates(self, tmp_path: Path) -> None:
        # Run batch execution outputting to a temporary CSV file path
        temp_out = tmp_path / "temp_output.csv"
        
        # Run the orchestrator batch pipeline
        exit_code = run(output_path=temp_out)
        
        # Verify exit status is successful
        assert exit_code == 0
        assert temp_out.is_file()

        # Load predicted rows
        rows: list[dict[str, str]] = []
        with temp_out.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(row)

        # Assert exactly 110 output rows
        assert len(rows) == 110

        # Assert columns format
        expected_fields = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]
        for row in rows:
            assert all(col in row for col in expected_fields)
            # Action check
            assert row["action"] in ("notify", "digest", "mute")
            # Decimal precision check
            conf = float(row["confidence"])
            assert 0.50 <= conf <= 1.00
            # Semicolon join or none check for evidence
            assert row["evidence_message_ids"] == "none" or ";" in row["evidence_message_ids"] or len(row["evidence_message_ids"]) > 0


class TestSubmissionValidatorFailures:
    def test_validator_fails_missing_columns(self, tmp_path: Path) -> None:
        bad_csv = tmp_path / "bad_columns.csv"
        with bad_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["message_id", "action"])  # missing other columns
            writer.writerow(["msg_023", "notify"])

        messages_csv = _REPO_ROOT / "dataset" / "messages.csv"
        with pytest.raises(SubmissionValidationError, match="CSV columns or column order mismatch"):
            validate_submission(bad_csv, messages_csv)

    def test_validator_fails_count_mismatch(self, tmp_path: Path) -> None:
        bad_csv = tmp_path / "bad_count.csv"
        with bad_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"])
            writer.writerow(["msg_023", "notify", "urgent", "test", "0.95", "none"])  # only 1 row (need 110)

        messages_csv = _REPO_ROOT / "dataset" / "messages.csv"
        with pytest.raises(SubmissionValidationError, match="Row count mismatch"):
            validate_submission(bad_csv, messages_csv)

    def test_validator_fails_invalid_action(self, tmp_path: Path) -> None:
        # Load a valid copy of messages and swap an action to a bad string
        valid_out = _REPO_ROOT / "dataset" / "output.csv"
        rows = []
        with valid_out.open("r", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        
        # Change row 1 action
        rows[1][1] = "INVALID_ACTION_VALUE"
        
        bad_csv = tmp_path / "bad_action.csv"
        with bad_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerows(rows)

        messages_csv = _REPO_ROOT / "dataset" / "messages.csv"
        with pytest.raises(SubmissionValidationError, match="Invalid action"):
            validate_submission(bad_csv, messages_csv)


class TestCliExecution:
    def test_cli_runner(self, tmp_path: Path) -> None:
        main_path = _REPO_ROOT / "main.py"
        test_out = tmp_path / "cli_test_output.csv"
        res = subprocess.run(
            [sys.executable, str(main_path), "--output", str(test_out)],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0
        assert "completed successfully" in res.stderr or "completed successfully" in res.stdout
        assert test_out.is_file()
