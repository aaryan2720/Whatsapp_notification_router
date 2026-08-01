# Message Notification Router

AI-powered WhatsApp message notification router — HackerRank Orchestrate submission.

## What This Does

For every incoming WhatsApp message in `dataset/messages.csv`, this system decides:

- `notify` — interrupt the user now
- `digest` — show later
- `mute` — suppress as low-value, repetitive, unwanted, suspicious, or unsafe

Predictions are written to `dataset/output.csv` with full reasoning, confidence scores, and historical evidence IDs.

## Requirements

- Python 3.11 or later
- Dependencies listed in `requirements.txt`

## Setup

```bash
pip install -r requirements.txt
```

If OCR or ASR are needed, install the optional extras listed (commented out) in `requirements.txt` and ensure the respective system binaries are available.

## Running

From the repository root:

```bash
python code/main.py
```

Options:

```
--dataset-dir PATH    Override dataset directory
--output PATH         Override output CSV path
--log-level LEVEL     DEBUG | INFO | WARNING | ERROR (default: INFO)
```

## Output

Predictions are written to `dataset/output.csv` with the following columns (in order):

```
message_id, action, message_type, reason, confidence, evidence_message_ids
```

## Testing

```bash
pytest tests/ -v
```

## Repository Layout

```
code/           # This submission package (self-contained entry point)
dataset/        # Read-only inputs (never modified)
docs/           # Canonical architecture and design documentation
src/            # Implementation modules
tests/          # Unit tests
```

## Environment Variables

| Variable            | Default                   | Purpose                        |
|---------------------|---------------------------|--------------------------------|
| `ROUTER_ENV`        | `development`             | Runtime environment            |
| `ROUTER_LOG_LEVEL`  | `INFO`                    | Logging verbosity              |
| `ROUTER_REPO_ROOT`  | Auto-inferred             | Override repository root path  |
| `ROUTER_CACHE_DIR`  | `src/cache`               | Cache directory                |
| `ROUTER_LOG_DIR`    | `src/logs`                | Log directory                  |
| `ROUTER_OUTPUT_DIR` | `src/outputs`             | Scratch output directory       |

Never hardcode API keys or secrets. Use environment variables or a `.env` file.
