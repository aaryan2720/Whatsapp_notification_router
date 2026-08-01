"""
src/bootstrap.py
----------------
Application startup and pre-flight validation.

Call `bootstrap()` once at the beginning of any entry point (code/main.py,
tests, batch runner). It:

1. Sets up logging.
2. Ensures all writable runtime directories exist.
3. Validates that every required dataset file is present.
4. Logs a structured startup banner.

The function raises `BootstrapError` on unrecoverable problems so the
caller can exit cleanly instead of failing deep inside the pipeline.

Example
-------
    from src.bootstrap import bootstrap
    bootstrap()  # will raise BootstrapError if dataset files are missing
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.configs.paths import (
    REPO_ROOT,
    DATASET_DIR,
    MESSAGES_CSV,
    OUTPUT_CSV,
    ensure_writable_dirs,
    validate_dataset_files,
)
from src.configs.settings import ROUTER_ENV, LOGGING as _LOG_CFG, FEATURES
from src.utils.logging_utils import setup_logging, get_logger

logger = get_logger(__name__)


class BootstrapError(RuntimeError):
    """Raised when a startup pre-flight check fails unrecoverably."""


def bootstrap(
    *,
    strict: bool = True,
    log_level: str | None = None,
) -> None:
    """
    Initialise the runtime environment.

    Parameters
    ----------
    strict:    If True (default), missing dataset files raise BootstrapError.
               Set to False in test environments to allow partial datasets.
    log_level: Override the configured log level (useful in tests/scripts).

    Raises
    ------
    BootstrapError if strict=True and required files are missing.
    """
    # 1. Initialise logging first so all subsequent steps are visible.
    setup_logging(level=log_level)

    logger.info("=" * 60)
    logger.info("Message Notification Router — startup")
    logger.info("  env        : %s", ROUTER_ENV)
    logger.info("  repo_root  : %s", REPO_ROOT)
    logger.info("  dataset    : %s", DATASET_DIR)
    logger.info("  python     : %s", sys.version.split()[0])
    logger.info("  strict     : %s", strict)
    logger.info("  features   : ocr=%s  asr=%s  retrieval=%s  personalization=%s",
                FEATURES.enable_ocr, FEATURES.enable_asr,
                FEATURES.enable_evidence_retrieval, FEATURES.enable_personalization)
    logger.info("=" * 60)

    # 2. Create writable runtime directories.
    logger.info("Creating runtime directories...")
    ensure_writable_dirs()
    logger.info("Runtime directories ready.")

    # 3. Validate dataset files.
    logger.info("Validating dataset files...")
    errors = validate_dataset_files()

    if errors:
        for err in errors:
            logger.error(err)
        if strict:
            raise BootstrapError(
                f"Bootstrap failed: {len(errors)} required dataset file(s) missing. "
                "See log for details."
            )
        else:
            logger.warning(
                "Non-strict mode: %d missing dataset file(s) tolerated.", len(errors)
            )
    else:
        logger.info("All required dataset files present.")

    # 4. Confirm output template is reachable.
    if OUTPUT_CSV.is_file():
        logger.info("Output template found: %s", OUTPUT_CSV)
    else:
        logger.warning("Output template not found at %s — will be created.", OUTPUT_CSV)

    logger.info("Bootstrap complete.")


def get_startup_summary() -> dict[str, object]:
    """
    Return a dict of key runtime facts for debugging or diagnostics.
    Does not trigger logging or file system side effects.
    """
    return {
        "env": ROUTER_ENV,
        "repo_root": str(REPO_ROOT),
        "dataset_dir": str(DATASET_DIR),
        "messages_csv_exists": MESSAGES_CSV.is_file(),
        "output_csv_exists": OUTPUT_CSV.is_file(),
        "python_version": sys.version.split()[0],
        "features": {
            "ocr": FEATURES.enable_ocr,
            "asr": FEATURES.enable_asr,
            "retrieval": FEATURES.enable_evidence_retrieval,
            "personalization": FEATURES.enable_personalization,
        },
    }
