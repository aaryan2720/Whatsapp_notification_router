# Repository Structure

## Final Repository Layout

The working pattern agreed during planning is:

- Develop in `src/` as the source of truth.
- Package the final runnable submission inside `code/`.
- Leave `dataset/` untouched.

### Recommended Top-Level Layout

```text
hackerrank-orchestrate-august26-main/
├── AGENTS.md
├── CLAUDE.md
├── problem_statement.md
├── README.md
├── dataset/
├── docs/
├── src/
└── code/
```

## Purpose of Every Folder

### `dataset/`
Provided participant-facing input data. This directory must remain untouched.

### `docs/`
Canonical design documentation generated from the planning work.

### `src/`
Development source of truth. All implementation work should happen here first.

### `code/`
Submission package. This must become self-contained and runnable for `code.zip`.

## Final Directory Structure Inside `code`

```text
code/
├── main.py
├── README.md
├── requirements.txt
├── evaluation/
│   └── main.py
├── src/
│   ├── __init__.py
│   ├── loader/
│   ├── context/
│   ├── retrieval/
│   ├── multimodal/
│   ├── routing/
│   ├── output/
│   ├── configs/
│   ├── prompts/
│   └── utils/
├── cache/
├── logs/
├── outputs/
└── scripts/
```

## Purpose of the Main Subfolders in `code`

- `src/`: all runtime modules.
- `evaluation/`: local validation helpers and smoke checks.
- `cache/`: stored OCR, ASR, and retrieval artifacts.
- `logs/`: optional runtime diagnostics.
- `outputs/`: scratch outputs and local debug files.
- `scripts/`: helper commands for packaging, validation, and runs.

## Packaging Strategy

- Keep implementation inside `src/` during development.
- When the system is stable, copy or sync the final implementation into `code/src/`.
- Ensure `code/main.py` is the single entry point.
- Ensure `code/README.md` explains how to run the final package from the terminal.
- Ensure `code/requirements.txt` contains every runtime dependency.
- Ensure the final zip does not depend on the outer workspace to run.

## Development Workflow

1. Build and test in `src/`.
2. Keep all logic modular and independent.
3. Validate modules incrementally.
4. Sync stable code into `code/`.
5. Run final packaging verification from the `code/` folder.
6. Produce `output.csv` from the packaged entrypoint.

## How `src` Transitions into `code`

- `src` is the canonical implementation location during development.
- `code` is the submission artifact.
- No hidden runtime dependency should remain only in `src`.
- The final packaging step should mirror the tested modules from `src` into `code/src`.
- `code/main.py` should invoke the packaged modules, not the development workspace.

## Notes

- Keep logs optional and non-essential to correctness.
- Keep datasets read-only.
- Keep the submission package deterministic and self-contained.
