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
    RISK_PROFILES, ALLOCATION_MODES, ASSET_CLASS_ALLOCATIONS,
    DRAWDOWN_IMPACT, FIVE_FACTOR_WEIGHTS, TEN_FACTOR_WEIGHTS,
    RISK_TILT_PARAMETERS, TIER_ALLOCATIONS, FIXED_STRATEGIC,
    ASSET_UNIVERSE, ASSET_BY_TICKER,
)
from app.engine import (
    compute_allocations, compute_portfolio, compute_dca,
    compute_rebalance, compute_pnl, get_universe_tickers,
    five_factor_detail, ten_factor_detail,
)
from app.market_data import fetch_prices, fetch_market_data, price_age_str, background_refresh, get_logo_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UNIVERSE_OPTIONS = [
    "Teroxx Core (10)",
    "Teroxx Core+Additional (16)",
    "Pre-Kraken Embed (23)",
    "Full (25)",
    "Long (53)",
    "Extended (79)",
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
    task = asyncio.create_task(background_refresh())
    yield
    task.cancel()


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

templates.env.filters["fmt_pct"] = fmt_pct
templates.env.filters["fmt_usd"] = fmt_usd
templates.env.filters["fmt_num"] = fmt_num
templates.env.globals["json_dumps"] = json.dumps
templates.env.globals["get_logo"] = get_logo_url


@app.get("/health")
async def health():
    return {"status": "ok"}


def _chart_data(profile: str) -> str:
    labels = list(ASSET_CLASS_ALLOCATIONS.keys())
    values = [ASSET_CLASS_ALLOCATIONS[cls][profile] for cls in labels]
    return json.dumps({"labels": labels, "values": values})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    profile = "Balanced"
    universe = "Full (25)"
    mode = "Standard"
    allocs = compute_allocations(profile, universe, mode)
    return templates.TemplateResponse("base.html", {
        "request": request,
        "profiles": RISK_PROFILES,
        "universes": UNIVERSE_OPTIONS,
        "modes": ALLOCATION_MODES,
        "profile": profile,
        "universe": universe,
        "mode": mode,
        "allocs": allocs,
        "asset_class_allocs": ASSET_CLASS_ALLOCATIONS,
        "drawdown": DRAWDOWN_IMPACT,
        "chart_data": _chart_data(profile),
        "price_age": price_age_str(),
    })


# ── HTMX Partial Endpoints ──────────────────────────────────────────────

@app.post("/api/allocator", response_class=HTMLResponse)
async def allocator_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
    mode: str = Form("Standard"),
):
    allocs = compute_allocations(profile, universe, mode)
    return templates.TemplateResponse("partials/allocator_results.html", {
        "request": request,
        "allocs": allocs,
        "profile": profile,
        "asset_class_allocs": ASSET_CLASS_ALLOCATIONS,
        "drawdown": DRAWDOWN_IMPACT,
        "chart_data": _chart_data(profile),
        "price_age": price_age_str(),
    })


@app.post("/api/portfolio", response_class=HTMLResponse)
async def portfolio_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
    mode: str = Form("Standard"),
    portfolio_value: float = Form(100000),
):
    positions = compute_portfolio(profile, universe, mode, portfolio_value)
    crypto_allocs = [p for p in positions if p["ticker"] not in ("USDC", "EURC")]
    defensive_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] in ("USDC", "EURC", "PAXG"))
    crypto_pct = 1 - defensive_pct
    dd_50 = DRAWDOWN_IMPACT["Crypto -50%"].get(profile, 0)
    return templates.TemplateResponse("partials/portfolio_results.html", {
        "request": request,
        "positions": positions,
        "portfolio_value": portfolio_value,
        "profile": profile,
        "defensive_pct": defensive_pct,
        "crypto_pct": crypto_pct,
        "dd_50": dd_50,
        "price_age": price_age_str(),
    })


@app.post("/api/dca", response_class=HTMLResponse)
async def dca_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
    mode: str = Form("Standard"),
    monthly_amount: float = Form(1000),
    dca_scope: str = Form("BTC + Large Cap"),
    horizon_months: int = Form(12),
    min_order: float = Form(10),
):
    schedule = compute_dca(profile, universe, mode, monthly_amount, dca_scope, horizon_months, min_order)
    return templates.TemplateResponse("partials/dca_results.html", {
        "request": request,
        "schedule": schedule,
        "monthly_amount": monthly_amount,
        "horizon_months": horizon_months,
        "price_age": price_age_str(),
    })


@app.post("/api/factor-scores", response_class=HTMLResponse)
async def factor_scores_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
):
    tickers = [t for t in get_universe_tickers(universe) if t not in ("USDC", "EURC", "PAXG")]
    detail = five_factor_detail(profile, tickers)
    return templates.TemplateResponse("partials/factor_results.html", {
        "request": request,
        "detail": detail,
        "weights": FIVE_FACTOR_WEIGHTS,
        "profile": profile,
        "profiles": RISK_PROFILES,
        "price_age": price_age_str(),
    })


@app.post("/api/fundamentals", response_class=HTMLResponse)
async def fundamentals_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
):
    tickers = [t for t in get_universe_tickers(universe) if t not in ("USDC", "EURC", "PAXG")]
    detail = ten_factor_detail(profile, tickers)
    return templates.TemplateResponse("partials/fundamental_results.html", {
        "request": request,
        "detail": detail,
        "weights": TEN_FACTOR_WEIGHTS,
        "profile": profile,
        "profiles": RISK_PROFILES,
        "price_age": price_age_str(),
    })


@app.post("/api/allocations-detail", response_class=HTMLResponse)
async def allocations_detail_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
    mode: str = Form("Standard"),
):
    allocs = compute_allocations(profile, universe, mode)
    return templates.TemplateResponse("partials/allocations_results.html", {
        "request": request,
        "allocs": allocs,
        "profile": profile,
        "profiles": RISK_PROFILES,
        "risk_tilts": RISK_TILT_PARAMETERS,
        "tier_allocs": TIER_ALLOCATIONS,
        "fixed": FIXED_STRATEGIC,
        "price_age": price_age_str(),
    })


@app.post("/api/rebalancing", response_class=HTMLResponse)
async def rebalancing_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Full (25)"),
    mode: str = Form("Standard"),
    portfolio_value: float = Form(100000),
    current_holdings: str = Form("{}"),
):
    try:
        holdings = json.loads(current_holdings)
    except (json.JSONDecodeError, TypeError):
        holdings = {}
    results = compute_rebalance(profile, universe, mode, portfolio_value, holdings)
    return templates.TemplateResponse("partials/rebalancing_results.html", {
        "request": request,
        "results": results,
        "portfolio_value": portfolio_value,
        "price_age": price_age_str(),
    })


@app.post("/api/pnl", response_class=HTMLResponse)
async def pnl_partial(
    request: Request,
    positions_json: str = Form("[]"),
):
    try:
        positions = json.loads(positions_json)
    except (json.JSONDecodeError, TypeError):
        positions = []
    results = compute_pnl(positions)
    total_cost = sum(r["cost_basis"] for r in results)
    total_value = sum(r["current_value"] for r in results)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    return templates.TemplateResponse("partials/pnl_results.html", {
        "request": request,
        "results": results,
        "total_cost": total_cost,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "price_age": price_age_str(),
    })
