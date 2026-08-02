"""
code/main.py
------------
Entry point for the Message Notification Router submission package.

Usage
-----
    python main.py [--dataset-dir PATH] [--output PATH] [--log-level LEVEL]

This file is the single runnable entry point for the packaged submission.
During development, the implementation lives in src/; this file acts as
the launcher that delegates to src/pipeline/run_batch.py.

Module 12 will complete the pipeline wiring. For now, this stub verifies
that the bootstrap layer is functional.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure the package root is on the Python path when run as a script
# from inside the code/ directory, resolving from the self-contained code/src package.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Message Notification Router — HackerRank Orchestrate"
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

    # Apply environment overrides before importing config-dependent modules.
    if args.dataset_dir:
        os.environ["ROUTER_REPO_ROOT"] = os.path.dirname(
            os.path.abspath(args.dataset_dir)
        )

    from src.bootstrap import bootstrap, BootstrapError

    try:
        bootstrap(strict=True, log_level=args.log_level)
    except BootstrapError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 1

    # Run the full batch pipeline runner
    from src.pipeline.run_batch import run
    
    # Pass dataset_dir and output overrides if provided
    dataset_dir = os.path.abspath(args.dataset_dir) if args.dataset_dir else None
    output_path = os.path.abspath(args.output) if args.output else None

    return run(dataset_dir=dataset_dir, output_path=output_path)


if __name__ == "__main__":
    sys.exit(main())
