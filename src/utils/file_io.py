"""
src/utils/file_io.py
--------------------
Filesystem helpers shared across modules.

Responsibilities:
- Safe file existence checks with clear error messages
- Atomic-safe JSON cache read/write (used by OCR, ASR, index modules)
- CSV read helpers that never mutate the source file
- Path normalisation utilities

No business logic lives here.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Existence / safety checks
# ---------------------------------------------------------------------------

def require_file(path: Path, label: str = "file") -> Path:
    """
    Assert that a file exists and return it.

    Raises
    ------
    FileNotFoundError with a descriptive message if missing.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"Required {label} not found: {path}"
        )
    return path


def file_exists(path: Path) -> bool:
    """Return True only if path exists and is a regular file."""
    return path.is_file()


def dir_exists(path: Path) -> bool:
    """Return True only if path exists and is a directory."""
    return path.is_dir()


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it does not exist. Return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# JSON cache helpers
# ---------------------------------------------------------------------------

def read_json_cache(path: Path) -> Any | None:
    """
    Load a JSON cache file.

    Returns None if the file does not exist or cannot be parsed.
    Never raises — cache misses are silent.
    """
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def write_json_cache(path: Path, data: Any) -> None:
    """
    Write data to a JSON cache file atomically.

    Writes to a temp file first, then renames, so a crash mid-write
    does not corrupt the cache.
    """
    ensure_dir(path.parent)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        # Atomic rename (works on Windows; overwrites dest if present)
        Path(tmp).replace(path)
    except Exception:
        # Clean up the temp file on failure; do not propagate cache errors
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def read_csv_rows(
    path: Path,
    encoding: str = "utf-8",
) -> list[dict[str, str]]:
    """
    Read a CSV file into a list of row dicts.

    - Uses csv.DictReader so quoted multi-line fields are handled correctly.
    - Returns an empty list if the file is empty or has only a header.
    - Does NOT mutate the source file.

    Raises
    ------
    FileNotFoundError  if path does not exist.
    ValueError         if the file cannot be parsed as CSV.
    """
    require_file(path, label="CSV")
    try:
        with path.open(newline="", encoding=encoding) as fh:
            reader = csv.DictReader(fh)
            return [dict(row) for row in reader]
    except csv.Error as exc:
        raise ValueError(f"Failed to parse CSV {path}: {exc}") from exc


def get_csv_fieldnames(path: Path, encoding: str = "utf-8") -> list[str]:
    """
    Return the header row of a CSV file as a list of column names.

    Raises FileNotFoundError if the file does not exist.
    Returns an empty list if the file is empty.
    """
    require_file(path, label="CSV")
    with path.open(newline="", encoding=encoding) as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or [])


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------

def resolve_media_path(
    media_filename: str,
    media_dir: Path,
) -> Path | None:
    """
    Resolve a media filename to its full path.

    Returns None if the file does not exist, enabling graceful degradation
    in the multimodal pipeline.
    """
    if not media_filename:
        return None
    candidate = media_dir / media_filename
    return candidate if candidate.is_file() else None


def normalise_path(raw: str | Path) -> Path:
    """Convert a raw string or Path to a resolved absolute Path."""
    return Path(raw).resolve()
