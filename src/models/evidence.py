"""
src/models/evidence.py
----------------------
Defines the EvidenceRecord domain model.

This model is a typed, immutable representation of a single historical
evidence candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """
    Typed record representing a historical message retrieved as evidence.

    Used by the evidence retrieval index (Module 6).
    """

    message_id: str
    relevance_score: float
    matching_criteria: str  # e.g., "sender_match", "group_match", "content_similarity"
    created_at: datetime | None = None
    message_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "relevance_score": self.relevance_score,
            "matching_criteria": self.matching_criteria,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "message_text": self.message_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceRecord:
        created = data.get("created_at")
        created_dt = datetime.fromisoformat(created) if created else None
        return cls(
            message_id=data["message_id"],
            relevance_score=data["relevance_score"],
            matching_criteria=data["matching_criteria"],
            created_at=created_dt,
            message_text=data.get("message_text", ""),
        )
