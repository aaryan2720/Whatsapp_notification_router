"""
src/multimodal/image_preprocess.py
----------------------------------
Stage 1: Image Preprocessing.

Verifies image file existence and integrity using Pillow.
Extracts basic visual metadata (dimensions, formats) safely.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from PIL import Image, UnidentifiedImageError
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def preprocess_image(image_path: Path | str | None) -> dict[str, Any]:
    """
    Open the image at image_path and extract dimensions and format.

    Degrades gracefully on file missing or corrupt formats.
    """
    metadata: dict[str, Any] = {
        "width": 0,
        "height": 0,
        "format": "UNKNOWN",
        "mode": "UNKNOWN",
        "exists": False,
        "corrupt": False,
    }

    if not image_path:
        return metadata

    path = Path(image_path)
    if not path.is_file():
        logger.warning("Image path resolved but file does not exist: %s", path)
        return metadata

    metadata["exists"] = True

    try:
        with Image.open(path) as img:
            metadata["width"] = img.width
            metadata["height"] = img.height
            metadata["format"] = img.format or "UNKNOWN"
            metadata["mode"] = img.mode or "UNKNOWN"
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        logger.error("Failed to open or parse image format: %s. Error: %s", path, exc)
        metadata["corrupt"] = True

    return metadata
