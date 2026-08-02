"""
src/configs/paths.py
--------------------
All filesystem path resolution for the Message Notification Router.

Paths are computed relative to the repository root (two levels above this
file) so there are no hardcoded absolute or machine-specific paths.

The repo root can be overridden via the ROUTER_REPO_ROOT environment variable
for packaged submissions where the layout differs.

Directory layout assumed:
  <repo_root>/
    dataset/          - read-only participant inputs
    src/              - development source of truth (this package)
    code/             - submission package (populated at packaging time)
"""

from __future__ import annotations

import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Repository root resolution
# ---------------------------------------------------------------------------

def _resolve_repo_root() -> Path:
    """
    Resolve the repository root directory.

    Resolution order:
    1. ROUTER_REPO_ROOT environment variable (absolute path)
    2. Inferred from this file's location: <repo_root>/src/configs/paths.py
       => go up 3 levels: paths.py -> configs -> src -> repo_root
    """
    env_override = os.environ.get("ROUTER_REPO_ROOT")
    if env_override:
        candidate = Path(env_override).resolve()
        if not candidate.is_dir():
            raise EnvironmentError(
                f"ROUTER_REPO_ROOT points to a non-existent directory: {candidate}"
            )
        return candidate

    # Infer relative to this file's location
    this_path = Path(__file__).resolve()
    
    # If this is within code/src/configs/paths.py, check if the sibling dataset/ exists
    # paths.py -> configs -> src -> code -> repo_root (4 levels up)
    if "code" in this_path.parts:
        candidate = this_path.parent.parent.parent.parent
        if (candidate / "dataset").is_dir():
            return candidate

    # Default fallback: go up 3 levels: paths.py -> configs -> src -> repo_root
    return this_path.parent.parent.parent


REPO_ROOT: Path = _resolve_repo_root()


# ---------------------------------------------------------------------------
# Dataset paths (read-only)
# ---------------------------------------------------------------------------

DATASET_DIR: Path = REPO_ROOT / "dataset"

# Primary input
MESSAGES_CSV: Path = DATASET_DIR / "messages.csv"

# Context tables
USERS_CSV: Path = DATASET_DIR / "users.csv"
GROUPS_CSV: Path = DATASET_DIR / "groups.csv"
GROUP_MEMBERS_CSV: Path = DATASET_DIR / "group_members.csv"
BUSINESS_ACCOUNTS_CSV: Path = DATASET_DIR / "business_accounts.csv"
USER_BUSINESS_HISTORY_CSV: Path = DATASET_DIR / "user_business_history.csv"

# History tables
MESSAGE_HISTORY_CSV: Path = DATASET_DIR / "message_history.csv"
MESSAGE_EVENTS_CSV: Path = DATASET_DIR / "message_events.csv"

# Media metadata
IMAGES_CSV: Path = DATASET_DIR / "images.csv"
VOICE_NOTES_CSV: Path = DATASET_DIR / "voice_notes.csv"
DAILY_NOTIFICATION_SUMMARY_CSV: Path = DATASET_DIR / "daily_notification_summary.csv"

# Reference examples (format only — never used as ground truth)
SAMPLE_MESSAGES_CSV: Path = DATASET_DIR / "sample_messages.csv"

# Media directories
MEDIA_DIR: Path = DATASET_DIR / "media"
IMAGES_MEDIA_DIR: Path = MEDIA_DIR / "images"
AUDIO_MEDIA_DIR: Path = MEDIA_DIR / "audio"

# Submission template (write destination)
OUTPUT_CSV: Path = DATASET_DIR / "output.csv"


# ---------------------------------------------------------------------------
# Runtime working directories (writable)
# ---------------------------------------------------------------------------

def _writable_dir(env_var: str, default: Path) -> Path:
    """
    Resolve a writable runtime directory.

    The environment variable takes precedence; otherwise use the default
    (which is relative to REPO_ROOT so the path stays portable).
    """
    override = os.environ.get(env_var)
    if override:
        return Path(override).resolve()
    return default


# src/ sub-directories used during development
_SRC_DIR: Path = REPO_ROOT / "src"

CACHE_DIR: Path = _writable_dir("ROUTER_CACHE_DIR", _SRC_DIR / "cache")
LOG_DIR: Path = _writable_dir("ROUTER_LOG_DIR", _SRC_DIR / "logs")
OUTPUT_DIR: Path = _writable_dir("ROUTER_OUTPUT_DIR", _SRC_DIR / "outputs")

# Cache sub-directories (names must match CacheSettings in settings.py)
OCR_CACHE_DIR: Path = CACHE_DIR / "ocr"
ASR_CACHE_DIR: Path = CACHE_DIR / "asr"
INDEX_CACHE_DIR: Path = CACHE_DIR / "indexes"


# ---------------------------------------------------------------------------
# Required dataset files — validated at startup
# ---------------------------------------------------------------------------

REQUIRED_DATASET_FILES: list[Path] = [
    MESSAGES_CSV,
    USERS_CSV,
    GROUPS_CSV,
    GROUP_MEMBERS_CSV,
    BUSINESS_ACCOUNTS_CSV,
    USER_BUSINESS_HISTORY_CSV,
    MESSAGE_HISTORY_CSV,
    MESSAGE_EVENTS_CSV,
    IMAGES_CSV,
    VOICE_NOTES_CSV,
    DAILY_NOTIFICATION_SUMMARY_CSV,
]

# Directories that must exist (created if missing, never in dataset/)
REQUIRED_WRITABLE_DIRS: list[Path] = [
    CACHE_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    OCR_CACHE_DIR,
    ASR_CACHE_DIR,
    INDEX_CACHE_DIR,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_writable_dirs() -> None:
    """Create all writable runtime directories if they do not already exist."""
    for directory in REQUIRED_WRITABLE_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def validate_dataset_files() -> list[str]:
    """
    Check that every required dataset file exists.

    Returns a list of error strings (empty list = all present).
    Does NOT raise — callers decide how to handle missing files.
    """
    errors: list[str] = []
    for path in REQUIRED_DATASET_FILES:
        if not path.is_file():
            errors.append(f"Missing required dataset file: {path}")
    return errors
