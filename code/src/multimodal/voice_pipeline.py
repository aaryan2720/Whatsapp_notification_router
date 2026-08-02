"""
src/multimodal/voice_pipeline.py
--------------------------------
Orchestrates the entire voice processing and ASR transcription pipeline.

Public API:
    process_message_voice(
        message: MessageRecord,
        bundle: DatasetBundle
    ) -> tuple[str, TextFeatures | None, VoiceFeatures | None]
"""

from __future__ import annotations

from src.loader.csv_loader import DatasetBundle
from src.models import MessageRecord, TextFeatures, VoiceFeatures
from src.multimodal.voice_preprocess import preprocess_audio
from src.multimodal.voice_asr import transcribe_audio
from src.multimodal.text_features import extract_text_features
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def process_message_voice(
    message: MessageRecord,
    bundle: DatasetBundle,
) -> tuple[str, TextFeatures | None, VoiceFeatures | None]:
    """
    Execute the voice processing pipeline for an incoming message.

    Returns:
        tuple (transcript_text, text_features, voice_features)
    """
    if message.media_type != "voice" or not message.media_id:
        return "", None, None

    voice_note_id = message.media_id
    logger.info("Processing message voice note: %s", voice_note_id)

    # 1. Path resolution (using DatasetBundle O(1) index)
    vn_rec = bundle.voice_notes_by_id.get(voice_note_id)
    resolved_path = vn_rec["resolved_path"] if vn_rec else None

    # 2. Audio Preprocessing (Metadata resolution)
    metadata = preprocess_audio(voice_note_id, resolved_path, bundle)

    # 3. Audio Transcription (ASR Provider check)
    transcript, confidence, fallback_used = transcribe_audio(voice_note_id, resolved_path)

    # 4. Construct VoiceFeatures
    speech_detected = bool(transcript.strip())
    voice_features = VoiceFeatures(
        voice_note_id=voice_note_id,
        transcript=transcript,
        transcript_confidence=confidence,
        audio_duration=metadata["duration"],
        speech_detected=speech_detected,
        silence_detected=not speech_detected,
        processing_fallback_used=fallback_used,
        language="en" if speech_detected else "",
    )

    # 5. Extract text features from transcript (reusing Module 7 completely)
    text_features = None
    if transcript:
        text_features = extract_text_features(transcript)

    return transcript, text_features, voice_features
