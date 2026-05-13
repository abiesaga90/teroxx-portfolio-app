"""
Teroxx Portfolio Allocation Model — FastAPI Web App
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.data import (
    RISK_PROFILES, ALLOCATION_MODES,
    DRAWDOWN_IMPACT, TEN_FACTOR_WEIGHTS,
    TIER_ALLOCATIONS, FIXED_STRATEGIC,
    ASSET_UNIVERSE, ASSET_BY_TICKER,
    TOKEN_MAP, DEFILLAMA_MAP, DEFILLAMA_FEES_MAP,
)
from app.engine import (
    compute_allocations, compute_portfolio, compute_dca,
    compute_rebalance, compute_pnl, compute_rebalance_pnl,
    get_universe_tickers, ten_factor_detail, token_scorecard,
    full_data_breakdown, compute_p3_scores, compute_red_flag_scores,
    detect_vol_regime, compute_stress_scenarios, compute_diversification_score,
    compute_dca_backtest, compute_client_portfolio_pnl,
    compute_client_portfolio_history,
    compute_client_drift, compute_scenario_comparison,
)
from app.macro_regime import get_macro_regime, refresh_macro_regime
from app.session_context import SessionContext, load_context, patch_context
from app.db import SessionLocal, get_db, log_action
from app.repos import clients as clients_repo
from app.pdf.proposal import ProposalInputs, build_proposal_context, render_pdf as render_proposal_pdf
from fastapi.responses import Response


def list_clients():
    """DB-backed summary list (replaces the demo_clients dict accessor)."""
    with SessionLocal() as db:
        return [clients_repo.to_summary_dict(c) for c in clients_repo.list_active_clients(db)]


def get_client(client_id: str):
    """DB-backed read returning the legacy dict shape engine code expects."""
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        return clients_repo.to_legacy_dict(c) if c else None
from app.market_data import (
    fetch_prices, fetch_market_data, price_age_str, background_refresh,
    get_logo_url, get_source_health, fetch_historical_prices,
    fetch_defillama_data, fetch_defillama_protocol_detail,
    fetch_messari_networks, fetch_coingecko_dev_data, fetch_binance_perp_data,
    fetch_btc_volatility,
)
from app.defi_health import refresh_defi_health, get_defi_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UNIVERSE_OPTIONS = [
    "Teroxx Core (9)",
    "Teroxx Expanded (21)",
]


async def _initial_warmup():
    # Run all initial data fetches in background so the port binds fast
    # enough for Render's health check. Endpoints handle missing data
    # gracefully ("No data" placeholders) until the warmup completes.
    try:
        await fetch_prices()
        await fetch_market_data()
        logger.info("Initial market data loaded")
    except Exception as e:
        logger.warning(f"Initial fetch failed (will retry in background): {e}")
    from app.macro_regime import refresh_macro_regime
    for name, fn in [
        ("DeFiLlama", fetch_defillama_data),
        ("DeFiLlama protocols", fetch_defillama_protocol_detail),
        ("Messari networks", fetch_messari_networks),
        ("Binance perps", fetch_binance_perp_data),
        ("BTC volatility", fetch_btc_volatility),
        ("Macro regime", refresh_macro_regime),
    ]:
        try:
            await fn()
            logger.info(f"Initial {name} data loaded")
        except Exception as e:
            logger.warning(f"Initial {name} fetch failed: {e}")
    asyncio.create_task(fetch_coingecko_dev_data())
    try:
        await refresh_defi_health()
    except Exception as e:
        logger.warning(f"Initial DeFi health fetch failed: {e}")


async def _defi_health_loop():
    while True:
        await asyncio.sleep(7200)  # 2 hours
        try:
            await refresh_defi_health()
        except Exception as e:
            logger.warning(f"DeFi health refresh failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Persistence comes online before background refreshers so any
    # downstream code can already read clients/lots/audit rows.
    try:
        from app.db import init_db, DB_PATH
        init_db()
        logger.info("SQLite ready at %s", DB_PATH)
    except Exception as e:
        logger.exception("Failed to initialise SQLite: %s", e)
    warmup_task = asyncio.create_task(_initial_warmup())
    refresh_task = asyncio.create_task(background_refresh())
    defi_task = asyncio.create_task(_defi_health_loop())
    yield
    warmup_task.cancel()
    refresh_task.cancel()
    defi_task.cancel()


app = FastAPI(title="Teroxx Portfolio Allocator", lifespan=lifespan)
from app.auth import SESSION_SECRET, verify_password, get_current_user, require_auth
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/static") or path in ("/health", "/login", "/favicon.ico"):
            return await call_next(request)
        # CRM-facing surfaces have their own bearer-token auth.
        if path.startswith("/api/v1/") or path.startswith("/webhooks/"):
            return await call_next(request)
        user = get_current_user(request)
        if not user and path != "/logout":
            if path.startswith("/api/"):
                return HTMLResponse("Session expired. Please refresh the page.", status_code=401)
            return RedirectResponse("/login", status_code=302)
        return await call_next(request)


# Order matters: SessionMiddleware must wrap AuthMiddleware (added last = outermost)
app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=86400 * 7)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Mount the stable v1 API (bearer-token auth).
from app.api_v1 import router as api_v1_router
app.include_router(api_v1_router)


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


# ── User Preferences ───────────────────────────────────────────────

PREF_DEFAULTS = {
    "profile": "Balanced",
    "universe": "Teroxx Core (9)",
    "mode": "Fundamental",
    "portfolio_value": 100000,
}

PREF_KEYS = set(PREF_DEFAULTS.keys())


@app.post("/api/save-prefs")
async def save_prefs(request: Request):
    body = await request.json()
    prefs = request.session.get("prefs", {})
    for k, v in body.items():
        if k in PREF_KEYS:
            prefs[k] = v
    request.session["prefs"] = prefs
    # Mirror into SessionContext so the new context-aware surfaces stay in sync.
    patch_context(request, **{k: v for k, v in body.items() if k in PREF_KEYS})
    return {"ok": True}


@app.get("/api/session")
async def get_session(request: Request):
    """Return the current SessionContext as JSON for the frontend shim."""
    return load_context(request).model_dump()


@app.post("/api/session")
async def update_session(request: Request):
    """Patch one or more SessionContext fields from the frontend shim.

    Accepts JSON body with any of: mode, client_id, universe, profile,
    portfolio_value. Unknown keys are ignored.
    """
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)
    ctx = patch_context(request, **body)
    return ctx.model_dump()


# ── Authentication Routes ────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "email": None})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    if verify_password(email, password):
        request.session["user_email"] = email.lower()
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {
        "request": request, "error": "Invalid email or password.", "email": email,
    })


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


def _position_chart_data(positions: list[dict]) -> str:
    """Per-position pie chart data (only assets with alloc > 0)."""
    labels = [p["ticker"] for p in positions if p["alloc_pct"] > 0]
    values = [p["alloc_pct"] for p in positions if p["alloc_pct"] > 0]
    return json.dumps({"labels": labels, "values": values})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    # SessionContext is the new source of truth; prefs are still consulted
    # by load_context() for back-compat.
    ctx = load_context(request)
    prefs = request.session.get("prefs", {})
    profile = ctx.profile or prefs.get("profile", PREF_DEFAULTS["profile"])
    universe = ctx.universe or prefs.get("universe", PREF_DEFAULTS["universe"])
    mode = prefs.get("mode", PREF_DEFAULTS["mode"])  # allocation mode (Standard/Fundamental); distinct from ctx.mode
    portfolio_value = ctx.portfolio_value or prefs.get("portfolio_value", PREF_DEFAULTS["portfolio_value"])
    positions = compute_portfolio(profile, universe, mode, portfolio_value)
    defensive_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] in ("USDC", "EURC", "PAXG"))
    crypto_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] not in ("USDC", "EURC", "PAXG"))
    dd_50 = DRAWDOWN_IMPACT["Crypto -50%"].get(profile, 0)
    return templates.TemplateResponse("base.html", {
        "request": request,
        "current_user": user,
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
        "clients_list": list_clients(),
        "ctx": ctx.model_dump(),
        "app_mode": ctx.mode,
    })


# ── HTMX Partial Endpoints ──────────────────────────────────────────────

@app.post("/api/portfolio", response_class=HTMLResponse)
async def portfolio_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Teroxx Core (9)"),
    mode: str = Form("Standard"),
    portfolio_value: float = Form(100000),
):
    positions = compute_portfolio(profile, universe, mode, portfolio_value)
    defensive_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] in ("USDC", "EURC", "PAXG"))
    crypto_pct = sum(p["alloc_pct"] for p in positions if p["ticker"] not in ("USDC", "EURC", "PAXG"))
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
        "universe": universe,
        "clients": list_clients(),
    })


@app.post("/api/scoring", response_class=HTMLResponse)
async def scoring_partial(
    request: Request,
    profile: str = Form("Balanced"),
    universe: str = Form("Teroxx Core (9)"),
):
    tickers = [t for t in get_universe_tickers(universe) if t not in ("USDC", "EURC", "PAXG")]
    detail = ten_factor_detail(profile, tickers)
    weights = TEN_FACTOR_WEIGHTS
    model_label = "Sector-Differentiated Scoring"

    top5 = detail[:5]

    # Radar chart: top 5 tokens (use their sector signal names)
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
    top_dilutive = dilution_items[:15]
    # Reverse so the bar chart (top→bottom of the y-axis) puts most-dilutive at the BOTTOM.
    top_dilutive.reverse()
    dilution_data = json.dumps({
        "labels": [x[0] for x in top_dilutive],
        "values": [round(x[1], 2) for x in top_dilutive],
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
    universe: str = Form("Teroxx Core (9)"),
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
    universe: str = Form("Teroxx Core (9)"),
    mode: str = Form("Standard"),
    portfolio_value: float = Form(100000),
    positions_json: str = Form("{}"),
):
    try:
        positions = json.loads(positions_json)
    except (json.JSONDecodeError, TypeError):
        positions = {}
    data = compute_rebalance_pnl(profile, universe, mode, portfolio_value, positions)

    # P&L waterfall chart — sourced from row["pnl"] (engine field name).
    pnl_items = []
    for row in data.get("rows", []):
        pnl = row.get("pnl", 0) or 0
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
        "factors": data["signal_names"],
        "token_scores": [data["va_signals"][n] for n in data["signal_names"]],
        "median_scores": [data["va_medians"][n] for n in data["signal_names"]],
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
    universe: str = Form("Teroxx Core (9)"),
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


@app.get("/api/market-context", response_class=HTMLResponse)
async def market_context_partial(request: Request):
    state = get_macro_regime()
    if state.get("result") is None:
        # First load — refresh inline so we don't render an empty page
        try:
            await refresh_macro_regime()
            state = get_macro_regime()
        except Exception as e:
            logger.warning(f"Macro regime inline refresh failed: {e}")
    return templates.TemplateResponse("partials/market_context_results.html", {
        "request": request,
        "state": state,
        "price_age": price_age_str(),
    })


@app.get("/api/client-positions")
async def client_positions_json(client_id: str = ""):
    """Return a {ticker: {current_usd, entry_price}} map sized at *live* mark
    for the requested client, so the Rebalancing & P&L tab can populate
    its Current $ and Entry Price inputs from a real client portfolio.

    `current_usd` is set to the live USD value of all lots in that ticker
    (qty * live price). `entry_price` is the qty-weighted average entry
    across that ticker's lots. Stable pegs default to $1 if no live mark.
    """
    c = get_client(client_id) if client_id else None
    if not c:
        return JSONResponse({"positions": {}, "client": None})
    from app.market_data import get_price
    STABLES = {"USDC", "EURC", "USDT", "DAI", "FDUSD"}
    agg: dict[str, dict] = {}
    for pos in c.get("positions", []) or []:
        ticker = pos.get("ticker", "")
        qty = float(pos.get("quantity", 0) or 0)
        entry = float(pos.get("entry_price", 0) or 0)
        if not ticker or qty <= 0:
            continue
        live = 1.0 if ticker in STABLES else (get_price(ticker) or 0.0)
        if live <= 0:
            live = entry  # fall back so the row isn't blank
        bucket = agg.setdefault(ticker, {"qty": 0.0, "cost": 0.0, "current_usd": 0.0})
        bucket["qty"] += qty
        bucket["cost"] += qty * entry
        bucket["current_usd"] += qty * live
    positions = {}
    for t, b in agg.items():
        avg_entry = (b["cost"] / b["qty"]) if b["qty"] > 0 else 0.0
        positions[t] = {
            "current_usd": round(b["current_usd"], 2),
            "entry_price": round(avg_entry, 6),
        }
    return JSONResponse({
        "client": {"id": c.get("id"), "name": c.get("name"), "profile": c.get("profile")},
        "positions": positions,
    })


@app.get("/api/client-portfolio", response_class=HTMLResponse)
async def client_portfolio_partial(request: Request, client_id: str = ""):
    clients = list_clients()
    selected = None
    pnl = None
    history = None
    if client_id:
        c = get_client(client_id)
        if c:
            selected = client_id
            pnl = compute_client_portfolio_pnl(c)
            try:
                from datetime import date, datetime
                positions = c.get("positions", []) or []
                tickers = sorted({p.get("ticker", "") for p in positions if p.get("ticker")})
                earliest_str = min((p.get("entry_date", "") for p in positions if p.get("entry_date")), default="")
                days_needed = 365
                if earliest_str:
                    try:
                        edt = datetime.strptime(earliest_str, "%Y-%m-%d").date()
                        days_needed = max(30, (date.today() - edt).days + 7)
                    except ValueError:
                        pass
                hist_prices = await fetch_historical_prices(tickers, days=min(days_needed, 1900))
                history = compute_client_portfolio_history(c, hist_prices)
            except Exception as e:
                logger.warning(f"Client portfolio history failed for {client_id}: {e}")
                history = None
    return templates.TemplateResponse("partials/client_portfolio_results.html", {
        "request": request,
        "clients": clients,
        "selected": selected,
        "pnl": pnl,
        "history": history,
        "price_age": price_age_str(),
    })


# ── Workspace ────────────────────────────────────────────────────────


# ── Admin: API token management (Phase 9) ────────────────────────────


@app.get("/api/admin/api-tokens")
async def list_api_tokens(request: Request):
    """List API tokens (no secrets, only prefixes / metadata)."""
    from sqlalchemy import select
    from app.db import ApiToken
    with SessionLocal() as db:
        rows = db.execute(select(ApiToken).order_by(ApiToken.created_at.desc())).scalars().all()
        return [
            {
                "id": t.id, "name": t.name, "provider": t.provider,
                "prefix": t.token_prefix, "scopes": t.scopes,
                "created_at": t.created_at.isoformat(timespec="seconds"),
                "last_used_at": t.last_used_at.isoformat(timespec="seconds") if t.last_used_at else None,
                "revoked_at": t.revoked_at.isoformat(timespec="seconds") if t.revoked_at else None,
            }
            for t in rows
        ]


@app.post("/api/admin/api-tokens")
async def create_api_token(request: Request):
    """Mint a new API token. The plaintext value is returned only once."""
    from app.api_v1 import _new_token
    from app.db import ApiToken
    payload = await request.json()
    if not isinstance(payload, dict) or not payload.get("name"):
        return JSONResponse({"error": "name_required"}, status_code=400)
    plaintext, prefix, salt, token_hash = _new_token()
    actor = _actor_email(request) or "unknown"
    with SessionLocal() as db:
        row = ApiToken(
            name=str(payload["name"])[:160],
            provider=(payload.get("provider") or "internal")[:64],
            token_prefix=prefix,
            salt=salt,
            token_hash=token_hash,
            scopes=str(payload.get("scopes") or "clients:read")[:240],
            created_by=actor,
        )
        db.add(row)
        log_action(
            db, actor_email=actor, action_type="api_token_created",
            client_id=None,
            payload={"id": None, "name": row.name, "provider": row.provider, "scopes": row.scopes},
        )
        db.commit()
        db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "scopes": row.scopes,
        "prefix": row.token_prefix,
        "plaintext_token": plaintext,
        "warning": "Store this token now. It will not be shown again.",
    }


@app.delete("/api/admin/api-tokens/{token_id}")
async def revoke_api_token(request: Request, token_id: int):
    from app.db import ApiToken
    actor = _actor_email(request) or "unknown"
    with SessionLocal() as db:
        row = db.get(ApiToken, token_id)
        if not row:
            return JSONResponse({"error": "not_found"}, status_code=404)
        row.revoked_at = datetime.now(timezone.utc)
        log_action(
            db, actor_email=actor, action_type="api_token_revoked",
            client_id=None, payload={"id": token_id, "name": row.name},
        )
        db.commit()
        return {"ok": True}


# ── Scenarios (side-by-side comparison) ──────────────────────────────


@app.get("/api/scenarios/compare", response_class=HTMLResponse)
async def scenarios_compare_partial(
    request: Request,
    client_id: str = "",
    a_profile: str = "",
    a_universe: str = "",
    b_profile: str = "",
    b_universe: str = "",
):
    """Render the side-by-side scenario card for one client.

    Defaults: A = client's current target (profile + active universe);
    B = the same profile on the other available universe. Both can be
    overridden via query params.
    """
    ctx = load_context(request)
    if not client_id:
        client_id = ctx.client_id or ""
    if not client_id:
        return HTMLResponse(
            '<p style="padding:24px;color:var(--text-muted);">Select a client to compare scenarios.</p>'
        )
    c = get_client(client_id)
    if not c:
        return HTMLResponse('<p style="padding:24px;color:var(--text-muted);">Client not found.</p>')

    # Defaults: A = client's stated profile on the active universe;
    # B = same profile on the other universe so the diff has signal.
    universes = list(UNIVERSE_OPTIONS)
    default_universe = ctx.universe or universes[0]
    other_universe = next((u for u in universes if u != default_universe), default_universe)
    a_profile = a_profile or c.get("profile") or "Balanced"
    a_universe = a_universe or default_universe
    b_profile = b_profile or c.get("profile") or "Balanced"
    b_universe = b_universe or other_universe

    comp = compute_scenario_comparison(
        c,
        a_profile=a_profile, a_universe=a_universe,
        b_profile=b_profile, b_universe=b_universe,
    )
    with SessionLocal() as db:
        saved = clients_repo.list_scenarios(db, client_id)
        saved_payload = [{
            "id": s.id, "label": s.label,
            "a_profile": s.a_profile, "a_universe": s.a_universe,
            "b_profile": s.b_profile, "b_universe": s.b_universe,
        } for s in saved]

    return templates.TemplateResponse("partials/scenario_compare.html", {
        "request": request,
        "comp": comp,
        "profiles": RISK_PROFILES,
        "universes": universes,
        "saved_scenarios": saved_payload,
    })


@app.post("/api/clients/{client_id}/scenarios")
async def create_scenario_endpoint(request: Request, client_id: str):
    payload = await request.json()
    if not isinstance(payload, dict) or not payload.get("label"):
        return JSONResponse({"error": "label_required"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        s = clients_repo.create_scenario(
            db,
            actor_email=_actor_email(request),
            client_id=client_id,
            label=payload.get("label", ""),
            a_profile=payload.get("a_profile", ""),
            a_universe=payload.get("a_universe", ""),
            b_profile=payload.get("b_profile", ""),
            b_universe=payload.get("b_universe", ""),
            notes=payload.get("notes"),
        )
        db.commit()
        db.refresh(s)
        return {"id": s.id, "label": s.label}


@app.delete("/api/clients/{client_id}/scenarios/{scenario_id}")
async def delete_scenario_endpoint(request: Request, client_id: str, scenario_id: int):
    with SessionLocal() as db:
        from app.db import Scenario
        s = db.get(Scenario, scenario_id)
        if not s or s.client_id != client_id:
            return JSONResponse({"error": "not_found"}, status_code=404)
        clients_repo.delete_scenario(db, actor_email=_actor_email(request), scenario=s)
        db.commit()
        return {"ok": True}


# ── Client overview (drift roll-up) ──────────────────────────────────


@app.get("/api/client-overview", response_class=HTMLResponse)
async def client_overview_partial(request: Request):
    """Roll-up card listing every active client, sorted by max drift desc.

    Cheap to compute: walks the seeded client set once, uses cached live
    prices via compute_workspace_allocation(). Designed to embed above
    the Workspace tab as the advisor's "what needs attention" landing.
    """
    ctx = load_context(request)
    rows = []
    for summary in list_clients():
        client = get_client(summary["id"])
        if not client:
            continue
        try:
            drift = compute_client_drift(client, profile=client.get("profile"), universe=ctx.universe)
        except Exception as e:
            logger.warning("Drift compute failed for %s: %s", summary["id"], e)
            drift = {"max_drift_pp": None, "max_drift_ticker": None, "attention": False, "threshold_pp": None}
        try:
            pnl = compute_client_portfolio_pnl(client)
            total_value = pnl["summary"]["total_value"]
            total_pnl_pct = pnl["summary"]["total_pnl_pct"]
        except Exception as e:
            logger.warning("PnL compute failed for %s: %s", summary["id"], e)
            total_value = 0.0
            total_pnl_pct = 0.0
        rows.append({
            "id": client["id"],
            "name": client["name"],
            "profile": client.get("profile", "Balanced"),
            "domicile": client.get("domicile", ""),
            "total_value": total_value,
            "total_pnl_pct": total_pnl_pct,
            "max_drift_pp": drift.get("max_drift_pp"),
            "max_drift_ticker": drift.get("max_drift_ticker"),
            "attention": drift.get("attention", False),
            "threshold_pp": drift.get("threshold_pp"),
        })
    # Sort: attention first, then by max_drift desc.
    rows.sort(key=lambda r: (-(1 if r["attention"] else 0), -(r["max_drift_pp"] or 0)))
    return templates.TemplateResponse("partials/client_overview.html", {
        "request": request,
        "rows": rows,
    })


# ── Activity / Audit trail ───────────────────────────────────────────


def _format_activity_row(a, client_name_by_id: dict, actor_name_by_email: dict) -> dict:
    """Shape one AdvisorAction row for the Activity template / CSV export."""
    payload = a.payload_json or ""
    # Compact detail: strip surrounding {} for one-line table display.
    detail = payload.strip()
    if detail.startswith("{") and detail.endswith("}"):
        inner = detail[1:-1].strip()
        if len(inner) > 220:
            inner = inner[:217] + "..."
        detail = inner
    return {
        "id": a.id,
        "when": a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "actor_email": a.actor_email,
        "actor_name": actor_name_by_email.get((a.actor_email or "").lower()) or a.actor_email,
        "client_id": a.client_id,
        "client_name": client_name_by_id.get(a.client_id),
        "action_type": a.action_type,
        "detail": detail,
        "payload": payload,
    }


def _activity_query_lookups(db) -> tuple[dict, dict]:
    """Return (client_name_by_id, actor_name_by_email) maps used to enrich rows."""
    from app.auth import USERS
    client_name_by_id = {
        c.id: c.name for c in clients_repo.list_active_clients(db)
    }
    actor_name_by_email = {email.lower(): info["name"] for email, info in USERS.items()}
    return client_name_by_id, actor_name_by_email


@app.get("/api/activity", response_class=HTMLResponse)
async def activity_partial(
    request: Request,
    client_id: str = "",
    actor_email: str = "",
    action_type: str = "",
    days: int = 30,
    q: str = "",
):
    from app.auth import USERS
    with SessionLocal() as db:
        rows_raw = clients_repo.query_actions(
            db,
            client_id=client_id or None,
            actor_email=actor_email or None,
            action_type=action_type or None,
            days=days,
            q=q or None,
            limit=500,
        )
        client_name_by_id, actor_name_by_email = _activity_query_lookups(db)
        rows = [_format_activity_row(a, client_name_by_id, actor_name_by_email) for a in rows_raw]
        action_options = clients_repo.known_action_types(db)
        clients = [clients_repo.to_summary_dict(c) for c in clients_repo.list_active_clients(db)]
    actor_options = [(email.lower(), info["name"]) for email, info in USERS.items()]
    filters = {
        "client_id": client_id, "actor_email": actor_email,
        "action_type": action_type, "days": days, "q": q,
    }
    filters_applied = any([client_id, actor_email, action_type, days and days != 30, q])
    csv_query = "&".join(
        f"{k}={v}" for k, v in filters.items() if v not in (None, "", 0)
    )
    return templates.TemplateResponse("partials/activity.html", {
        "request": request,
        "rows": rows,
        "total_count": len(rows),
        "filters": filters,
        "filters_applied": filters_applied,
        "csv_query": csv_query,
        "actor_options": actor_options,
        "action_options": action_options,
        "clients": clients,
    })


@app.get("/api/activity.csv")
async def activity_csv(
    request: Request,
    client_id: str = "",
    actor_email: str = "",
    action_type: str = "",
    days: int = 30,
    q: str = "",
):
    import csv
    from io import StringIO
    with SessionLocal() as db:
        rows_raw = clients_repo.query_actions(
            db,
            client_id=client_id or None,
            actor_email=actor_email or None,
            action_type=action_type or None,
            days=days,
            q=q or None,
            limit=5000,
        )
        client_name_by_id, actor_name_by_email = _activity_query_lookups(db)
    buf = StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "id", "created_utc", "actor_email", "actor_name",
        "client_id", "client_name", "action_type", "payload_json",
    ])
    for a in rows_raw:
        writer.writerow([
            a.id,
            a.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            a.actor_email or "",
            actor_name_by_email.get((a.actor_email or "").lower(), ""),
            a.client_id or "",
            client_name_by_id.get(a.client_id, ""),
            a.action_type,
            a.payload_json or "",
        ])
    filename = f"teroxx_activity_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Client Review (calm screen-share surface) ────────────────────────


@app.get("/api/client-review", response_class=HTMLResponse)
async def client_review_partial(request: Request, client_id: str = ""):
    """Calm, read-only per-client review surface for screen-share / meetings."""
    ctx = load_context(request)
    if not client_id:
        client_id = ctx.client_id or ""
    clients = list_clients()
    selected_client = None
    pnl = None
    history = None
    donut_svg = ""
    legend = []
    narrative = {"portfolio": "", "macro": "", "next": ""}
    disclaimer = None
    as_of_date = datetime.utcnow().strftime("%d %B %Y")

    if not client_id and clients:
        client_id = clients[0]["id"]

    if client_id:
        c = get_client(client_id)
        if c:
            selected_client = c
            patch_context(request, client_id=client_id)
            pnl = compute_client_portfolio_pnl(c)
            # History (best effort).
            try:
                from datetime import date as _date, datetime as _dt
                positions = c.get("positions", []) or []
                tickers = sorted({p.get("ticker", "") for p in positions if p.get("ticker")})
                earliest_str = min(
                    (p.get("entry_date", "") for p in positions if p.get("entry_date")),
                    default="",
                )
                days_needed = 365
                if earliest_str:
                    try:
                        edt = _dt.strptime(earliest_str, "%Y-%m-%d").date()
                        days_needed = max(30, (_date.today() - edt).days + 7)
                    except ValueError:
                        pass
                hist_prices = await fetch_historical_prices(tickers, days=min(days_needed, 1900))
                history = compute_client_portfolio_history(c, hist_prices)
            except Exception as e:
                logger.warning("Client Review history fetch failed for %s: %s", client_id, e)
                history = None

            # Allocation donut sourced from the client's mark-to-market mix
            # (so the chart matches the table on screen).
            from app.pdf.exhibits import donut as _donut, donut_legend as _donut_legend
            ts = pnl.get("ticker_summary", []) if pnl else []
            slices = [(row["ticker"], float(row.get("current_value") or 0)) for row in ts]
            donut_svg = _donut(slices, width=320, height=320,
                               center_text=str(pnl["summary"]["n_unique_tickers"]) if pnl else "",
                               center_sub="positions")
            legend = _donut_legend(slices)

            # Macro state.
            macro = get_macro_regime()
            r = (macro or {}).get("result") or {}
            from app.pdf.narrative import client_review_narrative as _cv_narrative
            narrative = _cv_narrative(
                client_name=c.get("name", ""),
                profile=c.get("profile", "Balanced"),
                is_up=pnl["summary"]["total_pnl"] >= 0 if pnl else True,
                total_pnl_pct=pnl["summary"]["total_pnl_pct"] if pnl else 0.0,
                days_held=pnl["summary"]["days_since_entry"] if pnl else 0,
                n_unique_tickers=pnl["summary"]["n_unique_tickers"] if pnl else 0,
                regime_label=r.get("regime_label") or "Transition",
                score=r.get("composite_score"),
            )

            # Domicile-aware disclaimer.
            from app.data import DISCLAIMERS as _DISCLAIMERS
            domicile_key = (c.get("domicile_country") or "").upper()
            disclaimer = _DISCLAIMERS.get(domicile_key) or _DISCLAIMERS["default"]

    return templates.TemplateResponse("partials/client_review.html", {
        "request": request,
        "clients": clients,
        "selected_client": selected_client,
        "pnl": pnl,
        "history": history,
        "donut_svg": donut_svg,
        "legend": legend,
        "narrative": narrative,
        "disclaimer": disclaimer,
        "as_of_date": as_of_date,
    })


# ── Proposal PDF ─────────────────────────────────────────────────────


def _proposal_inputs_for(request: Request, client_id: str, *, portfolio_value: Optional[float] = None,
                         profile: Optional[str] = None, universe: Optional[str] = None) -> Optional[ProposalInputs]:
    """Common assembly for both /proposal.pdf and /proposal.html endpoints."""
    c = get_client(client_id)
    if not c:
        return None
    user = get_current_user(request) or {}
    ctx = load_context(request)
    profile_use = profile or c.get("profile") or "Balanced"
    universe_use = universe or ctx.universe or "Teroxx Core (9)"
    pv = portfolio_value if portfolio_value is not None else (ctx.portfolio_value or 100_000)
    # Live spot prices for all tickers in the universe — keeps rationale
    # pages from showing stale numbers.
    spot: dict[str, float] = {}
    try:
        from app.market_data import get_price
        from app.engine import get_universe_tickers
        for t in get_universe_tickers(universe_use):
            p = get_price(t)
            if p:
                spot[t] = float(p)
    except Exception:
        spot = {}
    return ProposalInputs(
        client=c,
        profile=profile_use,
        universe=universe_use,
        portfolio_value=float(pv),
        prepared_by=user.get("name") or user.get("email") or "Teroxx Advisory",
        prepared_date=datetime.utcnow().strftime("%d %B %Y"),
        macro_state=get_macro_regime(),
        spot_prices=spot,
    )


@app.get("/api/clients/{client_id}/proposal.pdf")
async def client_proposal_pdf(
    request: Request,
    client_id: str,
    profile: Optional[str] = None,
    universe: Optional[str] = None,
    portfolio_value: Optional[float] = None,
):
    inp = _proposal_inputs_for(request, client_id, profile=profile, universe=universe,
                               portfolio_value=portfolio_value)
    if inp is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ctx = build_proposal_context(inp)
        pdf_bytes = render_proposal_pdf(ctx, html_only=False)
    except Exception as e:
        logger.exception("Proposal PDF render failed for %s: %s", client_id, e)
        return JSONResponse({"error": "render_failed", "detail": str(e)}, status_code=500)
    # Audit log.
    try:
        with SessionLocal() as db:
            log_action(
                db,
                actor_email=_actor_email(request),
                action_type="proposal_generated",
                client_id=client_id,
                payload={"profile": inp.profile, "universe": inp.universe,
                         "portfolio_value": inp.portfolio_value, "size_bytes": len(pdf_bytes)},
            )
            db.commit()
    except Exception as e:
        logger.warning("Audit log for proposal_generated failed: %s", e)
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in inp.client.get("name", client_id))
    filename = f"Teroxx_Proposal_{safe_name}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "private, no-store",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.get("/api/clients/{client_id}/proposal.html", response_class=HTMLResponse)
async def client_proposal_html(
    request: Request,
    client_id: str,
    profile: Optional[str] = None,
    universe: Optional[str] = None,
    portfolio_value: Optional[float] = None,
):
    inp = _proposal_inputs_for(request, client_id, profile=profile, universe=universe,
                               portfolio_value=portfolio_value)
    if inp is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    try:
        ctx = build_proposal_context(inp)
        html = render_proposal_pdf(ctx, html_only=True)
    except Exception as e:
        logger.exception("Proposal HTML render failed for %s: %s", client_id, e)
        return JSONResponse({"error": "render_failed", "detail": str(e)}, status_code=500)
    return HTMLResponse(html)


# ── Client CRUD ──────────────────────────────────────────────────────


def _actor_email(request: Request):
    user = get_current_user(request)
    return user["email"] if user else None


@app.get("/api/clients")
async def list_clients_json(request: Request):
    with SessionLocal() as db:
        return [clients_repo.to_summary_dict(c) for c in clients_repo.list_active_clients(db)]


@app.get("/api/clients/{client_id}")
async def get_client_json(request: Request, client_id: str):
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return clients_repo.to_legacy_dict(c)


@app.post("/api/clients")
async def create_client_endpoint(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict) or not payload.get("name"):
        return JSONResponse({"error": "name_required"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.create_client(
            db,
            actor_email=_actor_email(request),
            name=payload.get("name", ""),
            profile=payload.get("profile", "Balanced"),
            domicile=payload.get("domicile"),
            domicile_country=payload.get("domicile_country"),
            currency=payload.get("currency", "USD"),
            inception_date=payload.get("inception_date"),
            starting_capital_usd=payload.get("starting_capital_usd"),
            tagline=payload.get("tagline"),
            risk_notes=payload.get("risk_notes"),
        )
        db.commit()
        db.refresh(c)
        return clients_repo.to_legacy_dict(c)


@app.patch("/api/clients/{client_id}")
async def update_client_endpoint(request: Request, client_id: str):
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid_body"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        clients_repo.update_client(db, actor_email=_actor_email(request), client=c, fields=payload)
        db.commit()
        db.refresh(c)
        return clients_repo.to_legacy_dict(c)


@app.delete("/api/clients/{client_id}")
async def delete_client_endpoint(request: Request, client_id: str):
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        clients_repo.soft_delete_client(db, actor_email=_actor_email(request), client=c)
        db.commit()
        return {"ok": True}


@app.post("/api/clients/{client_id}/lots")
async def add_lot_endpoint(request: Request, client_id: str):
    payload = await request.json()
    if not isinstance(payload, dict) or not payload.get("ticker"):
        return JSONResponse({"error": "ticker_required"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        lot = clients_repo.add_lot(
            db,
            actor_email=_actor_email(request),
            client=c,
            ticker=payload["ticker"],
            quantity=float(payload.get("quantity", 0) or 0),
            entry_price=float(payload.get("entry_price", 0) or 0),
            entry_date=payload.get("entry_date"),
            notes=payload.get("notes"),
        )
        db.commit()
        return {"id": lot.id, "ticker": lot.ticker, "quantity": lot.quantity, "entry_price": lot.entry_price}


@app.patch("/api/clients/{client_id}/lots/{lot_id}")
async def update_lot_endpoint(request: Request, client_id: str, lot_id: int):
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid_body"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        lot = next((l for l in c.lots if l.id == lot_id), None)
        if not lot:
            return JSONResponse({"error": "lot_not_found"}, status_code=404)
        clients_repo.update_lot(db, actor_email=_actor_email(request), lot=lot, fields=payload)
        db.commit()
        return {"id": lot.id, "ticker": lot.ticker, "quantity": lot.quantity, "entry_price": lot.entry_price}


@app.delete("/api/clients/{client_id}/lots/{lot_id}")
async def delete_lot_endpoint(request: Request, client_id: str, lot_id: int):
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        lot = next((l for l in c.lots if l.id == lot_id), None)
        if not lot:
            return JSONResponse({"error": "lot_not_found"}, status_code=404)
        clients_repo.delete_lot(db, actor_email=_actor_email(request), lot=lot)
        db.commit()
        return {"ok": True}
