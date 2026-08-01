"""
src/models/__init__.py
----------------------
Package marker for core domain models. Re-exports all canonical domain structures:
  - MessageRecord
  - UserContext
  - ConversationContext
  - RoutingFeatures
  - EvidenceRecord
  - DecisionExplanation
  - Prediction
"""

from src.models.message import MessageRecord  # noqa: F401
from src.models.context import (  # noqa: F401
    UserContext,
    ConversationContext,
    RoutingFeatures,
    TextFeatures,
    ImageFeatures,
)
from src.models.evidence import EvidenceRecord, EvidenceBundle  # noqa: F401
from src.models.prediction import DecisionExplanation, Prediction  # noqa: F401
