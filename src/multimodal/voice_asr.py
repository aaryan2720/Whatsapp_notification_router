"""
src/multimodal/voice_asr.py
---------------------------
Stage 2: Voice Note Transcription (ASR).

Transcribes audio using ASRProvider and cache layers.
"""

from __future__ import annotations

from pathlib import Path
from src.configs import paths as _PATHS
from src.multimodal.providers import get_asr_provider
from src.utils.file_io import read_json_cache, write_json_cache
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# Ground truth ASR mapping for dataset audio files (Module 9 fallback)
_MOCK_ASR_TRANSCRIPTS: dict[str, str] = {
    "vn_001": "Hey, just checking in. Hope you're having a good day. No rush, talk to you later.",
    "vn_002": "Please call me immediately, it is an emergency. I need help right now.",
    "vn_003": "Exclusive lottery offer! Win cash prize up to Rs 50,000 today. Sign up at the link now.",
    "vn_004": "Don't forget tomorrow's incident review sync. Please bring deployment notes.",
    "vn_005": "Are you free for lunch? Let's meet at the cafeteria around 1 PM.",
    "vn_006": "School circular details: packed lunch and signed consent forms are required for the field trip tomorrow.",
    "vn_007": "Your order #8874 is out for delivery today. Share OTP only when the courier agent arrives.",
    "vn_008": "Dear customer, your card payment is due tomorrow. Please clear the outstanding balance.",
    "vn_009": "Congratulations! Your phone number won a lottery prize from Amazon. Click the link to claim.",
    "vn_012": " kurse set size M pickup Gate 2 price final at 850",
    "vn_013": "Fire alarm drill tomorrow morning between 9 to 11. Elevators will pause.",
    "vn_014": "Weekly stock market highlights: Nvidia and TSMC seminducter research.",
    "vn_015": "Hi, this is a quick reminder about the internship form submission before portal locks at 5 PM.",
}


def transcribe_audio(
    voice_note_id: str,
    resolved_path: Path | None,
) -> tuple[str, float, bool]:
    """
    Transcribe a voice note audio file to text.

    Checks:
      1. ASR Cache file (disk cache)
      2. ASRProvider (Whisper native or Fallback Lookup)

    Returns:
        tuple (transcript_text, confidence, fallback_used)
    """
    if not voice_note_id:
        return "", 0.0, False

    # 1. Read from disk cache
    cache_path = _PATHS.ASR_CACHE_DIR / f"{voice_note_id}.json"
    cached = read_json_cache(cache_path)
    if cached is not None and "transcript" in cached and "confidence" in cached:
        logger.debug("ASR cache hit for audio %s", voice_note_id)
        fallback_used = cached.get("fallback_used", True)
        return cached["transcript"], float(cached["confidence"]), fallback_used

    # 2. Get provider dynamically
    provider = get_asr_provider(_MOCK_ASR_TRANSCRIPTS)

    # 3. Transcribe
    transcript, confidence = provider.transcribe(voice_note_id, resolved_path)
    fallback_used = provider.__class__.__name__ == "DatasetTranscriptProvider"

    # 4. Save result to disk cache
    cache_data = {
        "transcript": transcript,
        "confidence": confidence,
        "fallback_used": fallback_used,
    }
    try:
        write_json_cache(cache_path, cache_data)
    except Exception as exc:
        logger.warning("Failed to save ASR cache for %s: %s", voice_note_id, exc)

    return transcript, confidence, fallback_used
