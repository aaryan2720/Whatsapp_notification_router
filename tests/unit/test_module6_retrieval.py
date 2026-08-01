"""
tests/unit/test_module6_retrieval.py
------------------------------------
Unit tests for Module 6: Two-Stage Evidence Retrieval Pipeline.

Covers:
  - Stage 1: Candidate Generation (same sender, group, business, cross-channel)
  - Deduplication and current message exclusion
  - Stage 2: Lexical matching, recency decay, reaction weight influence
  - Determinism of ranking
  - Top-K selection and relevance threshold filtering
  - No-history cases
  - End-to-end smoke test on the real dataset
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.loader.csv_loader import DatasetBundle
from src.models import MessageRecord, EvidenceRecord, EvidenceBundle
from src.retrieval.index import generate_candidates
from src.retrieval.ranker import rank_candidates
from src.retrieval.evidence_selector import select_evidence


# ===========================================================================
# 1. Mock Helper
# ===========================================================================

def _create_mock_bundle(
    history: list[dict] | None = None,
    events: list[dict] | None = None,
) -> DatasetBundle:
    """Create a minimal DatasetBundle specifically for retrieval testing."""
    from src.loader.csv_loader import _build_index, _build_multi_index

    h_list = history or []
    e_list = events or []

    return DatasetBundle(
        messages=(),
        users=(),
        groups=(),
        group_members=(),
        business_accounts=(),
        user_business_history=(),
        message_history=tuple(h_list),
        message_events=tuple(e_list),
        images=(),
        voice_notes=(),
        daily_notification_summary=(),
        users_by_id={},
        groups_by_id={},
        business_by_id={},
        images_by_id={},
        voice_notes_by_id={},
        history_by_message_id=_build_index(h_list, "message_id"),
        group_members_by_user={},
        group_members_by_group={},
        group_member_by_user_and_group={},
        ubh_by_user_and_business={},
        ubh_by_user={},
        events_by_message_id=_build_index(e_list, "message_id"),
        history_by_user=_build_multi_index(h_list, "user_id"),
        daily_summary_by_user={},
        known_user_ids=frozenset(),
        known_group_ids=frozenset(),
        known_business_ids=frozenset(),
    )


# ===========================================================================
# 2. Test Cases
# ===========================================================================

class TestTwoStageRetrieval:
    def test_candidate_generation_filters(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="group",
            group_id="g_work",
            business_id="",
            sender_user_id="u_boss",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="Need status report",
            media_type="",
            media_id="",
            forwarded_count=0,
        )

        history = [
            # Matches group
            {"message_id": "h_01", "user_id": "u_001", "conversation_type": "group", "group_id": "g_work", "sender_user_id": "u_colleague"},
            # Matches sender but in another chat
            {"message_id": "h_02", "user_id": "u_001", "conversation_type": "personal", "group_id": "", "sender_user_id": "u_boss"},
            # Other user (should be ignored)
            {"message_id": "h_03", "user_id": "u_other", "conversation_type": "group", "group_id": "g_work", "sender_user_id": "u_boss"},
            # Unrelated channel same user
            {"message_id": "h_04", "user_id": "u_001", "conversation_type": "personal", "group_id": "", "sender_user_id": "u_stranger"},
        ]
        bundle = _create_mock_bundle(history=history)

        candidates = generate_candidates(incoming, bundle)

        # Should retrieve only u_001's related history (h_01 and h_02)
        c_ids = {c["message_id"] for c in candidates}
        assert c_ids == {"h_01", "h_02"}

        # Check tagged match reasons
        c_map = {c["message_id"]: c for c in candidates}
        assert c_map["h_01"]["candidate_generation_reason"] == "same_group"
        assert c_map["h_02"]["candidate_generation_reason"] == "same_sender_in_other_chat"

    def test_candidate_generation_excludes_current_message(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        # History contains a row with identical message_id (should be filtered out)
        history = [
            {"message_id": "msg_now", "user_id": "u_001", "conversation_type": "personal", "sender_user_id": "u_friend"},
            {"message_id": "h_01", "user_id": "u_001", "conversation_type": "personal", "sender_user_id": "u_friend"},
        ]
        bundle = _create_mock_bundle(history=history)
        candidates = generate_candidates(incoming, bundle)
        assert len(candidates) == 1
        assert candidates[0]["message_id"] == "h_01"

    def test_lexical_similarity_ranking(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="Need help with plumbing issue in Tower B room",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        candidates = [
            # High overlap: Tower, plumbing, room
            {"message_id": "cand_high", "message_text": "Plumbing problem reported in room at Tower B", "candidate_generation_reason": "same_sender", "created_at": datetime(2026, 7, 30, 12, 0)},
            # No overlap
            {"message_id": "cand_low", "message_text": "Verify email address link", "candidate_generation_reason": "same_sender", "created_at": datetime(2026, 7, 30, 12, 0)},
        ]
        bundle = _create_mock_bundle()

        ranked = rank_candidates(incoming, candidates, bundle)

        # High overlap must rank higher
        assert ranked[0][0]["message_id"] == "cand_high"
        assert ranked[0][1] > ranked[1][1]  # Score assertion

    def test_recency_decay_ranking(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        candidates = [
            # Sent 40 days ago
            {"message_id": "cand_old", "message_text": "hello", "candidate_generation_reason": "same_sender", "created_at": datetime(2026, 7, 30, 12, 0) - timedelta(days=40)},
            # Sent 1 hour ago
            {"message_id": "cand_recent", "message_text": "hello", "candidate_generation_reason": "same_sender", "created_at": datetime(2026, 7, 30, 11, 0)},
        ]
        bundle = _create_mock_bundle()

        ranked = rank_candidates(incoming, candidates, bundle)

        # Recent candidate must rank higher due to decay
        assert ranked[0][0]["message_id"] == "cand_recent"
        assert ranked[0][1] > ranked[1][1]

    def test_event_weight_influence(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hi",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        candidates = [
            # User reported this sender's message (massive threat indicator)
            {"message_id": "cand_reported", "message_text": "hi", "candidate_generation_reason": "same_sender", "created_at": datetime(2026, 7, 30, 12, 0)},
            # User ignored/dismissed this message
            {"message_id": "cand_ignored", "message_text": "hi", "candidate_generation_reason": "same_sender", "created_at": datetime(2026, 7, 30, 12, 0)},
        ]
        events = [
            {"message_id": "cand_reported", "user_id": "u_001", "message_reported": True, "message_opened": False, "message_replied": False, "notification_dismissed": False, "muted_after_message": False},
            {"message_id": "cand_ignored", "user_id": "u_001", "message_reported": False, "message_opened": False, "message_replied": False, "notification_dismissed": True, "muted_after_message": False},
        ]
        bundle = _create_mock_bundle(events=events)

        ranked = rank_candidates(incoming, candidates, bundle)

        # Reported message should rank higher
        assert ranked[0][0]["message_id"] == "cand_reported"

    def test_selector_top_k_and_filtering(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="plumbing",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        # Create a set of 5 history records
        history = [
            {"message_id": f"h_{i}", "user_id": "u_001", "sender_user_id": "u_friend", "conversation_type": "personal", "message_text": f"plumbing {i}", "created_at": datetime(2026, 7, 30, 12, 0)}
            for i in range(5)
        ]
        bundle = _create_mock_bundle(history=history)

        # Ask for Top-2
        bundle_out = select_evidence(incoming, bundle, top_k=2)

        assert isinstance(bundle_out, EvidenceBundle)
        assert len(bundle_out.ranked_evidence) == 2
        assert len(bundle_out.evidence_ids) == 2

    def test_no_history_cases(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="hello",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        bundle = _create_mock_bundle()
        bundle_out = select_evidence(incoming, bundle)

        assert len(bundle_out.ranked_evidence) == 0
        assert bundle_out.evidence_ids == ()
        assert bundle_out.retrieval_confidence == 0.0

    def test_determinism(self) -> None:
        incoming = MessageRecord(
            message_id="msg_now",
            user_id="u_001",
            conversation_type="personal",
            group_id="",
            business_id="",
            sender_user_id="u_friend",
            created_at=datetime(2026, 7, 30, 12, 0),
            message_text="plumbing",
            media_type="",
            media_id="",
            forwarded_count=0,
        )
        history = [
            {"message_id": "h_1", "user_id": "u_001", "sender_user_id": "u_friend", "conversation_type": "personal", "message_text": "plumbing", "created_at": datetime(2026, 7, 30, 12, 0)},
            {"message_id": "h_2", "user_id": "u_001", "sender_user_id": "u_friend", "conversation_type": "personal", "message_text": "hello", "created_at": datetime(2026, 7, 30, 12, 0)},
        ]
        bundle = _create_mock_bundle(history=history)

        b1 = select_evidence(incoming, bundle)
        b2 = select_evidence(incoming, bundle)

        assert b1 == b2


# ===========================================================================
# 3. Regression test / Full Dataset load check
# ===========================================================================

class TestRealRetrievalSmoke:
    def test_real_messages_evidence_retrieval(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()
        
        # Pull real messages
        real_msgs = bundle.messages
        assert len(real_msgs) > 0
        
        # Retrieve evidence for the first 10 messages
        for m_row in real_msgs[:10]:
            msg = MessageRecord.from_row(m_row)
            ev_bundle = select_evidence(msg, bundle)
            assert isinstance(ev_bundle, EvidenceBundle)
            assert isinstance(ev_bundle.evidence_ids, tuple)
            for ev in ev_bundle.ranked_evidence:
                assert isinstance(ev, EvidenceRecord)
                assert ev.relevance_score >= 0.0
