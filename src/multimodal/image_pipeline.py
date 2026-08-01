"""
src/multimodal/image_pipeline.py
--------------------------------
Orchestrates the entire image processing and OCR extraction pipeline.

Public API:
    process_message_image(
        message: MessageRecord,
        bundle: DatasetBundle
    ) -> tuple[str, TextFeatures | None, ImageFeatures | None]
"""

from __future__ import annotations

from src.loader.csv_loader import DatasetBundle
from src.models import MessageRecord, TextFeatures, ImageFeatures
from src.multimodal.image_preprocess import preprocess_image
from src.multimodal.image_ocr import extract_ocr_text
from src.multimodal.image_classifier import classify_image
from src.multimodal.text_features import extract_text_features
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def process_message_image(
    message: MessageRecord,
    bundle: DatasetBundle,
) -> tuple[str, TextFeatures | None, ImageFeatures | None]:
    """
    Execute the image processing pipeline for an incoming message.

    Returns:
        tuple (ocr_text, text_features, image_features)
    """
    if message.media_type != "image" or not message.media_id:
        return "", None, None

    image_id = message.media_id
    logger.info("Processing message image: %s", image_id)

    # 1. Path resolution (using DatasetBundle O(1) index)
    image_rec = bundle.images_by_id.get(image_id)
    resolved_path = image_rec["resolved_path"] if image_rec else None

    # 2. Image Preprocessing (Metadata verification)
    metadata = preprocess_image(resolved_path)

    # 3. OCR Text Extraction
    ocr_text, _ = extract_ocr_text(image_id, resolved_path)

    # 4. Visual Feature Extraction
    image_features = classify_image(image_id, metadata)

    # 5. Extract text features from OCR text (reusing Module 7 completely)
    text_features = None
    if ocr_text:
        text_features = extract_text_features(ocr_text)

    return ocr_text, text_features, image_features
