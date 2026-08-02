"""
src/multimodal/text_features.py
-------------------------------
Stage 1: Text Feature Extraction.

Parses raw message text to extract deterministic, reusable features
concerning urgency, billing, authentication (OTPs), URLs, suspicious links,
promotional vocabulary, and style cues.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse
from src.models.context import TextFeatures

# Regular Expressions
_URL_RE = re.compile(r"https?://[^\s]+")
_IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
_OTP_RE = re.compile(r"\b\d{4,8}\b")

# Keyword dictionaries for deterministic matching
_KEYWORDS = {
    "urgency": {
        "urgent", "immediate", "action required", "as soon as possible",
        "quick heads-up", "heads-up", "important notice", "attention required",
        "verify now", "immediate action", "at once", "critical update",
        "limited time offer", "limited time"
    },
    "payment": {
        "payment", "invoice", "receipt", "due", "overdue", "bill",
        "charge", "fee", "recharge", "balance", "pay now", "transferred",
        "amount due", "outstanding"
    },
    "otp": {
        "otp", "verification code", "one-time password", "security code",
        "auth code", "verify code", "confirm code", "temp password"
    },
    "business": {
        "dear customer", "dear client", "dear user", "team banking",
        "banking services", "customer support", "please review", "kindly update",
        "regarding your account", "valuable customer"
    },
    "greeting": {
        "hi", "hello", "dear", "hey", "good morning", "good afternoon",
        "good evening", "greetings"
    },
    "promotion": {
        "sale", "discount", "promo", "coupon", "cashback", "win a",
        "exclusive offer", "limited time offer", "free gift", "buy now",
        "special discount", "off your first", "clearance"
    },
    "scam": {
        "lottery", "lotto", "prize draw", "suspended account", "compromised",
        "unauthorized transaction", "claim your prize", "reattempt fee",
        "release package", "verify your credentials", "cash reward", "won a cash"
    },
    "event": {
        "meeting", "webinar", "parent-teacher", "parent teacher", "scheduled",
        "announcement", "calendar", "invite", "workshop", "discussion", "agenda"
    },
    "forwarded": {
        "forwarded", "forward this", "share with", "chain message", "circulate"
    }
}


def _matches_any_keyword(lower_text: str, keywords: set[str]) -> bool:
    """Helper to check if any keyword exists in lowercased text."""
    return any(kw in lower_text for kw in keywords)


def extract_text_features(text: str) -> TextFeatures:
    """
    Extract deterministic routing cues and statistics from the raw text.

    Guarantees no state mutations and returns an immutable TextFeatures object.
    """
    if not text:
        return TextFeatures()

    # Pre-lowercase input text once
    lower_text = text.lower()

    # 1. Lexical statistics
    char_count = len(text)
    words = text.split()
    word_count = len(words)
    line_count = text.count("\n") + 1 if text else 0

    # 2. Keyword matches
    is_urg = _matches_any_keyword(lower_text, _KEYWORDS["urgency"])
    is_pay = _matches_any_keyword(lower_text, _KEYWORDS["payment"])
    is_biz = _matches_any_keyword(lower_text, _KEYWORDS["business"])
    is_greet = _matches_any_keyword(lower_text, _KEYWORDS["greeting"])
    is_promo = _matches_any_keyword(lower_text, _KEYWORDS["promotion"])
    is_scam = _matches_any_keyword(lower_text, _KEYWORDS["scam"])
    is_evt = _matches_any_keyword(lower_text, _KEYWORDS["event"])
    has_fwd = _matches_any_keyword(lower_text, _KEYWORDS["forwarded"])

    # 3. OTP Detection
    has_otp = False
    if _OTP_RE.search(text) and _matches_any_keyword(lower_text, _KEYWORDS["otp"]):
        has_otp = True

    # 4. URL and Domain Extraction
    urls = _URL_RE.findall(text)
    domains: list[str] = []
    has_sus_link = False

    for url in urls:
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path.split("/")[0]
        # Clean port if present
        domain = netloc.split(":")[0].lower() if netloc else ""
        if domain:
            domains.append(domain)

        # Suspicious url checks
        # Check IP address link
        if _IP_RE.search(domain):
            has_sus_link = True

        # Check suspicious TLDs often used for registration campaigns by bad actors
        suspicious_tlds = {".xyz", ".top", ".club", ".info", ".work", ".click", ".bid"}
        if any(domain.endswith(tld) for tld in suspicious_tlds):
            has_sus_link = True

        # Check suspicious keyword patterns in domain/URL paths
        suspicious_words = {"verify", "update-account", "bank-login", "claim-bonus", "login-service"}
        if any(sw in url.lower() for sw in suspicious_words):
            has_sus_link = True

        # Insecure payment indicator
        if url.startswith("http://") and any(w in url.lower() for w in {"pay", "banking", "login", "checkout"}):
            has_sus_link = True

    # Scam indicator promotion: if scam keywords match OR suspicious links are present, flag scam signal
    if has_sus_link:
        is_scam = True

    return TextFeatures(
        is_urgency_indicated=is_urg,
        is_payment_indicated=is_pay,
        has_otp_pattern=has_otp,
        extracted_urls=tuple(urls),
        extracted_domains=tuple(domains),
        has_suspicious_link=has_sus_link,
        is_business_language=is_biz,
        is_greeting=is_greet,
        is_promotion=is_promo,
        is_scam_signal=is_scam,
        is_event_announcement=is_evt,
        has_forwarded_cues=has_fwd,
        char_count=char_count,
        word_count=word_count,
        line_count=line_count,
    )
