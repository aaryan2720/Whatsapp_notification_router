"""
src/routing/thresholds.py
-------------------------
Calibration thresholds for intermediate scoring and rule overrides.

Centralizes all numeric tuning values to make adjustments deterministic and easy.
"""

from __future__ import annotations

# Urgency score calibration
URGENCY_HIGH: float = 0.8
URGENCY_MEDIUM: float = 0.5

# Trust calibration
TRUST_HIGH: float = 0.8
TRUST_LOW: float = 0.3

# Scam and Phishing thresholds
SCAM_HIGH: float = 0.7
PHISHING_HIGH: float = 0.6

# Relationship context
RELATIONSHIP_STRONG: float = 0.7
RELATIONSHIP_WEAK: float = 0.3

# Spam & Promo thresholds
SPAM_HIGH: float = 0.7
PROMOTION_HIGH: float = 0.6

# Decision Matrix boundaries
FINAL_PRIORITY_NOTIFY: float = 0.5
FINAL_PRIORITY_DIGEST: float = -0.5
