#!/usr/bin/env python
"""OpenRouter 排行榜抓取脚本
每周抓取模型调用量排名、厂商市场份额数据，保存为 JSON。
需要先安装：pip install playwright && python -m playwright install chromium
运行：python scripts/scrape_openrouter_rankings.py
"""

import argparse
import json
import os
import re
from datetime import datetime, timezone, timedelta
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
        tokens = round(amount * (1e12 if unit == "T" else 1e9))
        shares.append({
            "rank": rank,
            "author": author,
            "tokens": tokens,
            "tokens_display": f"{amount}{unit}",
            "market_share_pct": share_pct,
        })
    return shares


def generate_csv(timeline, csv_path):
    """生成 CSV 报告：每个模型每周的调用数据和变化"""
    import csv as csv_module

    rows = []
    weeks = sorted({e["week"] for e in timeline})
    seen_models = set()

    for entry in timeline:
        week = entry["week"]
        for m in entry.get("model_rankings", []):
            rows.append({
                "week": week,
                "rank": m["rank"],
                "model": m["name"],
                "author": m["author"],
                "tokens": m["tokens"],
                "tokens_display": m["tokens_display"],
                "weekly_change_pct": m["weekly_change_pct"],
            })
            seen_models.add(m["name"])

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv_module.DictWriter(f, fieldnames=[
            "week", "rank", "model", "author", "tokens", "tokens_display", "weekly_change_pct"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[*] CSV: {csv_path} ({len(rows)} rows, {len(weeks)} weeks, {len(seen_models)} models)")


def format_tokens(n):
    """格式化 token 数为可读字符串"""
    if n >= 1e12:
        return f"{n/1e12:.2f}T"
    elif n >= 1e9:
        return f"{n/1e9:.1f}B"
    elif n >= 1e6:
        return f"{n/1e6:.0f}M"
    else:
        return str(int(n))


def generate_html(current, timeline, html_path):
    """生成可读的 HTML 报告"""
    models = current.get("model_rankings", [])
    shares = current.get("market_share", [])

    # 准备历史趋势数据 (每周的 Top 模型)
    history_labels = []
    history_data = {}
    for entry in timeline:
        week = entry.get("week", "")
        history_labels.append(week)
        for m in entry.get("model_rankings", []):
            name = m["name"]
            if name not in history_data:
                history_data[name] = {}
            history_data[name][week] = m["tokens"]

    # 只保留 top 模型的趋势
    top_names = {m["name"] for m in models[:8]} if models else set()
    trend_names = [n for n in top_names if n in history_data]

    # 生成模型表格行
    model_rows = ""
    for m in models:
        change = m["weekly_change_pct"]
        color = "#22c55e" if change >= 0 else "#ef4444"
        arrow = "&#9650;" if change >= 0 else "&#9660;"
        model_rows += f"""
        <tr>
            <td class="rank">{m["rank"]}</td>
            <td class="name">{m["name"]}<span class="author">by {m["author"]}</span></td>
            <td class="tokens">{m["tokens_display"]}</td>
            <td class="change" style="color:{color}">{arrow} {abs(change)}%</td>
        </tr>"""

    # 生成厂商市场份额行
    share_rows = ""
    max_tokens = max(s["tokens"] for s in shares) if shares else 1
    for s in shares:
        bar_width = (s["tokens"] / max_tokens * 100) if max_tokens > 0 else 0
        share_rows += f"""
        <tr>
            <td class="rank">{s["rank"]}</td>
            <td class="name">{s["author"]}</td>
            <td class="tokens">{s["tokens_display"]}</td>
            <td class="share">
                <div class="bar-bg"><div class="bar-fill" style="width:{bar_width}%"></div></div>
                <span>{s["market_share_pct"]}%</span>
            </td>
        </tr>"""

    # 历史趋势的 JS 数据
    trend_js = ""
    if trend_names and len(history_labels) >= 1:
        datasets = []
        colors = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4", "#a855f7", "#ec4899", "#14b8a6"]
        for i, name in enumerate(trend_names):
            d = history_data[name]
            values = [d.get(w, None) for w in history_labels]
            datasets.append(f"""{{label: '{name}', data: {values}, borderColor: '{colors[i % len(colors)]}', tension: 0.3, spanGaps: false}}""")
        trend_js = f"""
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <script>
    const ctx = document.getElementById('trendChart');
    if (ctx) {{
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(history_labels)},
                datasets: [{', '.join(datasets)}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{ ticks: {{ callback: v => v >= 1e12 ? (v/1e12).toFixed(1) + 'T' : (v/1e9).toFixed(0) + 'B' }} }}
                }},
                plugins: {{ legend: {{ position: 'bottom' }} }}
            }}
        }});
    }}
    </script>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenRouter LLM Rankings - {current.get("week", "")}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
.container {{ max-width: 960px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 4px; }}
.subtitle {{ color: #94a3b8; font-size: 14px; margin-bottom: 32px; }}
.section {{ margin-bottom: 40px; }}
.section h2 {{ font-size: 18px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #1e293b; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; color: #64748b; font-size: 12px; text-transform: uppercase; padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b11; font-size: 14px; }}
tr:hover {{ background: #1e293b44; }}
.rank {{ width: 40px; color: #64748b; font-weight: 600; text-align: center; }}
.name {{ font-weight: 500; }}
.author {{ display: block; font-size: 12px; color: #64748b; font-weight: 400; }}
.tokens {{ font-variant-numeric: tabular-nums; text-align: right; width: 100px; }}
.change {{ text-align: right; width: 80px; font-weight: 500; }}
.share {{ display: flex; align-items: center; gap: 8px; width: 200px; }}
.bar-bg {{ flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; }}
.bar-fill {{ height: 100%; background: #6366f1; border-radius: 3px; }}
.chart-container {{ height: 300px; margin-bottom: 32px; }}
.footer {{ color: #475569; font-size: 12px; margin-top: 40px; padding-top: 16px; border-top: 1px solid #1e293b; }}
.footer a {{ color: #6366f1; }}
</style>
</head>
<body>
<div class="container">
    <h1>LLM Rankings</h1>
    <p class="subtitle">OpenRouter Weekly Usage &mdash; {current.get("week", "")} &middot; Updated {current.get("fetched_at", "")[:10]}</p>

    {f'<div class="chart-container"><canvas id="trendChart"></canvas></div>' if trend_names else ''}

    <div class="section">
        <h2>Model Rankings ({len(models)} models)</h2>
        <table>
            <tr><th></th><th>Model</th><th>Tokens/Week</th><th>Change</th></tr>
            {model_rows}
        </table>
    </div>

    <div class="section">
        <h2>Market Share by Author</h2>
        <table>
            <tr><th></th><th>Author</th><th>Tokens</th><th>Share</th></tr>
            {share_rows}
        </table>
    </div>

    <div class="footer">
        Data from <a href="https://openrouter.ai/rankings">openrouter.ai/rankings</a> &middot;
        Auto-updated weekly via <a href="https://github.com/kimjonh/kimstore">GitHub Actions</a>
    </div>
</div>
{trend_js}
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true",
                        help="仅重新生成 HTML 和 CSV（不抓取），使用已有的 timeline.json 数据")
    args = parser.parse_args()

    # 仅重新生成报告模式
    if args.regenerate:
        timeline_path = DATA_DIR / "timeline.json"
        if not timeline_path.exists():
            print("[!] timeline.json 不存在，无法重新生成")
            return
        with open(timeline_path, "r", encoding="utf-8") as f:
            timeline = json.load(f)
        current = timeline[-1]
        generate_html(current, timeline, DATA_DIR / "rankings.html")
        generate_csv(timeline, DATA_DIR / "rankings.csv")
        print(f"[OK] 报告已重新生成 — week {current['week']}, {len(timeline)} 周数据, {len(timeline[-1].get('model_rankings',[]))} 个模型")
        return

    timestamp = datetime.now(timezone.utc).isoformat()
    # 使用 ISO 周数（%V），与 GitHub Actions 的 date +%Y-W%V 保持一致
    now = datetime.now()
    iso_year, iso_week, _ = now.isocalendar()
    week_str = f"{iso_year}-W{iso_week:02d}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://openrouter.ai/rankings", wait_until="domcontentloaded", timeout=90000)
        # 等待数据加载完成
        page.wait_for_selector('[data-testid="model-rankings-leaderboard-row"]', timeout=90000)
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

    # 生成 HTML
    html_path = DATA_DIR / "rankings.html"
    generate_html(result, timeline, html_path)

    # 生成 CSV
    csv_path = DATA_DIR / "rankings.csv"
    generate_csv(timeline, csv_path)

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
