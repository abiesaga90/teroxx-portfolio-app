# Teroxx Portfolio Allocation Model — Web App

## Overview
Interactive web version of the Teroxx Portfolio Allocation Model v4.1 (Excel).
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

## Proposal Export
Proposal card (Allocator results) exports the branded proposal as
**DOCX**, **PDF**, and **Google Docs**.
- **`proposal_docx.py:render_docx` is the SINGLE SOURCE OF TRUTH.** The
  PDF and Google Docs outputs are *conversions* of the DOCX, so the three
  can never drift apart. Do NOT add a separate PDF/HTML renderer or
  template — that divergence is exactly what this design removed.
  - `.docx` — `render_docx(ctx)`, the canonical artifact.
  - `.pdf` — DOCX converted via headless LibreOffice (`app/pdf/docx_to_pdf.py`).
  - `.gdoc` — DOCX uploaded to Google Drive as a native Google Doc
    (`app/google_docs.py`). Hidden until `GOOGLE_SERVICE_ACCOUNT_JSON` set.
- Endpoints: `/api/clients/{id}/proposal.{docx,pdf,gdoc}` and
  `/api/prospect/proposal.{docx,pdf,gdoc}`.
- The Docker image installs `libreoffice-writer` + the brand fonts for
  the PDF conversion. Google Docs setup: `docs/google_docs_setup.md`.

### v5.2 (2026-06-12) — advisor bug-fix pass (Jannick feedback)
- **Proposal: market regime removed.** The standalone macro/regime page,
  the regime gauge chart, the exec-summary "regime context" bullet, the
  regime-triggered review wording and the macro data-source line are all
  gone from the DOCX/PDF (`_macro_section` no longer called; `regime_gauge_svg`
  dropped from the EMF pre-pass). `build_proposal_context` still computes the
  macro state (it may inform the strategy narrative); only the rendering is
  removed. The regime lives on in the app's Market Context tab.
- **DOCX 502 on Render free tier.** Headless LibreOffice (EMF charts) under
  ~512 MB could OOM-kill the worker → proxy 502 on `/proposal.docx`. Set
  `TEROXX_VECTOR_CHARTS=0` in `render.yaml` so DOCX generation uses the fast
  in-process hi-DPI PNG path; the `.pdf` endpoint still spawns LibreOffice
  once for the DOCX→PDF convert. EMF batch timeout lowered 90s→30s. (Residual
  cold-start 502s are a free-tier characteristic — consider a keep-warm ping.)
- **Market Context coverage guard.** When data blocks fail to load (e.g. the
  Yahoo TradFi feed is IP-blocked), the composite no longer asserts a
  confident "Early Bull" off a skewed subset — `score_all` now flags
  `low_coverage`/`missing_categories` and the tab shows a "Low confidence"
  badge + warning instead.
- **DCA planner + Rebalancing tab auto-load.** Both forms lacked a `load`
  trigger, so the tabs looked empty until an input changed. DCA now triggers
  on `load`; Rebalancing computes on first tab-open (`switchTab` hook),
  seeding saved holdings so BUY/SELL shows immediately.
- **P&L no longer jumps.** Editing a P&L cell preserved neither scroll nor
  caret across the HTMX swap; `triggerRebalancePnl`/`restoreRpnlFocus` now
  restore both.
- **Scoring "Visual Analysis" side-by-side again.** Reverted the stacked
  (full-width) bubble + dilution layout to the original `.chart-box` pair.

### v5.0 (2026-06-11)
- **Vector charts:** charts embed as **EMF** (Word-native vector) via
  `app/pdf/svg_to_emf.py` (same LibreOffice as the PDF step; one soffice
  spawn for all charts). `_chart_bytes`/`_place_chart` in `proposal_docx.py`
  resolve EMF then fall back to a high-DPI (2400px) PNG. Toggle with env
  `TEROXX_VECTOR_CHARTS` (default on; set `0` to force PNG). `render_docx`
  now spawns LibreOffice, so endpoints call it via `run_in_threadpool`.
- **App↔proposal alignment:** the proposal is a faithful record of what the
  advisor saw. A server-side `AllocationSnapshot` (token in the download URL,
  `&snapshot=`) freezes the on-screen allocation; `build_proposal_context`
  renders it verbatim and logs `proposal_snapshot_drift` if the engine moved.
  Working settings (`default_universe/_alloc_mode/_portfolio_value`) persist
  on the client record. App + proposal share `DEFAULT_ALLOC_MODE` (Fundamental).
- **Cover:** full-bleed brand Nightblue via a behind-text image in the
  first-page header (renders in Word AND the LibreOffice PDF; body stays white).
- **i18n:** DE leaks fixed (no `{n}`/raw underscores; `Vertraulich` footer;
  localized dates via `format_long_date`). Note: tier/role tags + EUR-by-
  domicile default are deliberately deferred.

## Brand
- Nightblue `#010626`, Deep Indigo `#060d43`, Electric Sky `#0b688c`
- Sandstone `#bfb3a8`, Sunset Ember `#d06643`
- Fonts: Söhne (body), SometimesTimes (headings)

## Deployment
```bash
# Deploy to Render (auto-deploy from main branch)
git push origin main
```
