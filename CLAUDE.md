# Teroxx Portfolio Allocation Model — Web App

## Overview
Interactive web version of the Teroxx Portfolio Allocation Model v3.6 (Excel).
Scores 79 crypto tokens on multi-factor models, generates personalized portfolio allocations based on risk profile.

## Stack
- **Backend:** FastAPI + Jinja2 + HTMX
- **Charts:** Chart.js (donut/bar)
- **Market Data:** CoinGecko free API (5min price cache, 1hr market data cache)
- **Deployment:** Docker on Render (free plan)

## Running Locally
```bash
cd ~/teroxx-portfolio-app
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8888
# Open http://localhost:8888
```

## Project Structure
```
app/
├── main.py          # FastAPI routes + HTMX partial endpoints
├── data.py          # 79 assets, allocations, factor weights (from Excel)
├── engine.py        # Allocation engine, scoring, DCA, rebalancing, P&L
├── market_data.py   # CoinGecko client with TTL cache
├── templates/
│   ├── base.html    # Main shell (header, tabs, all 8 tab panels)
│   └── partials/    # HTMX swap targets (7 result fragments)
└── static/
    ├── css/teroxx.css
    ├── fonts/       # Söhne Buch/Halbfett/Fett + SometimesTimes
    ├── img/logo.svg
    └── js/          # htmx.min.js, chart.min.js, app.js
```

## 8 Tabs
1. **Allocator** — Risk profile + universe + mode → allocation table + donut chart
2. **Your Portfolio** — Portfolio value → position table with BUY actions
3. **Recurring Buys** — DCA planner (scope, horizon, min order)
4. **Factor Scores** — 5-factor model weights + composite scores
5. **Fundamentals** — 10-factor fundamental model
6. **Allocations** — Risk tilts, fixed strategic, per-asset breakdown
7. **Rebalancing** — Current vs target → BUY/SELL actions
8. **P&L Tracker** — Entry price/qty → unrealized P&L with live prices

## Brand
- Nightblue `#010626`, Deep Indigo `#060d43`, Electric Sky `#0b688c`
- Sandstone `#bfb3a8`, Sunset Ember `#d06643`
- Fonts: Söhne (body), SometimesTimes (headings)

## Deployment
```bash
# Deploy to Render (auto-deploy from main branch)
git push origin main
```
