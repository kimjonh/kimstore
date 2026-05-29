#!/usr/bin/env python
"""OpenRouter 排行榜抓取脚本
每周抓取模型调用量排名、厂商市场份额数据，保存为 JSON。
需要先安装：pip install playwright && python -m playwright install chromium
运行：python scripts/scrape_openrouter_rankings.py
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA_DIR = Path("data/openrouter_rankings")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def parse_model_rankings(page):
    """提取模型排行榜"""
    rows = page.query_selector_all('[data-testid="model-rankings-leaderboard-row"]')
    models = []
    for row in rows:
        text = row.text_content().strip()
        # 格式: "1. DeepSeek V4 Flashby deepseek3.53T tokens17%"
        match = re.match(
            r"(\d+)\.\s*(.+?)by\s+(\S+?)([\d.]+)([BT])\s*tokens?\s*(\d+)%", text
        )
        if match:
            rank = int(match.group(1))
            name = match.group(2).strip()
            author = match.group(3).strip()
            amount = float(match.group(4))
            unit = match.group(5)
            change_pct = float(match.group(6))
            tokens = round(amount * (1e12 if unit == "T" else 1e9))
            models.append({
                "rank": rank,
                "name": name,
                "author": author,
                "tokens": tokens,
                "tokens_display": f"{amount}{unit}",
                "weekly_change_pct": change_pct,
            })
    return models


def parse_market_share(page):
    """提取厂商市场份额"""
    body = page.query_selector("body")
    full_text = body.text_content()
    idx = full_text.find("Market Share")
    if idx < 0:
        return []
    section = full_text[idx:idx + 2000]
    # 格式: "1.anthropic3.78T19.0%2.deepseek3.62T18.2%..."
    pattern = r"(\d+)\.(\S+?)([\d.]+)([BT])([\d.]+)%"
    shares = []
    for m in re.finditer(pattern, section):
        rank = int(m.group(1))
        author = m.group(2).strip()
        amount = float(m.group(3))
        unit = m.group(4)
        share_pct = float(m.group(5))
        tokens = amount * (1e12 if unit == "T" else 1e9)
        shares.append({
            "rank": rank,
            "author": author,
            "tokens": tokens,
            "tokens_display": f"{amount}{unit}",
            "market_share_pct": share_pct,
        })
    return shares


def main():
    timestamp = datetime.now(timezone.utc).isoformat()
    week_str = datetime.now().strftime("%Y-W%W")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://openrouter.ai/rankings", wait_until="domcontentloaded", timeout=30000)
        # 等待数据加载完成
        page.wait_for_selector('[data-testid="model-rankings-leaderboard-row"]', timeout=30000)
        page.wait_for_timeout(2000)

        # 展开更多模型
        try:
            show_more = page.query_selector('button:has-text("Show more")')
            if show_more:
                show_more.click()
                page.wait_for_timeout(2000)
        except Exception:
            pass

        models = parse_model_rankings(page)
        market_share = parse_market_share(page)

        browser.close()

    result = {
        "source": "https://openrouter.ai/rankings",
        "fetched_at": timestamp,
        "week": week_str,
        "model_rankings": models,
        "market_share": market_share,
    }

    # 保存当前周数据
    out_path = DATA_DIR / f"rankings_{week_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 追加到汇总时间线
    timeline_path = DATA_DIR / "timeline.json"
    timeline = []
    if timeline_path.exists():
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline = json.load(f)
    timeline.append(result)
    with open(timeline_path, "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print(f"[OK] 抓取完成 — {timestamp}")
    print(f"\n[*] 模型排行榜 (Top 10):")
    for m in models[:10]:
        change = f"+{m['weekly_change_pct']}%" if m['weekly_change_pct'] >= 0 else f"-{m['weekly_change_pct']}%"
        print(f"  {m['rank']:>2}. {m['name']:<35} {m['tokens_display']:>6} tokens  {change}")

    print(f"\n[*] 厂商市场份额:")
    for s in market_share:
        print(f"  {s['rank']:>2}. {s['author']:<20} {s['tokens_display']:>6} tokens  {s['market_share_pct']}%")

    print(f"\n[*] 已保存到: {out_path}")
    print(f"[*] 时间线: {timeline_path} (共 {len(timeline)} 周数据)")


if __name__ == "__main__":
    main()
