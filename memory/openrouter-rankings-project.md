---
name: openrouter-rankings-project
description: OpenRouter LLM rankings scraper on GitHub Actions, repo kimjonh/kimstore
metadata:
  type: reference
---

# OpenRouter Rankings 追踪项目

## 仓库
- GitHub: https://github.com/kimjonh/kimstore
- 本地路径: `D:\AI_Investment_Analysis`
- 用户名: kimjonh
- 邮箱: hahapoint945@gmail.com

## 核心文件
- `scripts/scrape_openrouter_rankings.py` — Playwright 抓取脚本，抓 openrouter.ai/rankings 页面
- `.github/workflows/rankings.yml` — 每周一 UTC 00:00（北京 08:00）自动运行，抓取完整的上周数据
- `data/openrouter_rankings/timeline.json` — 历史数据（追加模式，不覆盖）
- `data/openrouter_rankings/rankings.html` — 可视化报告（含 Chart.js 趋势图）

## 数据来源
- `/api/v1/models` — 只有模型元数据，**没有调用量**
- `/rankings` 页面 — 客户端渲染，Playwright 抓取才能拿到真实排名数据
- 抓取字段：模型排名、每周 token 消耗、周变化%、厂商市场份额

## 输出文件
- `data/openrouter_rankings/timeline.json` — 历史数据（追加模式，不覆盖）
- `data/openrouter_rankings/rankings.html` — 可视化报告（含 Chart.js 趋势图）
- `data/openrouter_rankings/rankings.csv` — 结构化数据 (week/rank/model/author/tokens/weekly_change_pct)
- `data/openrouter_rankings/rankings_<周>.json` — 每周原始数据存档

## 脚本关键结构（`scripts/scrape_openrouter_rankings.py`）
- `parse_model_rankings(page)` — 从页面提取模型排名，CSS selector: `[data-testid="model-rankings-leaderboard-row"]`
- `parse_market_share(page)` — 从页面 body 文本提取厂商份额
- `generate_html(current, timeline, html_path)` — 生成 Chart.js 折线图 HTML
- `generate_csv(timeline, csv_path)` — 生成 long-format CSV
- `main()` — 入口，支持 `--regenerate` 参数跳过 scraping
- 周数使用 ISO isocalendar()，与 GitHub Actions 的 date +%V 一致
- 超时设 90s（原 30s 在慢网络下不够）

## 潜在修改点
- 如需增加字段：修改 `parse_model_rankings()` 的 return dict 和 CSV/HTML 生成函数
- 如需改频率：修改 `.github/workflows/rankings.yml` 的 cron 表达式

## 运行方式
- GitHub Actions 自动运行：每周一 UTC 00:00（北京 08:00），抓取完整的上周数据
- 本地手动运行：`python scripts/scrape_openrouter_rankings.py`
- 仅重新生成报告（不抓取）：`python scripts/scrape_openrouter_rankings.py --regenerate`

## 查看方式
- HTML 报告: https://htmlpreview.github.io/?https://github.com/kimjonh/kimstore/blob/master/data/openrouter_rankings/rankings.html
- 原始数据: https://github.com/kimjonh/kimstore/blob/master/data/openrouter_rankings/timeline.json
