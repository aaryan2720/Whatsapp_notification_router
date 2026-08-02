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
class DecisionScores:
    """
    Independent scores produced by every major feature family.
    Used for explainability, debugging, and calibration.
    """

    urgency_score: float = 0.0
    relationship_score: float = 0.0
    trust_score: float = 0.0
    business_score: float = 0.0
    promotion_score: float = 0.0
    spam_score: float = 0.0
    scam_score: float = 0.0
    evidence_score: float = 0.0
    multimodal_score: float = 0.0
    conversation_score: float = 0.0
    personalization_score: float = 0.0
    notification_fatigue_score: float = 0.0
    quiet_hours_score: float = 0.0
    final_priority_score: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "urgency_score": self.urgency_score,
            "relationship_score": self.relationship_score,
            "trust_score": self.trust_score,
            "business_score": self.business_score,
            "promotion_score": self.promotion_score,
            "spam_score": self.spam_score,
            "scam_score": self.scam_score,
            "evidence_score": self.evidence_score,
            "multimodal_score": self.multimodal_score,
            "conversation_score": self.conversation_score,
            "personalization_score": self.personalization_score,
            "notification_fatigue_score": self.notification_fatigue_score,
            "quiet_hours_score": self.quiet_hours_score,
            "final_priority_score": self.final_priority_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionScores:
        return cls(
            urgency_score=float(data.get("urgency_score", 0.0)),
            relationship_score=float(data.get("relationship_score", 0.0)),
            trust_score=float(data.get("trust_score", 0.0)),
            business_score=float(data.get("business_score", 0.0)),
            promotion_score=float(data.get("promotion_score", 0.0)),
            spam_score=float(data.get("spam_score", 0.0)),
            scam_score=float(data.get("scam_score", 0.0)),
            evidence_score=float(data.get("evidence_score", 0.0)),
            multimodal_score=float(data.get("multimodal_score", 0.0)),
            conversation_score=float(data.get("conversation_score", 0.0)),
            personalization_score=float(data.get("personalization_score", 0.0)),
            notification_fatigue_score=float(data.get("notification_fatigue_score", 0.0)),
            quiet_hours_score=float(data.get("quiet_hours_score", 0.0)),
            final_priority_score=float(data.get("final_priority_score", 0.0)),
        )


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """
    Trace logs of intermediate rule inputs, threshold crossings, and final reasoning.
    Used for reproducibility and inspection.
    """

    contributions: dict[str, float] = field(default_factory=dict)
    rule_overrides: list[str] = field(default_factory=list)
    thresholds_crossed: list[str] = field(default_factory=list)
    final_reasoning_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "contributions": self.contributions,
            "rule_overrides": self.rule_overrides,
            "thresholds_crossed": self.thresholds_crossed,
            "final_reasoning_path": self.final_reasoning_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionTrace:
        return cls(
            contributions=dict(data.get("contributions", {})),
            rule_overrides=list(data.get("rule_overrides", [])),
            thresholds_crossed=list(data.get("thresholds_crossed", [])),
            final_reasoning_path=data.get("final_reasoning_path", ""),
        )


@dataclass(frozen=True, slots=True)
class ReasonFragments:
    """
    Structured key-value flags summarizing rule and context contributions.
    Passed from scoring layer to explainability layer without re-running routing logic.
    """

    verified_business: bool = False
    trusted_sender: bool = False
    payment_due: bool = False
    otp_detected: bool = False
    recent_similar_message: bool = False
    user_usually_opens: bool = False
    promotion_detected: bool = False
    phishing_detected: bool = False
    muted_group: bool = False
    quiet_hours: bool = False
    multimodal_agreement: bool = False
    strong_historical_evidence: bool = False
    weak_evidence: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "verified_business": self.verified_business,
            "trusted_sender": self.trusted_sender,
            "payment_due": self.payment_due,
            "otp_detected": self.otp_detected,
            "recent_similar_message": self.recent_similar_message,
            "user_usually_opens": self.user_usually_opens,
            "promotion_detected": self.promotion_detected,
            "phishing_detected": self.phishing_detected,
            "muted_group": self.muted_group,
            "quiet_hours": self.quiet_hours,
            "multimodal_agreement": self.multimodal_agreement,
            "strong_historical_evidence": self.strong_historical_evidence,
            "weak_evidence": self.weak_evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasonFragments:
        return cls(
            verified_business=data.get("verified_business", False),
            trusted_sender=data.get("trusted_sender", False),
            payment_due=data.get("payment_due", False),
            otp_detected=data.get("otp_detected", False),
            recent_similar_message=data.get("recent_similar_message", False),
            user_usually_opens=data.get("user_usually_opens", False),
            promotion_detected=data.get("promotion_detected", False),
            phishing_detected=data.get("phishing_detected", False),
            muted_group=data.get("muted_group", False),
            quiet_hours=data.get("quiet_hours", False),
            multimodal_agreement=data.get("multimodal_agreement", False),
            strong_historical_evidence=data.get("strong_historical_evidence", False),
            weak_evidence=data.get("weak_evidence", False),
        )


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
    decision_scores: DecisionScores | None = None
    decision_trace: DecisionTrace | None = None
    reason_fragments: ReasonFragments | None = None

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
            "decision_scores": self.decision_scores.to_dict() if self.decision_scores else None,
            "decision_trace": self.decision_trace.to_dict() if self.decision_trace else None,
            "reason_fragments": self.reason_fragments.to_dict() if self.reason_fragments else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prediction:
        """Deserialize from generic dict representation."""
        ds_data = data.get("decision_scores")
        ds = DecisionScores.from_dict(ds_data) if ds_data else None

        dt_data = data.get("decision_trace")
        dt = DecisionTrace.from_dict(dt_data) if dt_data else None

        rf_data = data.get("reason_fragments")
        rf = ReasonFragments.from_dict(rf_data) if rf_data else None

        return cls(
            message_id=data["message_id"],
            action=data["action"],
            message_type=data["message_type"],
            reason=data["reason"],
            confidence=float(data["confidence"]),
            evidence_message_ids=tuple(data.get("evidence_message_ids", [])),
            decision_scores=ds,
            decision_trace=dt,
            reason_fragments=rf,
        )
