"""
src/context/business_context.py
-------------------------------
Extracts and computes business-related conversation context fields, including
trust, phishing probabilities, and verification signals.
"""

from __future__ import annotations

from typing import Any
from src.loader.csv_loader import DatasetBundle


def build_business_context_fields(
    user_id: str,
    business_id: str,
    bundle: DatasetBundle,
) -> dict[str, Any]:
    """
    Extract business account information and user-business interaction logs.

    Calculates:
      - business verification status
      - domain authenticity/phishing probability
      - sender trust rating
      - user-business history aggregates
    """
    fields: dict[str, Any] = {
        "business_id": business_id,
        "business_display_name": "Unknown Business",
        "business_brand_name": "Unknown Business",
        "business_category": "unknown",
        "business_verified": False,
        "business_official_domain": "",
        "business_domain_used_by_sender": "",
        "business_account_age_days": 0,
        "business_messages_sent_30d": 0,
        "business_user_reports_30d": 0,
        "business_domain_used_by_sender_age_days": 0,
        "ubh_why_user_knows_account": "",
        "ubh_last_activity_at": None,
        "ubh_allows_promotions": True,
        "ubh_activity_count_180d": 0,
        "ubh_messages_opened_30d": 0,
        "ubh_messages_dismissed_30d": 0,
        "ubh_messages_replied_30d": 0,
        "sender_trust": 0.5,
        "phishing_probability": 0.0,
    }

    if not business_id:
        return fields

    # 1. Resolve raw business metadata
    biz = bundle.business_by_id.get(business_id)
    if biz:
        fields["business_display_name"] = biz["display_name"]
        fields["business_brand_name"] = biz["brand_name"]
        fields["business_category"] = biz["category"]
        fields["business_verified"] = biz["verified"]
        fields["business_official_domain"] = biz["official_domain"]
        fields["business_domain_used_by_sender"] = biz["domain_used_by_sender"]
        fields["business_account_age_days"] = biz["account_age_days"]
        fields["business_messages_sent_30d"] = biz["messages_sent_30d"]
        fields["business_user_reports_30d"] = biz["user_reports_30d"]
        fields["business_domain_used_by_sender_age_days"] = biz["domain_used_by_sender_age_days"]

    # 2. Resolve user's explicit interaction history with this business
    ubh_rec = bundle.ubh_by_user_and_business.get((user_id, business_id))
    if ubh_rec:
        fields["ubh_why_user_knows_account"] = ubh_rec["why_user_knows_account"]
        fields["ubh_last_activity_at"] = ubh_rec["last_activity_at"]
        fields["ubh_allows_promotions"] = ubh_rec["allows_promotions"]
        fields["ubh_activity_count_180d"] = ubh_rec["activity_count_180d"]
        fields["ubh_messages_opened_30d"] = ubh_rec["messages_opened_30d"]
        fields["ubh_messages_dismissed_30d"] = ubh_rec["messages_dismissed_30d"]
        fields["ubh_messages_replied_30d"] = ubh_rec["messages_replied_30d"]

    # 3. Compute trust and phishing probabilities
    if biz:
        # Check domain authenticity
        official = biz["official_domain"].lower() if biz["official_domain"] else ""
        sender_domain = biz["domain_used_by_sender"].lower() if biz["domain_used_by_sender"] else ""

        # Mismatch is a massive phishing indicator
        if official and sender_domain and official != sender_domain:
            fields["phishing_probability"] = 0.95
            fields["sender_trust"] = 0.05
        else:
            # Verified and clean domains have high trust
            reports = biz["user_reports_30d"]
            trust = 0.70 if biz["verified"] else 0.50
            
            # Dampen trust and increase phishing probability with high reports
            if reports > 0:
                trust = max(0.10, trust - (reports * 0.05))
                fields["phishing_probability"] = min(0.90, reports * 0.10)
            
            fields["sender_trust"] = trust
            
        # Account age factor: brand new domain increases suspicious probability
        domain_age = biz["domain_used_by_sender_age_days"]
        if domain_age is not None and 0 < domain_age < 30:
            fields["phishing_probability"] = max(fields["phishing_probability"], 0.80)
            fields["sender_trust"] = min(fields["sender_trust"], 0.20)

    return fields
