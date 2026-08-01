"""
src/configs/settings.py
-----------------------
Central runtime configuration for the Message Notification Router.

All tuneable thresholds, feature flags, and runtime settings live here.
Environment variable overrides are documented inline.

Environment variables (all optional):
  ROUTER_ENV        - "development" | "production" (default: development)
  ROUTER_LOG_LEVEL  - "DEBUG" | "INFO" | "WARNING" | "ERROR" (default: INFO)
  ROUTER_CACHE_DIR  - override cache directory path
  ROUTER_OUTPUT_DIR - override output directory path
  ROUTER_LOG_DIR    - override log directory path
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Runtime environment
# ---------------------------------------------------------------------------

Environment = Literal["development", "production"]

ROUTER_ENV: Environment = os.environ.get("ROUTER_ENV", "development")  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoggingSettings:
    """Runtime logging configuration."""

    level: str = field(
        default_factory=lambda: os.environ.get("ROUTER_LOG_LEVEL", "INFO").upper()
    )
    format: str = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    date_format: str = "%Y-%m-%dT%H:%M:%S"
    # Runtime log file name (written under PATHS.log_dir)
    filename: str = "router.log"


LOGGING = LoggingSettings()


# ---------------------------------------------------------------------------
# Routing thresholds
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoutingThresholds:
    """
    Score thresholds used by the routing scorer (Module 10).

    These values are configured here so they can be tuned without touching
    scoring logic. All values are in the range [0.0, 1.0].
    """

    # Minimum score required to choose 'notify' over 'digest'
    notify_min_score: float = 0.65

    # Minimum score required to choose 'digest' over 'mute'
    digest_min_score: float = 0.35

    # Score margin below which confidence is dampened (ambiguous zone)
    ambiguous_margin: float = 0.10

    # Safety override: messages with scam/spam score above this are always muted
    scam_override_threshold: float = 0.70

    # Minimum evidence score to include an evidence ID in the output
    evidence_min_relevance: float = 0.30

    # Maximum number of evidence IDs emitted per prediction
    evidence_max_count: int = 3


THRESHOLDS = RoutingThresholds()


# ---------------------------------------------------------------------------
# Confidence calibration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfidenceSettings:
    """Controls confidence score generation (Module 11)."""

    # Clamp output confidence to this range
    min_confidence: float = 0.10
    max_confidence: float = 0.97

    # Base confidence when modality signal is unavailable (degraded path)
    degraded_base: float = 0.45

    # Base confidence for explicit safety overrides (scam/unsafe)
    safety_override_base: float = 0.88


CONFIDENCE = ConfidenceSettings()


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeatureFlags:
    """
    Toggle optional pipeline components on/off.

    Disabling OCR or ASR causes those messages to fall back to the
    metadata-only path with lower confidence.
    """

    enable_ocr: bool = True
    enable_asr: bool = True
    enable_evidence_retrieval: bool = True
    enable_personalization: bool = True
    # When True, log a debug entry for every scored message
    verbose_scoring: bool = ROUTER_ENV == "development"


FEATURES = FeatureFlags()


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BatchSettings:
    """Controls batch runner behaviour (Module 12)."""

    # Continue processing remaining messages even if one fails
    fail_on_error: bool = False

    # Flush the output writer after this many rows (0 = flush only at end)
    flush_interval: int = 50

    # Encoding for all CSV I/O
    csv_encoding: str = "utf-8"

    # Newline convention written to output.csv
    csv_newline: str = ""


BATCH = BatchSettings()


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CacheSettings:
    """Controls caching of expensive artifacts (OCR, ASR, retrieval indexes)."""

    enabled: bool = True
    # Subdirectory names under PATHS.cache_dir
    ocr_subdir: str = "ocr"
    asr_subdir: str = "asr"
    index_subdir: str = "indexes"
    # Cache file extension
    ext: str = ".json"


CACHE = CacheSettings()
