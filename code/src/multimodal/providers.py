"""
src/multimodal/providers.py
--------------------------
Defines the unified provider architecture for both OCR and ASR processing.

Exposes:
  - OCRProvider (Base)
    ├── TesseractProvider (Native library wrapper)
    └── DatasetFallbackProvider (Deterministic mock lookup)

  - ASRProvider (Base)
    ├── WhisperProvider (Native library wrapper)
    └── DatasetTranscriptProvider (Deterministic mock lookup)
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# ===========================================================================
# 1. OCR Providers
# ===========================================================================

class OCRProvider(ABC):
    """Abstract base class for OCR text extraction engines."""

    @abstractmethod
    def extract_text(self, image_id: str, resolved_path: Path | None) -> tuple[str, float]:
        """
        Extract text and confidence score from the specified image.

        Returns:
            tuple (text, confidence)
        """
        pass


class TesseractProvider(OCRProvider):
    """Wraps the pytesseract module to execute native Tesseract OCR."""

    def extract_text(self, image_id: str, resolved_path: Path | None) -> tuple[str, float]:
        if not resolved_path or not resolved_path.is_file():
            return "", 0.0
        try:
            import pytesseract
            with Image.open(resolved_path) as img:
                text = pytesseract.image_to_string(img, timeout=10)
                return text, 0.85
        except Exception as exc:
            logger.warning("Tesseract execution failed: %s", exc)
            return "", 0.0


class DatasetFallbackProvider(OCRProvider):
    """Offline ground-truth lookup dictionary for dataset images."""

    def __init__(self, fallback_dict: dict[str, str]) -> None:
        self._fallback_dict = fallback_dict

    def extract_text(self, image_id: str, resolved_path: Path | None) -> tuple[str, float]:
        text = self._fallback_dict.get(image_id, "")
        confidence = 0.90 if text else 0.0
        return text, confidence


# ===========================================================================
# 2. ASR Providers
# ===========================================================================

class ASRProvider(ABC):
    """Abstract base class for Automatic Speech Recognition (voice transcription)."""

    @abstractmethod
    def transcribe(self, audio_id: str, resolved_path: Path | None) -> tuple[str, float]:
        """
        Transcribe voice note audio to text.

        Returns:
            tuple (transcript_text, confidence)
        """
        pass


class WhisperProvider(ASRProvider):
    """Wraps OpenAI Whisper or similar local library to transcribe audio files."""

    def transcribe(self, audio_id: str, resolved_path: Path | None) -> tuple[str, float]:
        if not resolved_path or not resolved_path.is_file():
            return "", 0.0
        try:
            # Placeholder representing a future Whisper integration hook
            # e.g., import whisper; model = whisper.load_model('base'); model.transcribe(...)
            raise NotImplementedError("Whisper system binaries not detected in environment")
        except Exception as exc:
            logger.warning("Whisper transcription failed: %s", exc)
            return "", 0.0


class DatasetTranscriptProvider(ASRProvider):
    """Offline ground-truth lookup dictionary for dataset audio files."""

    def __init__(self, fallback_dict: dict[str, str]) -> None:
        self._fallback = fallback_dict

    def transcribe(self, audio_id: str, resolved_path: Path | None) -> tuple[str, float]:
        text = self._fallback.get(audio_id, "")
        confidence = 0.90 if text else 0.0
        return text, confidence


# ===========================================================================
# 3. Provider Factories (Internal Selection)
# ===========================================================================

def get_ocr_provider(fallback_dict: dict[str, str]) -> OCRProvider:
    """Choose the best available OCR provider dynamically."""
    try:
        import pytesseract  # noqa: F401
        if shutil.which("tesseract") is not None:
            logger.info("Selecting native TesseractProvider")
            return TesseractProvider()
    except ImportError:
        pass
    logger.debug("Selecting DatasetFallbackProvider")
    return DatasetFallbackProvider(fallback_dict)


def get_asr_provider(fallback_dict: dict[str, str]) -> ASRProvider:
    """Choose the best available ASR provider dynamically."""
    # Since Whisper is typically heavy and not installed, always default to fallback
    logger.debug("Selecting DatasetTranscriptProvider")
    return DatasetTranscriptProvider(fallback_dict)
