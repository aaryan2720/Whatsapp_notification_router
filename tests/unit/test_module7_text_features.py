"""
tests/unit/test_module7_text_features.py
----------------------------------------
Unit tests for Module 7: Text Feature Extraction.

Covers:
  - Scam examples (lottery, delivery fees, suspicious IP and domain links)
  - Promotions (discounts, exclusive sales, promo codes)
  - Greetings (formal/informal)
  - Payment reminders (bills, receipts, invoices)
  - OTP messages (with verification code and digits)
  - URL and domain extraction (regular and port variants)
  - Empty text fallbacks
  - Multiline messages parsing
  - Mixed-language text features
  - Integration/regression smoke test on the real dataset
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.models import TextFeatures
from src.multimodal.text_features import extract_text_features


class TestTextFeatureExtraction:
    def test_empty_text(self) -> None:
        features = extract_text_features("")
        assert features.char_count == 0
        assert features.word_count == 0
        assert features.line_count == 0
        assert features.is_greeting is False
        assert features.extracted_urls == ()

    def test_greetings(self) -> None:
        text = "Hello! Hope you are doing well."
        features = extract_text_features(text)
        assert features.is_greeting is True
        assert features.is_scam_signal is False

    def test_payment_reminders(self) -> None:
        text = "Your invoice #2026 is due now. Please complete the bill payment."
        features = extract_text_features(text)
        assert features.is_payment_indicated is True
        assert features.is_urgency_indicated is False

    def test_otp_detection(self) -> None:
        # Happy path OTP
        text = "Your WhatsApp verification code is 482934. Do not share this OTP."
        features = extract_text_features(text)
        assert features.has_otp_pattern is True

        # Number present but no OTP keywords
        text_no_otp = "There are 482934 stars in the sky."
        features_no_otp = extract_text_features(text_no_otp)
        assert features_no_otp.has_otp_pattern is False

    def test_promotions(self) -> None:
        text = "Exclusive limited time offer: Get 50% discount on your first order! Buy now."
        features = extract_text_features(text)
        assert features.is_promotion is True
        assert features.is_urgency_indicated is True  # due to "limited time offer"

    def test_scam_examples_and_suspicious_links(self) -> None:
        # 1. Lottery keywords
        text_lotto = "Congratulations! You won the Mega cash reward lottery. Call now."
        features_lotto = extract_text_features(text_lotto)
        assert features_lotto.is_scam_signal is True

        # 2. Suspicious IP link
        text_ip = "Urgent: Verify your account immediately at http://192.168.1.1/login"
        features_ip = extract_text_features(text_ip)
        assert features_ip.has_suspicious_link is True
        assert features_ip.is_scam_signal is True

        # 3. Suspicious TLD
        text_tld = "Click here for free reward: https://free-cash-deals.xyz"
        features_tld = extract_text_features(text_tld)
        assert features_tld.has_suspicious_link is True
        assert "free-cash-deals.xyz" in features_tld.extracted_domains

    def test_url_and_domain_extraction(self) -> None:
        text = "Check http://google.com and https://my-dashboard.in:8080/reports for details."
        features = extract_text_features(text)
        assert len(features.extracted_urls) == 2
        assert "google.com" in features.extracted_domains
        assert "my-dashboard.in" in features.extracted_domains

    def test_multiline_messages(self) -> None:
        text = "Dear Customer,\n\nYour account has a critical update.\n\nTeam Services."
        features = extract_text_features(text)
        assert features.line_count == 5
        assert features.is_business_language is True

    def test_mixed_language_and_special_chars(self) -> None:
        text = "Hi, code is 998811 OTP verification done. Dhanyawad!"
        features = extract_text_features(text)
        assert features.is_greeting is True
        assert features.has_otp_pattern is True

    def test_determinism(self) -> None:
        text = "Verify your invoice at https://verify-bank.com"
        f1 = extract_text_features(text)
        f2 = extract_text_features(text)
        assert f1 == f2


# ===========================================================================
# 3. Regression test / Full Dataset load check
# ===========================================================================

class TestRealTextFeaturesSmoke:
    def test_real_messages_text_feature_extraction(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        from src.models import MessageRecord
        
        bundle = load_all_datasets()
        
        # Test extraction on real messages
        for m_row in bundle.messages[:15]:
            msg = MessageRecord.from_row(m_row)
            features = extract_text_features(msg.message_text)
            assert isinstance(features, TextFeatures)
            assert features.char_count == len(msg.message_text)
            assert isinstance(features.extracted_urls, tuple)
