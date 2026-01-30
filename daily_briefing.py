#!/usr/bin/env python3
import os
import textwrap
import requests
import feedparser
from datetime import datetime

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "").strip()
if not FEISHU_WEBHOOK:
    raise SystemExit("Missing env FEISHU_WEBHOOK")

# 成都坐标（可改）
CHENGDU_LAT = 30.5728
CHENGDU_LON = 104.0668

RSS_FEEDS = [
    ("OpenAI News", "https://openai.com/news/rss.xml"),
    ("DeepMind Blog", "https://deepmind.com/blog/feed/basic/"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("The Verge - Tech", "https://www.theverge.com/rss/tech/index.xml"),
    ("MIT Tech Review", "https://www.technologyreview.com/topnews.rss"),
    ("WIRED - AI", "https://www.wired.com/feed/category/artificial-intelligence/latest/rss"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
]

def fetch_weather_chengdu():
    # Open-Meteo: daily forecast (today)
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": CHENGDU_LAT,
        "longitude": CHENGDU_LON,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Asia/Shanghai",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()["daily"]
    today = 0
    tmax = data["temperature_2m_max"][today]
    tmin = data["temperature_2m_min"][today]
    pop  = data["precipitation_probability_max"][today]
    code = data["weathercode"][today]
    # 简单 weather code 映射（够用版）
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
    return f"成都天气：{desc}，{tmin:.0f}–{tmax:.0f}°C，降雨概率 {pop}%"

def fetch_top_items(max_items=8):
    items = []
    per_feed_limit = max(1, max_items // 4)  # 让来源更分散
    for name, url in RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:per_feed_limit]:
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                if title and link:
                    items.append((name, title, link))
        except Exception:
            continue
        if len(items) >= max_items:
            break
    return items[:max_items]

def build_card(weather_line, news_items):
    now = datetime.now().strftime("%Y-%m-%d")
    news_md = "\n".join([f"- **{src}**：[{title}]({link})" for src, title, link in news_items]) or "-（暂无）"
    content = textwrap.dedent(f"""
    **Daily Briefing · {now}**

    {weather_line}

    **今日新闻（科技 / AI / 国际）**
    {news_md}
    """).strip()

    # 飞书群机器人：用 interactive card（更好看）
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "📰 Daily Briefing"}},
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}}
            ],
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
    weather = fetch_weather_chengdu()
    news = fetch_top_items(max_items=10)
    payload = build_card(weather, news)
    resp = send_to_feishu(payload)
    print("OK", resp)

if __name__ == "__main__":
    main()
