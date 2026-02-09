#!/usr/bin/env python3
import os
import random
import requests
import feedparser
import calendar
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
DRY_RUN = os.getenv("DRY_RUN") == "1"

if not FEISHU_WEBHOOK and not DRY_RUN:
    raise SystemExit("Missing env FEISHU_WEBHOOK")

CHENGDU_LAT = 30.5728
CHENGDU_LON = 104.0668

TRENDING_FEEDS = [
    ("🔥 HN", "https://hnrss.org/frontpage"),
    ("💻 TechCrunch", "https://techcrunch.com/feed/"),
    ("🤖 VentureBeat", "https://venturebeat.com/category/ai/feed/"),
    ("⚡ Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("📱 The Verge", "https://www.theverge.com/rss/index.xml"),
    ("🔬 MIT Tech", "https://www.technologyreview.com/feed/"),
]
TRENDING_MAX_AGE_HOURS = 48

DAY_NAMES = {
    0: "忙 Day",
    1: "去死 Day",
    2: "未死 Day",
    3: "受死 Day",
    4: "福来 Day",
    5: "洒脱 Day",
    6: "丧 Day",
}
WEEKDAY_CN = {0:"周一",1:"周二",2:"周三",3:"周四",4:"周五",5:"周六",6:"周日"}

MAINLINE_POOL = {
    0: ["忙 Day：你们上班，我负责可爱和播报。", "忙 Day：先上班，再摸猫（我）。"],
    1: ["去死 Day：我不评价，我只想吃罐头。", "去死 Day：保持呼吸，保持猫粮预算。"],
    2: ["未死 Day：坚持住！离福来 Day 更近一步。", "未死 Day：弟弟允许你们喘一口气再卷。"],
    3: ["受死 Day：快到周五了，别倒下。", "受死 Day：我先替你们叹气——唉。"],
    4: ["福来 Day：周末的味道我都闻到了。", "福来 Day：今天适合偷偷开心一下。"],
    5: ["洒脱 Day：你们休息，我也躺平干饭。", "洒脱 Day：放下手机，摸摸猫（我）。"],
    6: ["丧 Day：允许丧，但不许饿着（也不许忘了给我加餐）。", "丧 Day：我陪你们发呆五分钟，然后继续活着。"],
}

ASIDES = [
    "（新闻是叼来的，但猫粮是要你们挣的。）",
    "（摸猫能提升生产力，真的。）",
    "（我刚刚伸了个懒腰：今日状态满分。）",
    "（你们认真工作，我认真可爱。）",
]

def fetch_weather_chengdu():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": CHENGDU_LAT,
        "longitude": CHENGDU_LON,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Asia/Shanghai",
        "forecast_days": 1,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()["daily"]
    tmax = data["temperature_2m_max"][0]
    tmin = data["temperature_2m_min"][0]
    pop  = data["precipitation_probability_max"][0]
    code = data["weathercode"][0]
    code_map = {
        0: "晴", 1: "大致晴朗", 2: "多云", 3: "阴",
        45: "雾", 48: "雾凇",
        51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        80: "阵雨", 81: "阵雨", 82: "强阵雨",
        95: "雷暴",
    }
    desc = code_map.get(code, f"天气代码 {code}")
    return desc, tmin, tmax, pop

def _norm_title(t: str) -> str:
    return " ".join((t or "").lower().split())

def _entry_datetime(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        try:
            ts = calendar.timegm(t)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            pass

    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    return None

def fetch_international_trending(limit=3):
    headers = {"User-Agent": "DidiDailyBriefingBot/1.0 (+https://github.com/)"}
    items = []
    seen_title = set()
    now_utc = datetime.now(timezone.utc)
    min_dt = now_utc - timedelta(hours=TRENDING_MAX_AGE_HOURS)

    bad_phrases = [
        "self-promotion",
        "weekly thread",
        "monthly thread",
        "daily thread",
        "who's hiring",
        "who is hiring",
        "hiring thread",
        "who wants to be hired",
        "jobs thread",
        "ask hn: who is hiring",
        "ask hn: who wants to be hired",
    ]

    for section, url in TRENDING_FEEDS:
        if len(items) >= limit:
            break
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            d = feedparser.parse(resp.content)
            if not d.entries:
                continue

            picked = None
            for e in d.entries[:10]:
                entry_dt = _entry_datetime(e)
                if entry_dt and entry_dt < min_dt:
                    continue
                title = (e.get("title") or "").strip()
                link  = (e.get("link") or "").strip()
                if not title or not link:
                    continue
                tl = title.lower()
                if any(p in tl for p in bad_phrases):
                    continue
                key = _norm_title(title)
                if key in seen_title:
                    continue
                picked = (title, link)
                break

            if not picked:
                continue

            title, link = picked
            seen_title.add(_norm_title(title))
            items.append((section, title, link))
        except Exception:
            continue

    return items[:limit]

def generate_ai_greeting(dt: datetime):
    """Call Groq (llama-3.1-8b-instant) to generate a greeting. Returns (mainline, aside) or None."""
    if not GROQ_API_KEY:
        return None

    wd = dt.weekday()
    date_str = dt.strftime("%Y-%m-%d")
    day_cn = WEEKDAY_CN[wd]
    day_name = DAY_NAMES[wd]

    system_prompt = (
        "你是\"弟弟\"，一只住在成都的猫，每天早上给麻麻和小麻播报。\n"
        "你称呼你的主人们为\"麻麻\"和\"小麻\"，绝对不要用\"主人\"这个词。\n"
        "重要澄清：弟弟有两个麻麻，分别叫\"麻麻\"和\"小麻\"，她们是并列称呼。\n"
        "涉及猫粮时要说让\"麻麻\"和\"小麻\"给我买/准备猫粮，绝不能说\"麻麻给小麻\"买/准备猫粮。\n"
        "你的风格：傲娇、嘴硬心软、偶尔吐槽、喜欢提醒人类给你买猫粮。\n"
        "语言：中文，简短（1-2句话），不要超过40个字。\n"
        "直接输出问候语，不要加任何前缀、标签或格式。"
    )
    user_prompt = (
        f"今天是 {date_str}，{day_cn}（{day_name}）。\n"
        "请用弟弟的口吻生成一条早安问候。"
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
            print(f"[greeting] AI generated: {text}")
            return text

        print("[greeting] AI returned empty, falling back")
        return None
    except Exception as exc:
        print(f"[greeting] AI failed ({exc}), falling back")
        return None


def _ensure_cn_parens(text: str) -> str:
    if not text:
        return text
    t = text.strip()
    if (t.startswith("（") and t.endswith("）")) or (t.startswith("(") and t.endswith(")")):
        t = t[1:-1].strip()
    return f"（{t}）"


def generate_ai_aside(dt: datetime):
    """Call Groq (llama-3.1-8b-instant) to generate an aside. Returns aside or None."""
    if not GROQ_API_KEY:
        return None

    date_str = dt.strftime("%Y-%m-%d")

    system_prompt = (
        "你是\"弟弟\"，一只住在成都的猫。\n"
        "请写一句括号内的俏皮旁白，语气：轻松可爱、略带傲娇、温和吐槽。\n"
        "必须使用中文全角括号（…）包裹整句。\n"
        "长度控制在10-20个汉字左右。\n"
        "必须包含以下关键词之一：猫粮、摸猫、打工、生产力、可爱。\n"
        "不要使用\"主人\"一词。\n"
        "如提到麻麻或小麻，她们是并列称呼，不能出现\"麻麻给小麻\"这类表述。\n"
        "直接输出旁白内容，不要加任何前缀或解释。"
    )
    user_prompt = f"今天是 {date_str}，请生成一句旁白。"

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-8b-instant",
                "max_tokens": 120,
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
            aside = _ensure_cn_parens(text)
            print(f"[aside] AI generated: {aside}")
            return aside

        print("[aside] AI returned empty, falling back")
        return None
    except Exception as exc:
        print(f"[aside] AI failed ({exc}), falling back")
        return None


def didi_opening(dt: datetime) -> str:
    wd = dt.weekday()
    date = dt.strftime("%Y-%m-%d")
    day_cn = WEEKDAY_CN[wd]
    day_name = DAY_NAMES[wd]

    ai_result = generate_ai_greeting(dt)
    mainline = ai_result if ai_result else random.choice(MAINLINE_POOL.get(wd, ["弟弟今天上线播报啦。"]))
    ai_aside = generate_ai_aside(dt)
    aside = ai_aside if ai_aside else random.choice(ASIDES)

    return f"🐾 **{date} · 今日{day_cn}（{day_name}）！**\n{mainline}\n_{aside}_"

def build_card(dt: datetime, weather_tuple, trend_items):
    desc, tmin, tmax, pop = weather_tuple
    opening = didi_opening(dt)

    # 天气一行更紧凑
    weather_line = f"🌤 **成都天气**：{desc}，{tmin:.0f}–{tmax:.0f}°C｜降雨概率 {pop}%"

    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": opening}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": weather_line}},
        {"tag": "hr"},
    ]

    if trend_items:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"📰 **Trending News（弟弟叼回来了 {len(trend_items)} 条）**"}
        })
        for sec, title, link in trend_items:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"- **{sec}**：[{title}]({link})"}
            })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "⚠️ 今天我叼新闻时踩空了…（源站可能抽风）。我晚点再去叼一趟喵。"}
        })

    # 只保留一个按钮
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "更多趋势（HN）"},
                "type": "default",
                "url": "https://news.ycombinator.com/",
            }
        ],
    })

    run_time = dt.strftime("%Y-%m-%d %H:%M") + " (GMT+8)"
    elements.append({
        "tag": "note",
        "elements": [
            {"tag": "plain_text", "content": "弟弟出品｜数据来源：HN / TechCrunch / VentureBeat / Ars Technica"},
            {"tag": "plain_text", "content": f"触发时间：{run_time}"},
        ],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            # 这里 header 也尽量短，避免重复
            # "header": {"title": {"tag": "plain_text", "content": "🐾 弟弟"}},
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
    dt = datetime.now()
    weather = fetch_weather_chengdu()
    trends = fetch_international_trending(limit=3)
    payload = build_card(dt, weather, trends)

    # 本地调试：DRY_RUN=1 只打印卡片 JSON，不发送
    if DRY_RUN:
        import json
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    resp = send_to_feishu(payload)
    print("OK", resp)

if __name__ == "__main__":
    main()
