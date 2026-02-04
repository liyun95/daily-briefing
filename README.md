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

### Offwork reminder (weekday 18:00 Shanghai time)
```bash
FEISHU_WEBHOOK=... python offwork_reminder.py
```

### Offwork reminder dry run
```bash
DRY_RUN=1 python offwork_reminder.py
```

### Offwork reminder force send (ignores time + weekday)
```bash
FORCE_SEND=1 DRY_RUN=1 python offwork_reminder.py
```

## Environment Variables
- `FEISHU_WEBHOOK` (required): Feishu webhook URL
- `GROQ_API_KEY` (optional): Groq API key for AI-generated copy
- `DRY_RUN=1` (optional): Print JSON payload without sending
- `FORCE_SEND=1` (optional): Ignore time window and weekday checks for offwork reminder

## Cron example (Shanghai time)
```bash
TZ=Asia/Shanghai
0 18 * * 1-5 /usr/bin/python3 /Users/liyun/daily-briefing/offwork_reminder.py
```

## Lint / Format (optional)
Ruff and Black are configured via `pyproject.toml`.

```bash
ruff check .
black .
```

## Notes
- The script fails fast if `FEISHU_WEBHOOK` is missing.
- RSS sources are unreliable; the script skips bad entries quietly.
