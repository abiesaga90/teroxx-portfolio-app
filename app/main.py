"""
Teroxx Portfolio Allocation Model — FastAPI Web App
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.data import (
    RISK_PROFILES, ALLOCATION_MODES,
    DRAWDOWN_IMPACT, FIVE_FACTOR_WEIGHTS, TEN_FACTOR_WEIGHTS,
    TIER_ALLOCATIONS, FIXED_STRATEGIC,
    ASSET_UNIVERSE, ASSET_BY_TICKER,
    TOKEN_MAP, DEFILLAMA_MAP, DEFILLAMA_FEES_MAP,
)
from app.engine import (
    compute_allocations, compute_portfolio, compute_dca,
    compute_rebalance, compute_pnl, compute_rebalance_pnl,
    get_universe_tickers, five_factor_detail, ten_factor_detail, token_scorecard,
    full_data_breakdown, compute_p3_scores, compute_red_flag_scores,
    detect_vol_regime, compute_stress_scenarios, compute_diversification_score,
    compute_dca_backtest,
)
from app.market_data import (
    fetch_prices, fetch_market_data, price_age_str, background_refresh,
    get_logo_url, get_source_health, fetch_historical_prices,
    fetch_defillama_data, fetch_defillama_protocol_detail,
    fetch_messari_networks, fetch_coingecko_dev_data, fetch_binance_perp_data,
)
from app.defi_health import refresh_defi_health, get_defi_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UNIVERSE_OPTIONS = [
    "Teroxx Core (9)",
    "Teroxx Core+Additional (15)",
    "Pre-Kraken Embed (22)",
    "Full (24)",
    "Teroxx Research (21)",
    "Long (79)",
    "Extended (87)",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fetch data before accepting requests so "Prices: No data" never shows
    try:
        await fetch_prices()
        await fetch_market_data()
        logger.info("Initial market data loaded")
    except Exception as e:
        logger.warning(f"Initial fetch failed (will retry in background): {e}")
    # Fetch fast scoring data on startup (DeFiLlama, Messari, Binance)
    for name, fn in [
        ("DeFiLlama", fetch_defillama_data),
        ("DeFiLlama protocols", fetch_defillama_protocol_detail),
        ("Messari networks", fetch_messari_networks),
        ("Binance perps", fetch_binance_perp_data),
    ]:
        try:
            await fn()
            logger.info(f"Initial {name} data loaded")
        except Exception as e:
            logger.warning(f"Initial {name} fetch failed: {e}")
    # CoinGecko dev data is slow (87 tokens × 2s + rate limits) — load in background
    asyncio.create_task(fetch_coingecko_dev_data())
    # DeFi health (non-blocking — ok if it fails on first load)
    try:
        await refresh_defi_health()
    except Exception as e:
        logger.warning(f"Initial DeFi health fetch failed: {e}")
    task = asyncio.create_task(background_refresh())

    async def _defi_health_loop():
        while True:
            await asyncio.sleep(7200)  # 2 hours
            try:
                await refresh_defi_health()
            except Exception as e:
                logger.warning(f"DeFi health refresh failed: {e}")
    defi_task = asyncio.create_task(_defi_health_loop())
    yield
    task.cancel()
    defi_task.cancel()


app = FastAPI(title="Teroxx Portfolio Allocator", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def fmt_pct(value):
    if value is None:
        return "-"
    return f"{value * 100:.2f}%"

def fmt_usd(value):
    if value is None:
        return "-"
    return f"${value:,.2f}"

def fmt_num(value, decimals=2):
    if value is None:
        return "-"
    return f"{value:,.{decimals}f}"

def fmt_compact(value):
    """Format large numbers: $1.42T, $88.3B, $4.16M, $72.0K"""
    if value is None or value == 0:
        return "-"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1e12:
        return f"{sign}${abs_val / 1e12:.2f}T"
    if abs_val >= 1e9:
        return f"{sign}${abs_val / 1e9:.1f}B"
    if abs_val >= 1e6:
        return f"{sign}${abs_val / 1e6:.1f}M"
    if abs_val >= 1e3:
        return f"{sign}${abs_val / 1e3:.0f}K"
    return f"{sign}${abs_val:,.0f}"

templates.env.filters["fmt_pct"] = fmt_pct
templates.env.filters["fmt_usd"] = fmt_usd
templates.env.filters["fmt_num"] = fmt_num
templates.env.filters["fmt_compact"] = fmt_compact
templates.env.globals["json_dumps"] = json.dumps
templates.env.globals["get_logo"] = get_logo_url


@app.get("/health")
async def health():
    return {"status": "ok"}


def _position_chart_data(positions: list[dict]) -> str:
    """Per-position pie chart data (only assets with alloc > 0)."""
    labels = [p["ticker"] for p in positions if p["alloc_pct"] > 0]
    values = [p["alloc_pct"] for p in positions if p["alloc_pct"] > 0]
    return json.dumps({"labels": labels, "values": values})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    profile = "Balanced"
    universe = "Full (24)"
    mode = "Fundamental"
    portfolio_value = 100000
    positions = compute_portfolio(profile, universe, mode, portfolio_value)
    defensive_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] in ("USDC", "EURC", "PAXG"))
    crypto_pct = 1 - defensive_pct
    dd_50 = DRAWDOWN_IMPACT["Crypto -50%"].get(profile, 0)
    return templates.TemplateResponse("base.html", {
        "request": request,
        "profiles": RISK_PROFILES,
        "universes": UNIVERSE_OPTIONS,
        "modes": ALLOCATION_MODES,
        "profile": profile,
        "universe": universe,
        "mode": mode,
        "positions": positions,
        "portfolio_value": portfolio_value,
        "defensive_pct": defensive_pct,
        "crypto_pct": crypto_pct,
        "dd_50": dd_50,
        "position_chart_data": _position_chart_data(positions),

        "tier_allocs": TIER_ALLOCATIONS,
        "fixed": FIXED_STRATEGIC,
        "price_age": price_age_str(),
        "n_tokens": len(TOKEN_MAP),
        "n_defillama": len(DEFILLAMA_MAP),
        "n_defillama_fees": len(DEFILLAMA_FEES_MAP),
        "defi_health": get_defi_health(),
        "vol_regime": detect_vol_regime(),
        "source_health": get_source_health(),
    })


# ── HTMX Partial Endpoints ──────────────────────────────────────────────

@app.post("/api/portfolio", response_class=HTMLResponse)
async def portfolio_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (24)"),
    mode: str = Form("Standard"),
    portfolio_value: float = Form(100000),
):
    positions = compute_portfolio(profile, universe, mode, portfolio_value)
    defensive_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] in ("USDC", "EURC", "PAXG"))
    crypto_pct = 1 - defensive_pct
    dd_50 = DRAWDOWN_IMPACT["Crypto -50%"].get(profile, 0)
    # Risk heatmap: category × risk_tier allocation matrix
    risk_tiers = ["Defensive", "Core", "Growth", "Speculative"]
    heatmap = {}
    for pos in positions:
        cat = ASSET_BY_TICKER.get(pos["ticker"], {}).get("category", "Other")
        rt = ASSET_BY_TICKER.get(pos["ticker"], {}).get("risk_tier", "Speculative")
        if cat not in heatmap:
            heatmap[cat] = {r: 0 for r in risk_tiers}
        heatmap[cat][rt] = heatmap[cat].get(rt, 0) + pos["alloc_pct"]
    # Sort categories by total allocation
    heatmap_sorted = sorted(heatmap.items(), key=lambda x: -sum(x[1].values()))
    heatmap_cats = [x[0] for x in heatmap_sorted]
    heatmap_data = {cat: vals for cat, vals in heatmap_sorted}

    # Sector allocation data for stacked bar chart
    sector_matrix = {}
    for p_name in RISK_PROFILES:
        sector_matrix[p_name] = {}
        p_positions = compute_portfolio(p_name, universe, mode, portfolio_value)
        for pos in p_positions:
            cat = ASSET_BY_TICKER.get(pos["ticker"], {}).get("category", "Other")
            sector_matrix[p_name][cat] = sector_matrix[p_name].get(cat, 0) + pos["alloc_pct"]
    all_cats = sorted(set(c for pm in sector_matrix.values() for c in pm))
    sector_data = json.dumps({
        "profiles": RISK_PROFILES,
        "categories": all_cats,
        "matrix": sector_matrix,
    })

    # Stress scenarios + diversification
    stress = compute_stress_scenarios(positions, portfolio_value)
    diversity = compute_diversification_score(positions)

    return templates.TemplateResponse("partials/portfolio_results_new.html", {
        "request": request,
        "positions": positions,
        "portfolio_value": portfolio_value,
        "profile": profile,
        "profiles": RISK_PROFILES,
        "defensive_pct": defensive_pct,
        "crypto_pct": crypto_pct,
        "dd_50": dd_50,
        "position_chart_data": _position_chart_data(positions),
        "sector_data": sector_data,
        "heatmap_cats": heatmap_cats,
        "heatmap_data": heatmap_data,
        "risk_tiers": risk_tiers,
        "stress_scenarios": stress,
        "diversity": diversity,

        "tier_allocs": TIER_ALLOCATIONS,
        "fixed": FIXED_STRATEGIC,
        "price_age": price_age_str(),
    })


@app.post("/api/scoring", response_class=HTMLResponse)
async def scoring_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (24)"),
    model: str = Form("factor"),
):
    tickers = [t for t in get_universe_tickers(universe) if t not in ("USDC", "EURC", "PAXG")]
    if model == "fundamental":
        detail = ten_factor_detail(profile, tickers)
        weights = TEN_FACTOR_WEIGHTS
        model_label = "Sector-Differentiated Scoring"
        is_fundamental = True
    else:
        detail = five_factor_detail(profile, tickers)
        weights = FIVE_FACTOR_WEIGHTS
        model_label = "5-Factor Model"
        is_fundamental = False

    # Build chart data from scoring detail
    factor_names = list(weights.keys())
    top5 = detail[:5]

    # Radar chart: top 5 tokens (use their sector signal names)
    if is_fundamental:
        # For sector-differentiated: use common 7-point radar with each token's own signals
        radar_labels = [f"Signal {i+1}" for i in range(7)]
        radar_tokens = []
        for d in top5:
            snames = d.get("_signal_names", [])
            radar_tokens.append({
                "ticker": d["ticker"],
                "scores": [d.get(n, 50) for n in snames[:7]],
                "labels": snames[:7],
            })
        radar_data = json.dumps({"factors": radar_labels, "tokens": radar_tokens})
    else:
        radar_data = json.dumps({
            "factors": factor_names,
            "tokens": [{"ticker": d["ticker"], "scores": [d.get(f, 50) for f in factor_names]} for d in top5],
        })

    # Bubble chart: risk/return scatter (all tokens with raw data)
    bubble_tokens = []
    for d in detail:
        raw = d.get("_raw", {})
        if raw.get("market_cap", 0) > 0:
            asset = ASSET_BY_TICKER.get(d["ticker"], {})
            bubble_tokens.append({
                "ticker": d["ticker"],
                "vol": abs(raw.get("change_30d", 0)),
                "mom": (raw.get("change_7d", 0) or 0) + (raw.get("change_30d", 0) or 0),
                "mcap": raw.get("market_cap", 0),
                "cat": d.get("_sector_label") or asset.get("category", "Other"),
            })
    bubble_data = json.dumps({"tokens": bubble_tokens})

    # Dilution bar chart: sorted by FDV/MCap
    dilution_items = []
    for d in detail:
        raw = d.get("_raw", {})
        fdv_ratio = raw.get("fdv_mcap_ratio") if raw else None
        if fdv_ratio and fdv_ratio > 0:
            dilution_items.append((d["ticker"], fdv_ratio))
    dilution_items.sort(key=lambda x: -x[1])
    dilution_data = json.dumps({
        "labels": [x[0] for x in dilution_items[:15]],
        "values": [round(x[1], 2) for x in dilution_items[:15]],
    })

    # For sector-differentiated: pass sector info to template
    from app.data import SECTOR_SIGNAL_NAMES, SECTOR_WEIGHTS, SECTOR_LABELS
    sector_info = {
        sector: {"label": SECTOR_LABELS[sector], "signals": SECTOR_SIGNAL_NAMES[sector], "weights": SECTOR_WEIGHTS[sector]}
        for sector in SECTOR_SIGNAL_NAMES
    }

    return templates.TemplateResponse("partials/scoring_results.html", {
        "request": request,
        "detail": detail,
        "weights": weights,
        "profile": profile,
        "profiles": RISK_PROFILES,
        "model_label": model_label,
        "is_fundamental": is_fundamental,
        "price_age": price_age_str(),
        "radar_data": radar_data,
        "bubble_data": bubble_data,
        "dilution_data": dilution_data,
        "sector_info": sector_info,
    })


@app.post("/api/dca", response_class=HTMLResponse)
async def dca_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (24)"),
    mode: str = Form("Standard"),
    monthly_amount: float = Form(1000),
    dca_scope: str = Form("BTC + Large Cap"),
    horizon_months: int = Form(12),
    min_order: float = Form(10),
):
    schedule = compute_dca(profile, universe, mode, monthly_amount, dca_scope, horizon_months, min_order)

    # DCA chart: stacked cumulative per token + total invested line
    top_dca = [s for s in schedule if s.get("monthly_buy", 0) > 0][:8]
    months = list(range(1, horizon_months + 1))
    month_labels = [f"M{m}" for m in months]
    dca_series = []
    for s in top_dca:
        monthly = s.get("monthly_buy", 0)
        dca_series.append({
            "label": s["ticker"],
            "values": [round(monthly * m, 2) for m in months],
        })
    # Total invested line
    total_invested = [round(monthly_amount * m, 2) for m in months]
    # Projected units accumulated per token at current prices
    projected_units = []
    for s in top_dca:
        price = s.get("price") or 0
        monthly = s.get("monthly_buy", 0)
        if price > 0:
            projected_units.append({
                "ticker": s["ticker"],
                "units_per_month": round(monthly / price, 6),
                "total_units": round(monthly * horizon_months / price, 6),
                "current_price": price,
            })

    dca_chart_data = json.dumps({
        "months": month_labels,
        "series": dca_series,
        "total_invested": total_invested,
        "projected_units": projected_units,
    })

    return templates.TemplateResponse("partials/dca_results.html", {
        "request": request,
        "schedule": schedule,
        "monthly_amount": monthly_amount,
        "horizon_months": horizon_months,
        "price_age": price_age_str(),
        "dca_chart_data": dca_chart_data,
    })


@app.post("/api/dca-backtest", response_class=HTMLResponse)
async def dca_backtest_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Teroxx Core (9)"),
    mode: str = Form("Standard"),
    monthly_amount: float = Form(1000),
    dca_scope: str = Form("All Crypto"),
    months_back: int = Form(12),
):
    # Only fetch historical prices for tokens in scope (not entire universe)
    from app.data import DCA_SCOPES
    scope_def = DCA_SCOPES.get(dca_scope, "all")
    if isinstance(scope_def, list):
        fetch_tickers = scope_def
    else:
        tickers = get_universe_tickers(universe)
        fetch_tickers = [t for t in tickers if t not in ("USDC", "EURC", "PAXG")]

    # Fetch historical prices (cached 24h)
    historical = await fetch_historical_prices(fetch_tickers, days=months_back * 31)

    # Run backtest
    data = compute_dca_backtest(
        profile, universe, mode, monthly_amount, dca_scope,
        historical, months_back,
    )

    # Chart data: invested vs value over time + buy prices per token
    snapshots = data.get("monthly_snapshots", [])
    # Collect all tickers that have buy prices
    all_buy_tickers = set()
    for s in snapshots:
        all_buy_tickers.update(s.get("buy_prices", {}).keys())

    backtest_chart_data = json.dumps({
        "months": [s["month"] for s in snapshots],
        "invested": [s["invested"] for s in snapshots],
        "value": [s["value"] for s in snapshots],
        "buy_prices": {
            ticker: [s.get("buy_prices", {}).get(ticker) for s in snapshots]
            for ticker in sorted(all_buy_tickers)
        },
    })

    return templates.TemplateResponse("partials/dca_backtest_results.html", {
        "request": request,
        "data": data,
        "backtest_chart_data": backtest_chart_data,
        "price_age": price_age_str(),
    })


@app.post("/api/rebalance-pnl", response_class=HTMLResponse)
async def rebalance_pnl_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (24)"),
    mode: str = Form("Standard"),
    portfolio_value: float = Form(100000),
    positions_json: str = Form("{}"),
):
    try:
        positions = json.loads(positions_json)
    except (json.JSONDecodeError, TypeError):
        positions = {}
    data = compute_rebalance_pnl(profile, universe, mode, portfolio_value, positions)

    # P&L waterfall chart
    pnl_items = []
    for row in data.get("rows", []):
        pnl = row.get("pnl_usd", 0)
        if pnl != 0:
            pnl_items.append((row.get("ticker", "?"), round(pnl, 2)))
    pnl_items.sort(key=lambda x: -abs(x[1]))
    pnl_chart_data = json.dumps({
        "labels": [x[0] for x in pnl_items[:15]],
        "values": [x[1] for x in pnl_items[:15]],
    })

    return templates.TemplateResponse("partials/rebalance_pnl_results.html", {
        "request": request,
        "data": data,
        "portfolio_value": portfolio_value,
        "price_age": price_age_str(),
        "pnl_chart_data": pnl_chart_data,
    })


@app.get("/api/token/{ticker}", response_class=HTMLResponse)
async def token_detail(request: Request, ticker: str, profile: str = "Balanced"):
    data = token_scorecard(ticker, profile)
    radar_data = json.dumps({
        "factors": data["factor_names_5"],
        "token_scores": [data["five_factor"][f] for f in data["factor_names_5"]],
        "median_scores": [data["five_medians"][f] for f in data["factor_names_5"]],
        "token_label": data["ticker"],
    })
    return templates.TemplateResponse("partials/token_modal.html", {
        "request": request,
        "d": data,
        "radar_data": radar_data,
    })


@app.post("/api/data", response_class=HTMLResponse)
async def data_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (24)"),
):
    tickers = [t for t in get_universe_tickers(universe) if t not in ("USDC", "EURC", "PAXG")]
    rows = full_data_breakdown(tickers, profile)
    return templates.TemplateResponse("partials/data_results.html", {
        "request": request,
        "rows": rows,
        "profile": profile,
        "profiles": RISK_PROFILES,
        "price_age": price_age_str(),
    })
