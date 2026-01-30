# Daily Briefing to Feishu

Small Python script that fetches weather + international trending news and posts a Feishu interactive card.

## Features
- Chengdu weather via Open-Meteo
- Trending headlines from HN / Reddit / BBC RSS
- Feishu interactive card payload
- Dry run mode for local debugging

## Requirements
- Python 3.8+
- Dependencies: `requests`, `feedparser`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage
### Send to Feishu
```bash
FEISHU_WEBHOOK=... python daily_briefing.py
```

### Dry run (prints payload)
```bash
DRY_RUN=1 python daily_briefing.py
```

## Environment Variables
- `FEISHU_WEBHOOK` (required): Feishu webhook URL
- `DRY_RUN=1` (optional): Print JSON payload without sending

## Lint / Format (optional)
Ruff and Black are configured via `pyproject.toml`.

```bash
ruff check .
black .
```

## Notes
- The script fails fast if `FEISHU_WEBHOOK` is missing.
- RSS sources are unreliable; the script skips bad entries quietly.
