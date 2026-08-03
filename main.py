"""
main.py
-------
CLI launcher and orchestration entrypoint for the WhatsApp Message Notification Router.

Usage:
    python main.py [--dataset-dir PATH] [--output PATH] [--log-level LEVEL]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WhatsApp Message Notification Router CLI"
    )
    parser.add_argument(
        "--dataset-dir",
        default=None,
        help="Override dataset directory path (default: <repo_root>/dataset)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Override output CSV path (default: <repo_root>/dataset/output.csv)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level (default: INFO)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    # Apply environment overrides before importing config-dependent modules
    if args.dataset_dir:
        os.environ["ROUTER_REPO_ROOT"] = str(
            Path(args.dataset_dir).resolve().parent
        )

    # Ensure the root is on path
    _HERE = Path(__file__).resolve().parent
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))

    from src.bootstrap import bootstrap, BootstrapError
    try:
        bootstrap(strict=True, log_level=args.log_level)
    except BootstrapError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 1

    from src.pipeline.run_batch import run
    dataset_dir = os.path.abspath(args.dataset_dir) if args.dataset_dir else None
    output_path = os.path.abspath(args.output) if args.output else None

    return run(dataset_dir=dataset_dir, output_path=output_path)


if __name__ == "__main__":
    sys.exit(main())
