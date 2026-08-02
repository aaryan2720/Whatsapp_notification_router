"""
src/multimodal/image_ocr.py
---------------------------
Stage 2: OCR Text Extraction.

Extracts text from images using an OCRProvider abstraction.
Caches results to disk for fast subsequent execution.
"""

from __future__ import annotations

from pathlib import Path
from src.configs import paths as _PATHS
from src.multimodal.providers import get_ocr_provider
from src.utils.file_io import read_json_cache, write_json_cache
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# Ground truth OCR mapping for dataset images (Module 8 fallback)
_MOCK_OCR_TEXT: dict[str, str] = {
    "img_001": "Dear Customer, your bank statement is available for download. Tap below to view details.",
    "img_002": "Refund approved for your ticket. Verify wallet and card details before midnight.",
    "img_003": "Ladakh trip itinerary: 7 nights, all in, from Rs 17,999 per person. Reply STOP to unsubscribe.",
    "img_004": "Sync meeting at 7 PM. Bring yesterday's incident summary and open rollback questions.",
    "img_005": "Package delivery status: Out for delivery today. Tap below to view details.",
    "img_006": "Weekly dinner menu card. Scan code to order tonight.",
    "img_007": "Dear Customer, Shopee return pickup today 2-5 PM. Share pickup code only after courier arrives.",
    "img_008": "Product details: kurta set size M, and blue denim jacket.",
    "img_010": "Reminder: shopping offer available. Tap below for extra discounts. Reply STOP to unsubscribe.",
    "img_011": "School circular: Field trip timing, sign consent form, pack lunch, ID card in pocket.",
    "img_012": "Internship approval forms deadline: Portal closes at 5 PM today. Late entries not accepted.",
    "img_013": "Alumni meetup poster. Register for this weekend's reunion.",
    "img_014": "Feedback survey link. Please take a few minutes to complete.",
    "img_016": "Team Banking Services: Card payment updates available.",
    "img_020": "Marketing offer: Special deals inside. Reply STOP to unsubscribe.",
    "img_022": "Medical prescription photo. Pick up these medicines today.",
    "img_023": "Fire alarm test schedule: tomorrow 9 AM to 11 AM. Elevators paused.",
    "img_024": "Weekly market note: Nvidia and TSMC research commentary.",
    "img_025": "Real estate deals: Plots near airport road. Pay Rs 11,000 token today.",
    "img_026": "Verify details: Tap below to view transaction history.",
}


def extract_ocr_text(image_id: str, resolved_path: Path | None) -> tuple[str, float]:
    """
    Extract text and OCR confidence from an image using the OCR provider abstraction.

    Reads from disk cache first to ensure fast execution.
    """
    if not image_id:
        return "", 0.0

    # 1. Read from disk cache
    cache_path = _PATHS.OCR_CACHE_DIR / f"{image_id}.json"
    cached = read_json_cache(cache_path)
    if cached is not None and "text" in cached and "confidence" in cached:
        logger.debug("OCR cache hit for image %s", image_id)
        return cached["text"], float(cached["confidence"])

    # 2. Get provider dynamically (internal selection)
    provider = get_ocr_provider(_MOCK_OCR_TEXT)

    # 3. Extract text
    extracted_text, confidence = provider.extract_text(image_id, resolved_path)

    # 4. Save result to disk cache
    cache_data = {
        "text": extracted_text,
        "confidence": confidence,
    }
    try:
        write_json_cache(cache_path, cache_data)
    except Exception as exc:
        logger.warning("Failed to save OCR cache for %s: %s", image_id, exc)

    return extracted_text, confidence
