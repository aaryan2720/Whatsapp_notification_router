"""
tests/unit/test_module11_output.py
----------------------------------
Unit tests for Module 11: Reason and Confidence Builder.

Covers:
  - Explanation generation (templates)
  - ReasonFragments mapping
  - Confidence normalization & clamping
  - Evidence formatting and deduplication (maintaining order)
  - Missing evidence ("none" emission)
  - Deterministic explanations
  - Regression against Modules 1-10
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.models import Prediction, ReasonFragments, DecisionTrace
from src.output.reason_builder import (
    build_deterministic_reason,
    finalize_confidence,
    format_evidence_message_ids,
    build_final_prediction,
)


class TestReasonBuilder:
    def test_phishing_scam_reason(self) -> None:
        frag = ReasonFragments(phishing_detected=True)
        reason = build_deterministic_reason("mute", "scam", [], frag)
        assert "Potential phishing attempt" in reason

    def test_business_opt_out_reason(self) -> None:
        frag = ReasonFragments(promotion_detected=True)
        reason = build_deterministic_reason("mute", "promotion", ["Business Opt-Out Override"], frag)
        assert "opted-out business" in reason

    def test_otp_bypass_reason(self) -> None:
        frag = ReasonFragments(otp_detected=True)
        reason = build_deterministic_reason("notify", "urgent", ["OTP Bypass Override"], frag)
        assert "Urgent verification code" in reason

    def test_payment_due_verified_business_reason(self) -> None:
        frag = ReasonFragments(payment_due=True, verified_business=True)
        reason = build_deterministic_reason("notify", "payment", [], frag)
        assert "Verified business payment reminder" in reason

    def test_strong_evidence_reason(self) -> None:
        frag = ReasonFragments(strong_historical_evidence=True, user_usually_opens=True)
        reason = build_deterministic_reason("notify", "personal", [], frag)
        assert "Similar messages were previously opened" in reason


class TestConfidenceNormalization:
    def test_finalize_confidence_clamping(self) -> None:
        # High value clamped to 1.0
        assert finalize_confidence(1.2) == 1.0
        # Low value clamped to 0.50
        assert finalize_confidence(0.3) == 0.50
        # Regular values rounded to 2 decimal places
        assert finalize_confidence(0.856) == 0.86


class TestEvidenceFormatting:
    def test_evidence_deduplication_preserves_order(self) -> None:
        ids = ("msg_01", "msg_02", "msg_01", "msg_03", "none", "")
        formatted = format_evidence_message_ids(ids)
        assert formatted == ("msg_01", "msg_02", "msg_03")

    def test_missing_evidence_emits_none(self) -> None:
        assert format_evidence_message_ids(()) == ("none",)
        assert format_evidence_message_ids(("none", "")) == ("none",)


class TestPredictionFinalization:
    def test_build_final_prediction_pipeline(self) -> None:
        trace = DecisionTrace(
            contributions={},
            rule_overrides=["OTP Bypass Override"],
            thresholds_crossed=[],
            final_reasoning_path="OTP Override triggered",
        )
        frag = ReasonFragments(otp_detected=True)
        preliminary = Prediction(
            message_id="msg_100",
            action="notify",
            message_type="urgent",
            reason="preliminary reason log",
            confidence=0.888,
            evidence_message_ids=("msg_05", "msg_05", "none"),
            decision_scores=None,
            decision_trace=trace,
            reason_fragments=frag,
        )

        final = build_final_prediction(preliminary)

        assert final.message_id == "msg_100"
        assert final.action == "notify"
        assert final.message_type == "urgent"
        # Reason mapped to OTP template
        assert final.reason == "Urgent verification code requiring immediate attention."
        # Confidence finalized to 0.89
        assert final.confidence == 0.89
        # Evidence cleaned and deduplicated
        assert final.evidence_message_ids == ("msg_05",)
