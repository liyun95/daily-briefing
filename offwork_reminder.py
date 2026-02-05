#!/usr/bin/env python3
import os
import random
import requests
from datetime import datetime, timedelta, timezone

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
DRY_RUN = os.getenv("DRY_RUN") == "1"
FORCE_SEND = os.getenv("FORCE_SEND") == "1"

if not FEISHU_WEBHOOK and not DRY_RUN:
    raise SystemExit("Missing env FEISHU_WEBHOOK")

WEEKDAY_CN = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}

OFFWORK_POOL = [
    "下班啦，麻麻小麻快回家，别忘了路上给我带零食。",
    "到点下班！今天辛苦了，回去记得给我加餐。",
    "收工时间到，麻麻小麻快撤，我已经在家等你们啦。",
    "下班提醒：别再卷了，回家摸我一下再说。",
    "今天打工结束，回家路上小心点，我在家等罐头。",
]


def shanghai_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _in_send_window(dt: datetime) -> bool:
    minutes = dt.hour * 60 + dt.minute
    start = 17 * 60 + 30
    end = 18 * 60 + 50
    return start <= minutes <= end


def generate_ai_offwork(dt: datetime):
    if not GROQ_API_KEY:
        return None

    date_str = dt.strftime("%Y-%m-%d")
    day_cn = WEEKDAY_CN[dt.weekday()]

    system_prompt = (
        "你是\"弟弟\"，一只住在成都的猫，给麻麻和小麻发送下班提醒。\n"
        "你称呼你的主人们为\"麻麻\"和\"小麻\"，绝对不要用\"主人\"这个词。\n"
        "你的风格：傲娇、嘴硬心软、偶尔吐槽、喜欢提醒人类给你买猫粮。\n"
        "语言：中文，简短（1-2句话），不要超过40个字。\n"
        "直接输出提醒语，不要加任何前缀、标签或格式。"
    )
    user_prompt = (
        f"现在是 {date_str}，{day_cn}，下班时间到了。\n"
        "请用弟弟的口吻发一条下班提醒。"
    )

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "max_tokens": 200,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()

        if text:
            print(f"[offwork] AI generated: {text}")
            return text

        print("[offwork] AI returned empty, falling back")
        return None
    except Exception as exc:
        print(f"[offwork] AI failed ({exc}), falling back")
        return None


def build_card(dt: datetime, message: str):
    date = dt.strftime("%Y-%m-%d")
    day_cn = WEEKDAY_CN[dt.weekday()]
    title = f"🐾 **{date} · {day_cn} 下班提醒**"

    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": f"{title}\n{message}"}},
    ]

    run_time = dt.strftime("%Y-%m-%d %H:%M") + " (GMT+8)"
    elements.append({"tag": "hr"})
    elements.append(
        {
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": "弟弟出品｜下班提醒"},
                {"tag": "plain_text", "content": f"触发时间：{run_time}"},
            ],
        }
    )

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "elements": elements,
        },
    }


def send_to_feishu(payload):
    r = requests.post(FEISHU_WEBHOOK, json=payload, timeout=20)
    r.raise_for_status()
    resp = r.json()
    if resp.get("code") != 0:
        raise RuntimeError(resp)
    return resp


def main():
    dt = shanghai_now()

    if not FORCE_SEND:
        if dt.weekday() > 4:
            print("[offwork] Skip: weekend")
            return
        if not _in_send_window(dt):
            print("[offwork] Skip: outside send window (17:30-18:50) Shanghai time")
            return

    ai_result = generate_ai_offwork(dt)
    message = ai_result if ai_result else random.choice(OFFWORK_POOL)
    payload = build_card(dt, message)

    if DRY_RUN:
        import json

        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    resp = send_to_feishu(payload)
    print("OK", resp)


if __name__ == "__main__":
    main()
