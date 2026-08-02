"""
src/models/evidence.py
----------------------
Defines the EvidenceRecord domain model.

This model is a typed, immutable representation of a single historical
evidence candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """
    Holds the complete set of ranked evidence for a message,
    allowing downstream modules (like routing and explanation engines)
    to consume features without performing queries.
    """

    ranked_evidence: tuple[EvidenceRecord, ...]
    ranking_scores: dict[str, float] = field(default_factory=dict)
    retrieval_metadata: dict[str, Any] = field(default_factory=dict)
    retrieval_confidence: float = 0.0
    retrieval_explanation: dict[str, str] = field(default_factory=dict)

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        """Convenience property returning just the message IDs of the evidence."""
        return tuple(ev.message_id for ev in self.ranked_evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ranked_evidence": [ev.to_dict() for ev in self.ranked_evidence],
            "ranking_scores": self.ranking_scores,
            "retrieval_metadata": self.retrieval_metadata,
            "retrieval_confidence": self.retrieval_confidence,
            "retrieval_explanation": self.retrieval_explanation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceBundle:
        ev_list = [EvidenceRecord.from_dict(d) for d in data.get("ranked_evidence", [])]
        return cls(
            ranked_evidence=tuple(ev_list),
            ranking_scores=data.get("ranking_scores", {}),
            retrieval_metadata=data.get("retrieval_metadata", {}),
            retrieval_confidence=float(data.get("retrieval_confidence", 0.0)),
            retrieval_explanation=data.get("retrieval_explanation", {}),
        )
