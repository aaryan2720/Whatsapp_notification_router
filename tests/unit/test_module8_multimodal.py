"""
tests/unit/test_module8_multimodal.py
-------------------------------------
Unit tests for Module 8: Image Processing & OCR Pipeline.

Covers:
  - Preprocessing (existing vs missing file aspects)
  - Preprocessing corrupt/empty image handling
  - OCR extraction cache hits/misses, disk write
  - Known image fallback text maps
  - Visual classification properties (posters, screenshots, receipts, etc.)
  - aspect ratio heuristics fallbacks for unknown images
  - Full pipeline orchestration (OCR text features extraction reuse)
  - Regression smoke test on real dataset
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

# Ensure repo root on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.loader.csv_loader import DatasetBundle
from src.models import MessageRecord, ImageFeatures, TextFeatures
from src.multimodal.image_preprocess import preprocess_image
from src.multimodal.image_ocr import extract_ocr_text
from src.multimodal.image_classifier import classify_image
from src.multimodal.image_pipeline import process_message_image


# ===========================================================================
# 1. Image Preprocessing Tests
# ===========================================================================

class TestImagePreprocessing:
    def test_preprocess_missing_file(self) -> None:
        meta = preprocess_image(Path("/path/to/ghost.jpg"))
        assert meta["exists"] is False
        assert meta["width"] == 0

    def test_preprocess_corrupt_file(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "bad.jpg"
        corrupt.write_text("not a jpeg picture data")
        meta = preprocess_image(corrupt)
        assert meta["exists"] is True
        assert meta["corrupt"] is True
        assert meta["format"] == "UNKNOWN"

    def test_preprocess_valid_image(self, tmp_path: Path) -> None:
        valid = tmp_path / "valid.jpg"
        # Create a tiny 10x20 valid image using Pillow
        img = Image.new("RGB", (10, 20), color="blue")
        img.save(valid)

        meta = preprocess_image(valid)
        assert meta["exists"] is True
        assert meta["corrupt"] is False
        assert meta["width"] == 10
        assert meta["height"] == 20
        assert meta["format"] == "JPEG"


# ===========================================================================
# 2. Image OCR Extraction Tests
# ===========================================================================

class TestImageOCRExtraction:
    def test_ocr_fallback_known_id(self) -> None:
        # Pytesseract is absent in this test, so it uses fallback Ground Truth dict
        text, conf = extract_ocr_text("img_012", None)
        assert "Internship approval forms" in text
        assert conf == 0.90

    def test_ocr_unknown_id(self) -> None:
        text, conf = extract_ocr_text("img_999", None)
        assert text == ""
        assert conf == 0.0

    def test_ocr_cache_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.configs.paths as _paths
        cache_dir = tmp_path / "ocr_cache"
        monkeypatch.setattr(_paths, "OCR_CACHE_DIR", cache_dir)

        # 1. Miss cache, load fallback, and check cache file is created
        text1, conf1 = extract_ocr_text("img_023", None)
        assert "Fire alarm test" in text1
        cache_file = cache_dir / "img_023.json"
        assert cache_file.is_file()

        # 2. Mutate cache file content to verify next call reads from cache
        cache_data = {"text": "MUTATED CACHE TEXT", "confidence": 0.99}
        cache_file.write_text(json.dumps(cache_data))

        text2, conf2 = extract_ocr_text("img_023", None)
        assert text2 == "MUTATED CACHE TEXT"
        assert conf2 == 0.99


# ===========================================================================
# 3. Image Classification Tests
# ===========================================================================

class TestImageClassification:
    def test_known_id_classification(self) -> None:
        # img_010 is a shopping discount banner (Poster)
        feat_poster = classify_image("img_010", {})
        assert feat_poster.is_poster is True
        assert feat_poster.is_screenshot is False
        assert feat_poster.text_ratio == 0.60
        assert feat_poster.image_complexity == "high"

        # img_002 is a refund screenshot (Screenshot + Receipt)
        feat_screenshot = classify_image("img_002", {})
        assert feat_screenshot.is_screenshot is True
        assert feat_screenshot.is_receipt is True
        assert feat_screenshot.is_poster is False

    def test_unknown_id_heuristics_fallback(self) -> None:
        # Aspect ratio 0.5 (height > width) matches mobile screenshot
        meta_scr = {"width": 1080, "height": 2160, "exists": True, "corrupt": False}
        feat_scr = classify_image("img_unknown_99", meta_scr)
        assert feat_scr.is_screenshot is True
        assert feat_scr.is_poster is False

        # Aspect ratio 1.0 matches poster
        meta_post = {"width": 800, "height": 800, "exists": True, "corrupt": False}
        feat_post = classify_image("img_unknown_99", meta_post)
        assert feat_post.is_poster is True
        assert feat_post.is_screenshot is False


# ===========================================================================
# 4. Pipeline Orchestration Tests
# ===========================================================================

class TestImagePipelineOrchestration:
    def _create_bundle_with_image(self, img_id: str, resolved_path: Path) -> DatasetBundle:
        from src.loader.csv_loader import _build_index
        images = [{"image_id": img_id, "file_path": str(resolved_path), "resolved_path": resolved_path}]
        bundle = DatasetBundle(
            messages=(), users=(), groups=(), group_members=(), business_accounts=(),
            user_business_history=(), message_history=(), message_events=(),
            images=tuple(images), voice_notes=(), daily_notification_summary=(),
            users_by_id={}, groups_by_id={}, business_by_id={}, images_by_id=_build_index(images, "image_id"),
            voice_notes_by_id={}, history_by_message_id={}, group_members_by_user={},
            group_members_by_group={}, group_member_by_user_and_group={}, ubh_by_user_and_business={},
            ubh_by_user={}, events_by_message_id={}, history_by_user={}, daily_summary_by_user={},
            known_user_ids=frozenset(), known_group_ids=frozenset(), known_business_ids=frozenset(),
        )
        return bundle

    def test_pipeline_reuses_module7_text_features(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.configs.paths as _paths
        monkeypatch.setattr(_paths, "OCR_CACHE_DIR", tmp_path / "cache")

        # Create tiny valid img for img_010
        valid = tmp_path / "img_010.jpg"
        Image.new("RGB", (10, 10)).save(valid)
        bundle = self._create_bundle_with_image("img_010", valid)

        msg = MessageRecord(
            message_id="msg_01", user_id="u_001", conversation_type="personal",
            group_id="", business_id="", sender_user_id="", created_at=None,
            message_text="", media_type="image", media_id="img_010", forwarded_count=0
        )

        ocr_text, text_feat, img_feat = process_message_image(msg, bundle)

        # Asserts
        # ocr_text for img_010 should be loaded from fallback
        assert "shopping offer available" in ocr_text
        assert img_feat is not None
        assert img_feat.is_poster is True

        # Module 7 TextFeatures should be computed and returned for the ocr_text
        assert text_feat is not None
        assert isinstance(text_feat, TextFeatures)
        # "Reply STOP to unsubscribe" is in img_010 text, so is_promotion should be True
        assert text_feat.is_promotion is True


# ===========================================================================
# 5. Regression test / Full Dataset smoke
# ===========================================================================

class TestRealImagePipelineSmoke:
    def test_real_image_pipeline_regression(self) -> None:
        from src.loader.csv_loader import load_all_datasets
        bundle = load_all_datasets()

        # Find first image message in messages
        img_msg = None
        for m in bundle.messages:
            if m["media_type"] == "image":
                img_msg = MessageRecord.from_row(m)
                break

        assert img_msg is not None, "Real dataset must have at least one image message"
        ocr_text, text_feat, img_feat = process_message_image(img_msg, bundle)

        assert ocr_text != ""
        assert isinstance(text_feat, TextFeatures)
        assert isinstance(img_feat, ImageFeatures)
        assert img_feat.image_id == img_msg.media_id
