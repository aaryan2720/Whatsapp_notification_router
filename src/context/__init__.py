"""
src/context/__init__.py
-----------------------
Package marker for context builder modules.
Re-exports:
  - build_user_context
  - compute_user_historical_rates
"""

from src.context.user_context import build_user_context  # noqa: F401
from src.context.user_aggregates import compute_user_historical_rates  # noqa: F401
