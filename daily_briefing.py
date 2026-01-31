#!/usr/bin/env python3
import os
import random
import requests
import feedparser
from datetime import datetime

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "").strip()
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

def fetch_international_trending(limit=3):
    headers = {"User-Agent": "DidiDailyBriefingBot/1.0 (+https://github.com/)"}
    items = []
    seen_title = set()

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

def didi_opening(dt: datetime) -> str:
    wd = dt.weekday()
    date = dt.strftime("%Y-%m-%d")
    day_cn = WEEKDAY_CN[wd]
    day_name = DAY_NAMES[wd]
    mainline = random.choice(MAINLINE_POOL.get(wd, ["弟弟今天上线播报啦。"]))
    aside = random.choice(ASIDES)
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

    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "弟弟出品｜数据来源：HN / TechCrunch / VentureBeat / Ars Technica"}]
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
