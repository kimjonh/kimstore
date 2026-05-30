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
- `.github/workflows/rankings.yml` — 每周一 UTC 07:00（北京 15:00）自动运行
- `data/openrouter_rankings/timeline.json` — 历史数据（追加模式，不覆盖）
- `data/openrouter_rankings/rankings.html` — 可视化报告（含 Chart.js 趋势图）

## 数据来源
- `/api/v1/models` — 只有模型元数据，**没有调用量**
- `/rankings` 页面 — 客户端渲染，Playwright 抓取才能拿到真实排名数据
- 抓取字段：模型排名、每周 token 消耗、周变化%、厂商市场份额

## 查看方式
- HTML 报告: https://htmlpreview.github.io/?https://github.com/kimjonh/kimstore/blob/master/data/openrouter_rankings/rankings.html
- 原始数据: https://github.com/kimjonh/kimstore/blob/master/data/openrouter_rankings/timeline.json
