"""
src/pipeline/run_batch.py
-------------------------
Batch Execution Pipeline (Module 12).

Orchestrates path resolution, dataset loading, iterative processing of each
message through the context builders, retrievers, multimodal processors,
routing scorer, explanation builder, and writes the output file.
Runs the SubmissionValidator at the end to ensure submission readiness.
"""

from __future__ import annotations

import csv
from pathlib import Path
from src.configs import paths as _PATHS
from src.loader.csv_loader import load_all_datasets
from src.models import MessageRecord, RoutingFeatures
from src.context.user_context import build_user_context
from src.context.conversation_context import build_conversation_context
from src.retrieval.evidence_selector import select_evidence
from src.multimodal.text_features import extract_text_features
from src.multimodal.image_pipeline import process_message_image
from src.multimodal.voice_pipeline import process_message_voice
from src.routing.scorer import route_message
from src.output.reason_builder import build_final_prediction
from src.output.submission_validator import validate_submission
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def run(
    dataset_dir: Path | str | None = None,
    output_path: Path | str | None = None,
) -> int:
    """
    Execute the entire Message Notification Router pipeline end-to-end.

    Returns:
        0 on success, non-zero on failure.
    """
    logger.info("Starting Message Routing pipeline batch run.")

    # 1. Path resolution
    if dataset_dir:
        dataset_path = Path(dataset_dir).resolve()
        logger.info("Overriding dataset directory: %s", dataset_path)
    else:
        dataset_path = _PATHS.DATASET_DIR

    if output_path:
        out_csv = Path(output_path).resolve()
        logger.info("Overriding output CSV path: %s", out_csv)
    else:
        out_csv = _PATHS.OUTPUT_CSV

    messages_csv = dataset_path / "messages.csv"

    # 2. Dataset Loading
    try:
        # load_all_datasets accepts the custom dataset directory path
        bundle = load_all_datasets(dataset_path)
    except Exception as exc:
        logger.error("Failed to load datasets from %s: %s", dataset_path, exc)
        return 1

    # 3. Message Iteration
    predictions = []
    for idx, raw_msg in enumerate(bundle.messages):
        msg = MessageRecord.from_row(raw_msg)
        logger.debug("Processing message %d/%d (ID: %s)", idx + 1, len(bundle.messages), msg.message_id)

        try:
            # Context construction
            user_ctx = build_user_context(msg.user_id, bundle)
            conv_ctx = build_conversation_context(msg, bundle)

            # Evidence retrieval
            evidence_bundle = select_evidence(msg, bundle)
            evidence_ids = evidence_bundle.evidence_ids

            # Text features
            tf = extract_text_features(msg.message_text)

            # Multimodal media resolution
            ocr_text = ""
            asr_transcript = ""
            resolved_media_path: Path | None = None
            img_feat = None
            voice_feat = None

            if msg.media_type == "image":
                image_rec = bundle.images_by_id.get(msg.media_id)
                resolved_media_path = image_rec["resolved_path"] if image_rec else None
                ocr_text, _, img_feat = process_message_image(msg, bundle)
            elif msg.media_type == "voice":
                vn_rec = bundle.voice_notes_by_id.get(msg.media_id)
                resolved_media_path = vn_rec["resolved_path"] if vn_rec else None
                asr_transcript, _, voice_feat = process_message_voice(msg, bundle)

            # Build RoutingFeatures context
            has_media = bool(resolved_media_path)
            is_dnd = user_ctx.is_in_dnd(msg.created_at) if msg.created_at else False

            # Historical rates calculations
            historical_dismiss_rate = user_ctx.notification_dismiss_rate
            historical_open_rate = 1.0 - historical_dismiss_rate
            historical_reply_rate = user_ctx.reply_to_open_ratio
            historical_report_rate = user_ctx.report_tendency

            rf = RoutingFeatures(
                message=msg,
                user=user_ctx,
                conversation=conv_ctx,
                ocr_text=ocr_text,
                asr_transcript=asr_transcript,
                resolved_media_path=str(resolved_media_path) if resolved_media_path else None,
                has_valid_media=has_media,
                matched_evidence_ids=evidence_ids,
                is_dnd_active=is_dnd,
                historical_open_rate=historical_open_rate,
                historical_reply_rate=historical_reply_rate,
                historical_dismiss_rate=historical_dismiss_rate,
                historical_report_rate=historical_report_rate,
                text_features=tf,
                image_features=img_feat,
                voice_features=voice_feat,
            )

            # Decision Fusion (Module 10)
            preliminary_pred = route_message(rf)

            # Reason & Confidence Presentation Formatting (Module 11)
            final_pred = build_final_prediction(preliminary_pred)
            predictions.append(final_pred)

        except Exception as exc:
            logger.error("Error processing message %s: %s", msg.message_id, exc, exc_info=True)
            return 1

    # 4. CSV Writing
    logger.info("Writing %d predictions to %s", len(predictions), out_csv)
    # Ensure parent directory exists
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    try:
        with out_csv.open("w", newline="", encoding="utf-8") as fh:
            fieldnames = ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for pred in predictions:
                writer.writerow(pred.to_csv_row())
    except Exception as exc:
        logger.error("Failed to write output CSV: %s", exc)
        return 1

    # 5. Submission Validation
    try:
        validate_submission(out_csv, messages_csv)
    except Exception as exc:
        logger.error("Submission validation failed: %s", exc)
        return 1

    logger.info("Message Routing pipeline batch run completed successfully. output.csv is ready.")
    return 0
