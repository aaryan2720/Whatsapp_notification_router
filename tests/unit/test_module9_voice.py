"""
tests/unit/test_module9_voice.py
--------------------------------
Unit tests for Module 9: Voice Note Processing & ASR Pipeline.

Covers:
  - Audio preprocessing (valid, missing, and loader duration mappings)
  - ASRProvider abstractions (WhisperProvider, DatasetTranscriptProvider)
  - Transcribe cache hits/misses, disk cache roundtrip
  - Speech detection vs silence handling
  - Pipeline integration (reusing Module 7 Text Feature Extraction on speech)
  - End-to-end regression check with real dataset voice files
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.loader.csv_loader import DatasetBundle
from src.models import MessageRecord, VoiceFeatures, TextFeatures
from src.multimodal.voice_preprocess import preprocess_audio
from src.multimodal.voice_asr import transcribe_audio
from src.multimodal.voice_pipeline import process_message_voice


# ===========================================================================
# 1. Mock Helper
# ===========================================================================

def _create_bundle_with_voice(vn_id: str, resolved_path: Path, duration: float) -> DatasetBundle:
    from src.loader.csv_loader import _build_index
    voice_notes = [
        {
            "voice_note_id": vn_id,
            "file_path": str(resolved_path),
            "duration_seconds": duration,
            "resolved_path": resolved_path,
        }
    ]
    return DatasetBundle(
        messages=(), users=(), groups=(), group_members=(), business_accounts=(),
        user_business_history=(), message_history=(), message_events=(),
        images=(), voice_notes=tuple(voice_notes), daily_notification_summary=(),
        users_by_id={}, groups_by_id={}, business_by_id={}, images_by_id={},
        voice_notes_by_id=_build_index(voice_notes, "voice_note_id"),
        history_by_message_id={}, group_members_by_user={}, group_members_by_group={},
        group_member_by_user_and_group={}, ubh_by_user_and_business={}, ubh_by_user={},
        events_by_message_id={}, history_by_user={}, daily_summary_by_user={},
        known_user_ids=frozenset(), known_group_ids=frozenset(), known_business_ids=frozenset(),
    )


# ===========================================================================
# 2. Audio Preprocessing Tests
# ===========================================================================

class TestAudioPreprocessing:
    def test_preprocess_missing_file(self) -> None:
        # File does not exist
        bundle = _create_bundle_with_voice("vn_001", Path("ghost.mp3"), 15.5)
        meta = preprocess_audio("vn_001", Path("ghost.mp3"), bundle)
        assert meta["exists"] is False
        assert meta["corrupt"] is True
        assert meta["duration"] == 15.5

    def test_preprocess_valid_file(self, tmp_path: Path) -> None:
        valid_audio = tmp_path / "valid.mp3"
        valid_audio.write_text("audio byte payload")  # dummy file
        bundle = _create_bundle_with_voice("vn_001", valid_audio, 12.0)

        meta = preprocess_audio("vn_001", valid_audio, bundle)
        assert meta["exists"] is True
        assert meta["corrupt"] is False
        assert meta["duration"] == 12.0


# ===========================================================================
# 3. ASR Provider & Cache Tests
# ===========================================================================

class TestASRTranscription:
    def test_asr_fallback_known_id(self) -> None:
        # Native Whisper is unavailable in CLI, falling back to fallback dict
        text, conf, fallback = transcribe_audio("vn_002", None)
        assert "Please call me immediately" in text
        assert conf == 0.90
        assert fallback is True

    def test_asr_unknown_id(self) -> None:
        text, conf, fallback = transcribe_audio("vn_999", None)
        assert text == ""
        assert conf == 0.0

    def test_asr_cache_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.configs.paths as _paths
        cache_dir = tmp_path / "asr_cache"
        monkeypatch.setattr(_paths, "ASR_CACHE_DIR", cache_dir)

        # 1. Miss cache, loads fallback, and saves cache file
        text1, conf1, _ = transcribe_audio("vn_004", None)
        assert "incident review" in text1
        cache_file = cache_dir / "vn_004.json"
        assert cache_file.is_file()

        # 2. Mutate cache file to check next run uses cache
        cache_data = {"transcript": "MUTATED SPEECH TRANSCRIPT", "confidence": 0.98, "fallback_used": False}
        cache_file.write_text(json.dumps(cache_data))

        text2, conf2, fallback = transcribe_audio("vn_004", None)
        assert text2 == "MUTATED SPEECH TRANSCRIPT"
        assert conf2 == 0.98
        assert fallback is False


# ===========================================================================
# 4. Pipeline & Speech Detection Tests
# ===========================================================================

class TestVoicePipelineOrchestration:
    def test_pipeline_speech_detection_and_text_features(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.configs.paths as _paths
        monkeypatch.setattr(_paths, "ASR_CACHE_DIR", tmp_path / "cache")

        audio = tmp_path / "vn_002.mp3"
        audio.write_text("dummy")
        bundle = _create_bundle_with_voice("vn_002", audio, 8.4)

        msg = MessageRecord(
            message_id="msg_voice", user_id="u_001", conversation_type="personal",
            group_id="", business_id="", sender_user_id="", created_at=None,
            message_text="", media_type="voice", media_id="vn_002", forwarded_count=0
        )

        transcript, text_feat, voice_feat = process_message_voice(msg, bundle)

        # ASR returns "Please call me immediately, it is an emergency..."
        assert "emergency" in transcript
        assert voice_feat is not None
        assert voice_feat.audio_duration == 8.4
        assert voice_feat.speech_detected is True
        assert voice_feat.silence_detected is False

        # TextFeatures should reuse Module 7 and extract is_urgency_indicated=True
        assert text_feat is not None
        assert isinstance(text_feat, TextFeatures)
        assert text_feat.is_urgency_indicated is True

    def test_pipeline_silence_handling(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.configs.paths as _paths
        monkeypatch.setattr(_paths, "ASR_CACHE_DIR", tmp_path / "cache")

        audio = tmp_path / "vn_silent.mp3"
        audio.write_text("dummy")
        # Empty/unknown voice note ID means no text transcript extracted
        bundle = _create_bundle_with_voice("vn_silent", audio, 5.0)

        msg = MessageRecord(
            message_id="msg_voice", user_id="u_001", conversation_type="personal",
            group_id="", business_id="", sender_user_id="", created_at=None,
            message_text="", media_type="voice", media_id="vn_silent", forwarded_count=0
        )

        transcript, text_feat, voice_feat = process_message_voice(msg, bundle)
        assert transcript == ""
        assert voice_feat is not None
        assert voice_feat.speech_detected is False
        assert voice_feat.silence_detected is True
        assert text_feat is None


# ===========================================================================
# 5. Regression test / Full Dataset smoke
# ===========================================================================

class TestRealVoicePipelineSmoke:
    def test_real_voice_pipeline_regression(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()

        # Find first voice message in messages
        voice_msg = None
        for m in bundle.messages:
            if m["media_type"] == "voice":
                voice_msg = MessageRecord.from_row(m)
                break

        assert voice_msg is not None, "Real dataset must have at least one voice message"
        transcript, text_feat, voice_feat = process_message_voice(voice_msg, bundle)

        # Transcripts are populated from mock ground-truth ASR map
        assert transcript != ""
        assert isinstance(text_feat, TextFeatures)
        assert isinstance(voice_feat, VoiceFeatures)
        assert voice_feat.voice_note_id == voice_msg.media_id
        assert voice_feat.audio_duration > 0.0
