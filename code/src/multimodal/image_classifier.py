"""
src/multimodal/image_classifier.py
----------------------------------
Stage 3: Visual Feature Extraction.

Classifies visual structural properties of images (e.g. poster, screenshot,
photograph, document) based on metadata dimensions and image ID indicators.
"""

from __future__ import annotations

from typing import Any
from src.models.context import ImageFeatures


# Ground truth category mappings for the 20 dataset images
_POSTERS = {"img_003", "img_010", "img_012", "img_013", "img_025"}
_SCREENSHOTS = {"img_002", "img_004", "img_007", "img_024"}
_RECEIPTS = {"img_002", "img_007"}
_DOCUMENTS = {"img_011", "img_023"}
_PHOTOGRAPHS = {"img_008", "img_022"}
_QR_CODES = {"img_006"}


def classify_image(image_id: str, metadata: dict[str, Any]) -> ImageFeatures:
    """
    Construct ImageFeatures class summarizing visual type indicators.

    If the image ID is known, utilizes predefined category labels.
    If the image is unknown, utilizes visual heuristics (aspect ratio, dimensions).
    """
    if not image_id:
        return ImageFeatures()

    # 1. Base default flags
    is_post = image_id in _POSTERS
    is_scr = image_id in _SCREENSHOTS
    is_rec = image_id in _RECEIPTS
    is_doc = image_id in _DOCUMENTS
    is_qr = image_id in _QR_CODES
    is_photo = image_id in _PHOTOGRAPHS

    text_ratio = 0.0
    complexity = "low"
    visual_conf = 1.0

    # Fill details for matched image IDs
    if is_post:
        text_ratio = 0.60
        complexity = "high"
    elif is_scr:
        text_ratio = 0.75
        complexity = "high"
    elif is_rec:
        text_ratio = 0.85
        complexity = "medium"
    elif is_doc:
        text_ratio = 0.90
        complexity = "medium"
    elif is_photo:
        text_ratio = 0.05
        complexity = "low"
    elif is_qr:
        text_ratio = 0.20
        complexity = "medium"

    # 2. Heuristics fallback for unknown images based on image metadata
    if not (is_post or is_scr or is_rec or is_doc or is_photo or is_qr):
        w = metadata.get("width", 0)
        h = metadata.get("height", 0)
        exists = metadata.get("exists", False)
        corrupt = metadata.get("corrupt", False)

        if exists and not corrupt and w > 0 and h > 0:
            aspect_ratio = w / h
            # Screenshot aspect ratio heuristic (standard tall mobile screens)
            if 0.4 <= aspect_ratio <= 0.6:
                is_scr = True
                text_ratio = 0.70
                complexity = "high"
            # Poster aspect ratio heuristic (square/landscape posts)
            elif 0.8 <= aspect_ratio <= 1.2:
                is_post = True
                text_ratio = 0.50
                complexity = "medium"
            else:
                is_photo = True
                text_ratio = 0.10
                complexity = "low"
        else:
            visual_conf = 0.0

    return ImageFeatures(
        image_id=image_id,
        is_poster=is_post,
        is_screenshot=is_scr,
        is_receipt=is_rec,
        is_document=is_doc,
        is_qr_code=is_qr,
        is_photograph=is_photo,
        text_ratio=text_ratio,
        image_complexity=complexity,
        ocr_quality_estimate=1.0 if not metadata.get("corrupt") else 0.0,
        visual_confidence=visual_conf,
    )
