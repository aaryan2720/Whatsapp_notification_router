"""
src/configs/__init__.py
-----------------------
Package marker. Re-exports the primary configuration objects for
convenience so callers can do:

    from src.configs import PATHS, SETTINGS, LOGGING_SETTINGS

instead of importing from the individual modules.
"""

from src.configs.paths import (  # noqa: F401
    REPO_ROOT,
    DATASET_DIR,
    MESSAGES_CSV,
    OUTPUT_CSV,
    CACHE_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    REQUIRED_DATASET_FILES,
    REQUIRED_WRITABLE_DIRS,
    ensure_writable_dirs,
    validate_dataset_files,
)
from src.configs.settings import (  # noqa: F401
    ROUTER_ENV,
    LOGGING as LOGGING_SETTINGS,
    THRESHOLDS,
    CONFIDENCE,
    FEATURES,
    BATCH,
    CACHE as CACHE_SETTINGS,
)
