"""
src/utils/logging_utils.py
--------------------------
Logging initialisation for the Message Notification Router.

Provides a single `get_logger(name)` factory and a one-time `setup_logging()`
call that must be invoked at startup. After setup, every module simply calls:

    from src.utils.logging_utils import get_logger
    logger = get_logger(__name__)

Design choices:
- One shared log file under LOG_DIR (configurable via ROUTER_LOG_DIR).
- Console output mirrors the file at the same level.
- setup_logging() is idempotent — safe to call multiple times.
- No third-party dependencies.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Deferred import to avoid circular dependency; resolved at call time.
_setup_done: bool = False


def setup_logging(
    level: str | None = None,
    log_dir: Path | None = None,
    filename: str | None = None,
    fmt: str | None = None,
    date_fmt: str | None = None,
) -> None:
    """
    Initialise the root logger.  Call once at application startup.

    Parameters
    ----------
    level:    Override log level (default taken from LOGGING_SETTINGS.level).
    log_dir:  Override log directory (default taken from LOG_DIR).
    filename: Override log file name (default taken from LOGGING_SETTINGS.filename).
    fmt:      Override message format string.
    date_fmt: Override date format string.
    """
    global _setup_done
    if _setup_done:
        return

    # Resolve defaults from config — imported here to allow overrides in tests.
    from src.configs.settings import LOGGING as _LOG_CFG
    from src.configs.paths import LOG_DIR as _LOG_DIR, ensure_writable_dirs

    ensure_writable_dirs()

    resolved_level = (level or _LOG_CFG.level).upper()
    resolved_dir = log_dir or _LOG_DIR
    resolved_file = filename or _LOG_CFG.filename
    resolved_fmt = fmt or _LOG_CFG.format
    resolved_date = date_fmt or _LOG_CFG.date_format

    numeric_level = getattr(logging, resolved_level, logging.INFO)

    formatter = logging.Formatter(fmt=resolved_fmt, datefmt=resolved_date)

    # File handler — append mode so log survives restarts
    log_path = Path(resolved_dir) / resolved_file
    file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    # Console handler — always at INFO or above to keep output readable
    console_level = max(numeric_level, logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Add our handlers only if neither a FileHandler nor a StreamHandler to
    # stdout is already registered.  This guard is robust to pytest, which
    # injects its own capture handler before our setup runs.
    has_file_handler = any(
        isinstance(h, logging.FileHandler) for h in root_logger.handlers
    )
    if not has_file_handler:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    _setup_done = True

    root_logger.info(
        "Logging initialised | level=%s | file=%s", resolved_level, log_path
    )
    # Flush immediately so the log file contains the startup entry as soon
    # as setup_logging() returns (important for tests and smoke checks).
    for h in root_logger.handlers:
        h.flush()


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    If setup_logging() has not been called yet, a warning-level console-only
    logger is returned so modules do not crash during unit tests.
    """
    return logging.getLogger(name)


def reset_logging() -> None:
    """
    Reset logging state.  Used only in unit tests to isolate test runs.
    """
    global _setup_done
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    _setup_done = False
