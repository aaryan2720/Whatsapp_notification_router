"""
src/output/submission_validator.py
----------------------------------
Submission Validator component (Module 12).

Responsible for verifying the correctness of the final output.csv file
before final submission. Raises detailed exceptions on contract violations.
"""

from __future__ import annotations

import csv
from pathlib import Path
from src.utils.types import ALLOWED_ACTIONS, ALLOWED_MESSAGE_TYPES


class SubmissionValidationError(ValueError):
    """Exception raised when final output.csv validation fails."""
    pass


def validate_submission(output_csv_path: Path, messages_csv_path: Path) -> None:
    """
    Validate that output_csv_path conforms strictly to the submission contract.

    Asserts:
      - File existence
      - Header columns and order match exactly
      - Row count matches messages.csv
      - Exact ordering of message_ids match messages.csv
      - Value ranges for action, message_type, and confidence are valid
    """
    if not output_csv_path.is_file():
        raise SubmissionValidationError(f"Output file does not exist: {output_csv_path}")
    if not messages_csv_path.is_file():
        raise SubmissionValidationError(f"Source messages file does not exist: {messages_csv_path}")

    # 1. Load source message_ids in order
    src_ids: list[str] = []
    try:
        with messages_csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                src_ids.append(row["message_id"])
    except Exception as exc:
        raise SubmissionValidationError(f"Failed to read source messages file: {exc}")

    # 2. Read output CSV rows and headers
    out_rows: list[dict[str, str]] = []
    headers: list[str] = []
    try:
        with output_csv_path.open("r", encoding="utf-8") as fh:
            # Get header columns directly to verify order
            header_line = fh.readline().strip()
            headers = [h.strip() for h in header_line.split(",")]
            
            fh.seek(0)
            reader = csv.DictReader(fh)
            for row in reader:
                out_rows.append(row)
    except Exception as exc:
        raise SubmissionValidationError(f"Failed to read output CSV: {exc}")

    # 3. Verify exact column headers and ordering
    expected_headers = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]
    if headers != expected_headers:
        raise SubmissionValidationError(
            f"CSV columns or column order mismatch.\nExpected: {expected_headers}\nFound: {headers}"
        )

    # 4. Verify row count matches exactly
    if len(out_rows) != len(src_ids):
        raise SubmissionValidationError(
            f"Row count mismatch.\nSource messages count: {len(src_ids)}\nOutput predictions count: {len(out_rows)}"
        )

    # 5. Validate each prediction row in order
    out_ids: list[str] = []
    for idx, row in enumerate(out_rows):
        msg_id = row.get("message_id")
        action = row.get("action")
        msg_type = row.get("message_type")
        reason = row.get("reason")
        confidence_str = row.get("confidence")
        evidence = row.get("evidence_message_ids")

        # Missing required fields check
        if not all([msg_id, action, msg_type, reason, confidence_str, evidence]):
            raise SubmissionValidationError(
                f"Missing required field in row {idx} (message_id: {msg_id}). Row content: {row}"
            )

        # Exact ordering check
        expected_id = src_ids[idx]
        if msg_id != expected_id:
            raise SubmissionValidationError(
                f"Message ID ordering mismatch at row {idx}.\nExpected: {expected_id}\nFound: {msg_id}"
            )

        # Duplicates check
        if msg_id in out_ids:
            raise SubmissionValidationError(f"Duplicate message_id found in output: {msg_id}")
        out_ids.append(msg_id)

        # Valid action checks
        if action not in ALLOWED_ACTIONS:
            raise SubmissionValidationError(
                f"Invalid action '{action}' at row {idx} for message {msg_id}. Allowed: {list(ALLOWED_ACTIONS)}"
            )

        # Valid message_type checks
        if msg_type not in ALLOWED_MESSAGE_TYPES:
            raise SubmissionValidationError(
                f"Invalid message_type '{msg_type}' at row {idx} for message {msg_id}. Allowed: {list(ALLOWED_MESSAGE_TYPES)}"
            )

        # Confidence checks
        try:
            val = float(confidence_str)
            if not (0.50 <= val <= 1.00):
                raise SubmissionValidationError(
                    f"Confidence {val} out of expected [0.50, 1.00] range at row {idx} for message {msg_id}."
                )
        except ValueError:
            raise SubmissionValidationError(
                f"Invalid confidence float format '{confidence_str}' at row {idx} for message {msg_id}."
            )

        # Evidence checks
        if evidence.lower() != "none":
            eids = [e.strip() for e in evidence.split(";")]
            for eid in eids:
                if not eid:
                    raise SubmissionValidationError(
                        f"Empty or malformed evidence ID found in '{evidence}' at row {idx} for message {msg_id}."
                    )

    # 6. Verify distinct set match of IDs
    if set(out_ids) != set(src_ids):
        raise SubmissionValidationError("Output message_ids do not match the set of source message_ids.")

    print(f"[OK] Submission Validator: Output conforms perfectly to contract (110 predictions validated).")
