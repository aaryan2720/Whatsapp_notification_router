"""
src/models/prediction.py
-------------------------
Defines Prediction and DecisionExplanation domain models.

These models represent the output of the decision-making engine and are
fully serialized back into output.csv format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.utils.types import Action, MessageType


@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    """
    Structured reasoning explanation template and confidence builder.

    Used by Module 11 to construct reasons and confidence scores.
    """

    reason_template: str
    template_variables: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.50
    evidence_message_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def rendered_reason(self) -> str:
        """Render the reason string using template variables."""
        try:
            return self.reason_template.format(**self.template_variables)
        except (KeyError, ValueError):
            return self.reason_template


@dataclass(frozen=True, slots=True)
class Prediction:
    """
    Canonical representation of a single message routing prediction.

    Replaces the raw output dictionaries in Module 12 output writing.
    """

    message_id: str
    action: Action
    message_type: MessageType
    reason: str
    confidence: float
    evidence_message_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_csv_row(self) -> dict[str, str]:
        """
        Convert prediction into a dictionary mapping exactly to output.csv columns.
        """
        evidence_str = (
            ";".join(self.evidence_message_ids)
            if self.evidence_message_ids
            else "none"
        )
        return {
            "message_id": self.message_id,
            "action": self.action,
            "message_type": self.message_type,
            "reason": self.reason,
            "confidence": f"{self.confidence:.2f}",
            "evidence_message_ids": evidence_str,
        }

    def to_dict(self) -> dict[str, Any]:
        """Generic serialization dict representation."""
        return {
            "message_id": self.message_id,
            "action": self.action,
            "message_type": self.message_type,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence_message_ids": list(self.evidence_message_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prediction:
        """Deserialize from generic dict representation."""
        return cls(
            message_id=data["message_id"],
            action=data["action"],
            message_type=data["message_type"],
            reason=data["reason"],
            confidence=float(data["confidence"]),
            evidence_message_ids=tuple(data.get("evidence_message_ids", [])),
        )
