"""
src/models/context.py
---------------------
Defines domain models related to context and pipeline feature representation:
- UserContext
- ConversationContext
- RoutingFeatures

These models are slots-based, frozen where appropriate, and typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from src.models.message import MessageRecord
from src.utils.types import ConversationType


@dataclass(frozen=True, slots=True)
class UserContext:
    """
    Personalized context for the receiving user.

    Constructed from users.csv, daily summaries, and business histories.
    """

    user_id: str
    do_not_disturb_window: tuple[str, str] | None  # (start_hhmm, end_hhmm)
    messages_opened_30d: int
    messages_replied_30d: int
    notifications_dismissed_30d: int
    messages_reported_30d: int
    daily_avg_notifications_sent: float
    daily_avg_notifications_dismissed: float
    opted_out_businesses: frozenset[str] = field(default_factory=frozenset)
    allows_promo_businesses: frozenset[str] = field(default_factory=frozenset)

    def is_in_dnd(self, dt: datetime) -> bool:
        """
        Check if a given datetime falls within the user's quiet hours (DND window).

        DND windows can cross midnight (e.g. "22:00-07:00").
        """
        if not self.do_not_disturb_window:
            return False

        start_str, end_str = self.do_not_disturb_window
        try:
            sh, sm = map(int, start_str.split(":"))
            eh, em = map(int, end_str.split(":"))
        except (ValueError, AttributeError):
            return False

        current_time = dt.time()
        start_time = time(sh, sm)
        end_time = time(eh, em)

        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:  # Overnight window (e.g. 22:00 to 07:00)
            return current_time >= start_time or current_time <= end_time

    @property
    def reply_to_open_ratio(self) -> float:
        """How likely the user is to reply once they open a message."""
        if self.messages_opened_30d <= 0:
            return 0.0
        return self.messages_replied_30d / self.messages_opened_30d

    @property
    def notification_dismiss_rate(self) -> float:
        """Proportion of notifications dismissed versus opened."""
        total = self.messages_opened_30d + self.notifications_dismissed_30d
        if total <= 0:
            return 0.0
        return self.notifications_dismissed_30d / total

    @property
    def report_tendency(self) -> float:
        """Tendency to report messages (spam/scam)."""
        total = self.messages_opened_30d + self.notifications_dismissed_30d
        if total <= 0:
            return 0.0
        return self.messages_reported_30d / total

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "user_id": self.user_id,
            "do_not_disturb_window": self.do_not_disturb_window,
            "messages_opened_30d": self.messages_opened_30d,
            "messages_replied_30d": self.messages_replied_30d,
            "notifications_dismissed_30d": self.notifications_dismissed_30d,
            "messages_reported_30d": self.messages_reported_30d,
            "daily_avg_notifications_sent": self.daily_avg_notifications_sent,
            "daily_avg_notifications_dismissed": self.daily_avg_notifications_dismissed,
            "opted_out_businesses": list(self.opted_out_businesses),
            "allows_promo_businesses": list(self.allows_promo_businesses),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserContext:
        """Deserialize from dict."""
        dnd = data.get("do_not_disturb_window")
        # Ensure DND is tuple if present in list form
        dnd_tuple = tuple(dnd) if dnd else None
        return cls(
            user_id=data["user_id"],
            do_not_disturb_window=dnd_tuple,  # type: ignore[arg-type]
            messages_opened_30d=data["messages_opened_30d"],
            messages_replied_30d=data["messages_replied_30d"],
            notifications_dismissed_30d=data["notifications_dismissed_30d"],
            messages_reported_30d=data["messages_reported_30d"],
            daily_avg_notifications_sent=data["daily_avg_notifications_sent"],
            daily_avg_notifications_dismissed=data["daily_avg_notifications_dismissed"],
            opted_out_businesses=frozenset(data.get("opted_out_businesses", [])),
            allows_promo_businesses=frozenset(data.get("allows_promo_businesses", [])),
        )


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """
    Context concerning the message sender, group, or business relationship.
    """

    conversation_type: ConversationType

    # Group fields (empty/default if not a group chat)
    group_id: str = ""
    group_name: str = ""
    group_type: str = ""
    group_member_count: int = 0
    group_admin_count: int = 0
    group_muted_by_user: bool = False
    user_role_in_group: str = ""  # "admin", "member", or ""

    # Business fields (empty/default if not a business sender)
    business_id: str = ""
    business_display_name: str = ""
    business_brand_name: str = ""
    business_category: str = ""
    business_verified: bool = False
    business_official_domain: str = ""
    business_domain_used_by_sender: str = ""
    business_account_age_days: int = 0
    business_messages_sent_30d: int = 0
    business_user_reports_30d: int = 0
    business_domain_used_by_sender_age_days: int = 0

    # User-Business history (if user has met business before)
    ubh_why_user_knows_account: str = ""
    ubh_last_activity_at: datetime | None = None
    ubh_allows_promotions: bool = True
    ubh_activity_count_180d: int = 0
    ubh_messages_opened_30d: int = 0
    ubh_messages_dismissed_30d: int = 0
    ubh_messages_replied_30d: int = 0

    # Personal sender details
    sender_user_id: str = ""

    # Precomputed behavioral/trust metrics (populated by context builder)
    sender_trust: float = 0.5
    relationship_strength: float = 0.0
    group_activity_score: float = 0.0
    phishing_probability: float = 0.0
    priority_hint: str = "normal"  # "urgent", "normal", "low"

    @property
    def is_group_admin(self) -> bool:
        return self.user_role_in_group == "admin"

    @property
    def is_verified_business(self) -> bool:
        return self.business_verified

    @property
    def domain_matches(self) -> bool:
        """True if the official domain matches the domain used by the sender."""
        if not self.business_official_domain:
            return False
        return self.business_official_domain.lower() == self.business_domain_used_by_sender.lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_type": self.conversation_type,
            "group_id": self.group_id,
            "group_name": self.group_name,
            "group_type": self.group_type,
            "group_member_count": self.group_member_count,
            "group_admin_count": self.group_admin_count,
            "group_muted_by_user": self.group_muted_by_user,
            "user_role_in_group": self.user_role_in_group,
            "business_id": self.business_id,
            "business_display_name": self.business_display_name,
            "business_brand_name": self.business_brand_name,
            "business_category": self.business_category,
            "business_verified": self.business_verified,
            "business_official_domain": self.business_official_domain,
            "business_domain_used_by_sender": self.business_domain_used_by_sender,
            "business_account_age_days": self.business_account_age_days,
            "business_messages_sent_30d": self.business_messages_sent_30d,
            "business_user_reports_30d": self.business_user_reports_30d,
            "business_domain_used_by_sender_age_days": self.business_domain_used_by_sender_age_days,
            "ubh_why_user_knows_account": self.ubh_why_user_knows_account,
            "ubh_last_activity_at": self.ubh_last_activity_at.isoformat() if self.ubh_last_activity_at else None,
            "ubh_allows_promotions": self.ubh_allows_promotions,
            "ubh_activity_count_180d": self.ubh_activity_count_180d,
            "ubh_messages_opened_30d": self.ubh_messages_opened_30d,
            "ubh_messages_dismissed_30d": self.ubh_messages_dismissed_30d,
            "ubh_messages_replied_30d": self.ubh_messages_replied_30d,
            "sender_user_id": self.sender_user_id,
            "sender_trust": self.sender_trust,
            "relationship_strength": self.relationship_strength,
            "group_activity_score": self.group_activity_score,
            "phishing_probability": self.phishing_probability,
            "priority_hint": self.priority_hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationContext:
        last_act = data.get("ubh_last_activity_at")
        last_act_dt = datetime.fromisoformat(last_act) if last_act else None
        return cls(
            conversation_type=data["conversation_type"],
            group_id=data.get("group_id", ""),
            group_name=data.get("group_name", ""),
            group_type=data.get("group_type", ""),
            group_member_count=data.get("group_member_count", 0),
            group_admin_count=data.get("group_admin_count", 0),
            group_muted_by_user=data.get("group_muted_by_user", False),
            user_role_in_group=data.get("user_role_in_group", ""),
            business_id=data.get("business_id", ""),
            business_display_name=data.get("business_display_name", ""),
            business_brand_name=data.get("business_brand_name", ""),
            business_category=data.get("business_category", ""),
            business_verified=data.get("business_verified", False),
            business_official_domain=data.get("business_official_domain", ""),
            business_domain_used_by_sender=data.get("business_domain_used_by_sender", ""),
            business_account_age_days=data.get("business_account_age_days", 0),
            business_messages_sent_30d=data.get("business_messages_sent_30d", 0),
            business_user_reports_30d=data.get("business_user_reports_30d", 0),
            business_domain_used_by_sender_age_days=data.get("business_domain_used_by_sender_age_days", 0),
            ubh_why_user_knows_account=data.get("ubh_why_user_knows_account", ""),
            ubh_last_activity_at=last_act_dt,
            ubh_allows_promotions=data.get("ubh_allows_promotions", True),
            ubh_activity_count_180d=data.get("ubh_activity_count_180d", 0),
            ubh_messages_opened_30d=data.get("ubh_messages_opened_30d", 0),
            ubh_messages_dismissed_30d=data.get("ubh_messages_dismissed_30d", 0),
            ubh_messages_replied_30d=data.get("ubh_messages_replied_30d", 0),
            sender_user_id=data.get("sender_user_id", ""),
            sender_trust=data.get("sender_trust", 0.5),
            relationship_strength=data.get("relationship_strength", 0.0),
            group_activity_score=data.get("group_activity_score", 0.0),
            phishing_probability=data.get("phishing_probability", 0.0),
            priority_hint=data.get("priority_hint", "normal"),
        )


@dataclass(frozen=True, slots=True)
class TextFeatures:
    """
    Extracted textual features from message text or OCR/transcript sources.
    Used by the routing decision engine for heuristics and risk profiling.
    """

    is_urgency_indicated: bool = False
    is_payment_indicated: bool = False
    has_otp_pattern: bool = False
    extracted_urls: tuple[str, ...] = field(default_factory=tuple)
    extracted_domains: tuple[str, ...] = field(default_factory=tuple)
    has_suspicious_link: bool = False
    is_business_language: bool = False
    is_greeting: bool = False
    is_promotion: bool = False
    is_scam_signal: bool = False
    is_event_announcement: bool = False
    has_forwarded_cues: bool = False
    char_count: int = 0
    word_count: int = 0
    line_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_urgency_indicated": self.is_urgency_indicated,
            "is_payment_indicated": self.is_payment_indicated,
            "has_otp_pattern": self.has_otp_pattern,
            "extracted_urls": list(self.extracted_urls),
            "extracted_domains": list(self.extracted_domains),
            "has_suspicious_link": self.has_suspicious_link,
            "is_business_language": self.is_business_language,
            "is_greeting": self.is_greeting,
            "is_promotion": self.is_promotion,
            "is_scam_signal": self.is_scam_signal,
            "is_event_announcement": self.is_event_announcement,
            "has_forwarded_cues": self.has_forwarded_cues,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "line_count": self.line_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextFeatures:
        return cls(
            is_urgency_indicated=data.get("is_urgency_indicated", False),
            is_payment_indicated=data.get("is_payment_indicated", False),
            has_otp_pattern=data.get("has_otp_pattern", False),
            extracted_urls=tuple(data.get("extracted_urls", [])),
            extracted_domains=tuple(data.get("extracted_domains", [])),
            has_suspicious_link=data.get("has_suspicious_link", False),
            is_business_language=data.get("is_business_language", False),
            is_greeting=data.get("is_greeting", False),
            is_promotion=data.get("is_promotion", False),
            is_scam_signal=data.get("is_scam_signal", False),
            is_event_announcement=data.get("is_event_announcement", False),
            has_forwarded_cues=data.get("has_forwarded_cues", False),
            char_count=data.get("char_count", 0),
            word_count=data.get("word_count", 0),
            line_count=data.get("line_count", 0),
        )


@dataclass(frozen=True, slots=True)
class RoutingFeatures:
    """
    Complete bundle of computed features passed into the Routing Decision Engine.

    Contains raw structures along with pre-calculated scores and stats.
    """

    message: MessageRecord
    user: UserContext
    conversation: ConversationContext
    ocr_text: str = ""
    asr_transcript: str = ""
    resolved_media_path: str | None = None
    has_valid_media: bool = False
    matched_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    is_dnd_active: bool = False
    historical_open_rate: float = 0.0
    historical_reply_rate: float = 0.0
    historical_dismiss_rate: float = 0.0
    historical_report_rate: float = 0.0
    text_features: TextFeatures | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message.to_dict(),
            "user": self.user.to_dict(),
            "conversation": self.conversation.to_dict(),
            "ocr_text": self.ocr_text,
            "asr_transcript": self.asr_transcript,
            "resolved_media_path": self.resolved_media_path,
            "has_valid_media": self.has_valid_media,
            "matched_evidence_ids": list(self.matched_evidence_ids),
            "is_dnd_active": self.is_dnd_active,
            "historical_open_rate": self.historical_open_rate,
            "historical_reply_rate": self.historical_reply_rate,
            "historical_dismiss_rate": self.historical_dismiss_rate,
            "historical_report_rate": self.historical_report_rate,
            "text_features": self.text_features.to_dict() if self.text_features else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutingFeatures:
        tf_data = data.get("text_features")
        tf = TextFeatures.from_dict(tf_data) if tf_data else None
        return cls(
            message=MessageRecord.from_row(data["message"]),
            user=UserContext.from_dict(data["user"]),
            conversation=ConversationContext.from_dict(data["conversation"]),
            ocr_text=data.get("ocr_text", ""),
            asr_transcript=data.get("asr_transcript", ""),
            resolved_media_path=data.get("resolved_media_path"),
            has_valid_media=data.get("has_valid_media", False),
            matched_evidence_ids=tuple(data.get("matched_evidence_ids", [])),
            is_dnd_active=data.get("is_dnd_active", False),
            historical_open_rate=data.get("historical_open_rate", 0.0),
            historical_reply_rate=data.get("historical_reply_rate", 0.0),
            historical_dismiss_rate=data.get("historical_dismiss_rate", 0.0),
            historical_report_rate=data.get("historical_report_rate", 0.0),
            text_features=tf,
        )
