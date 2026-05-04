"""
Macro Regime — 22-indicator composite score (0-100) with 5-state classification.

Ported from nickel-ls-rv (free-source variant, no Nansen dependency).
Sources: alternative.me, Yahoo Finance v8 chart API, Binance public fapi,
blockchain.info, CoinGecko /global, CoinMetrics community API. All free, no auth.

The composite is a weighted average of available scores; missing sources cause
weights to renormalize so a degraded fetch does not poison the composite.
Regime states: DEEP_BEAR, LATE_BEAR, TRANSITION, EARLY_BULL, FULL_BULL,
with hysteresis to prevent flipping at thresholds.
"""
from __future__ import annotations

import asyncio
import logging
import math
import statistics
import time
from collections import deque
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Regime + Indicator Definitions ────────────────────────────────────

REGIMES = {
    "deep_bear":  {"label": "Deep Bear",  "range": (0, 20),   "color": "#DC2626"},
    "late_bear":  {"label": "Late Bear",  "range": (20, 35),  "color": "#F97316"},
    "transition": {"label": "Transition", "range": (35, 55),  "color": "#EAB308"},
    "early_bull": {"label": "Early Bull", "range": (55, 75),  "color": "#22C55E"},
    "full_bull":  {"label": "Full Bull",  "range": (75, 100), "color": "#16A34A"},
}

INDICATORS = [
    # Sentiment (20%)
    {"key": "fear_greed",        "label": "Fear & Greed Index",     "category": "sentiment", "weight": 10},
    {"key": "funding_rate",      "label": "Aggregate Funding Rate", "category": "sentiment", "weight": 10},
    # TradFi (25-29%)
    {"key": "vix",               "label": "VIX",                    "category": "tradfi",    "weight": 7},
    {"key": "dxy_vs_sma",        "label": "DXY vs 50d SMA",         "category": "tradfi",    "weight": 6},
    {"key": "treasury_10y",      "label": "10Y Treasury Yield",     "category": "tradfi",    "weight": 5},
    {"key": "spx_vs_sma",        "label": "S&P 500 vs 200d SMA",    "category": "tradfi",    "weight": 7},
    {"key": "move_index",        "label": "MOVE Index",             "category": "tradfi",    "weight": 6},
    {"key": "oil_wti",           "label": "Oil WTI",                "category": "tradfi",    "weight": 5},
    {"key": "yield_curve",       "label": "Yield Curve (3m-10Y)",   "category": "tradfi",    "weight": 5},
    {"key": "treasury_2y",       "label": "2Y Yield Momentum",      "category": "tradfi",    "weight": 6},
    {"key": "equity_rsi_weekly", "label": "Equity RSI (Weekly)",    "category": "tradfi",    "weight": 5},
    {"key": "equity_ppo_daily",  "label": "Equity MACD (Daily PPO)","category": "tradfi",    "weight": 4},
    # On-chain (25%)
    {"key": "btc_dominance",     "label": "BTC Dominance",          "category": "onchain",   "weight": 8},
    {"key": "hash_rate_trend",   "label": "BTC Hash Rate Trend",    "category": "onchain",   "weight": 5},
    {"key": "open_interest_ctx", "label": "Open Interest Context",  "category": "onchain",   "weight": 7},
    {"key": "miner_revenue",     "label": "Miner Revenue Trend",    "category": "onchain",   "weight": 5},
    # Matrix (30%)
    {"key": "btc_trend",         "label": "BTC Trend (EMAs)",       "category": "matrix",    "weight": 10},
    {"key": "altcoin_breadth",   "label": "Altcoin Breadth",        "category": "matrix",    "weight": 8},
    {"key": "cross_correlation", "label": "Cross-Correlation",      "category": "matrix",    "weight": 7},
    {"key": "return_dispersion", "label": "Return Dispersion",      "category": "matrix",    "weight": 5},
    {"key": "btc_rsi_weekly",    "label": "BTC RSI (Weekly)",       "category": "matrix",    "weight": 6},
    {"key": "btc_ppo_daily",     "label": "BTC MACD (Daily PPO)",   "category": "matrix",    "weight": 5},
]


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


# ── Pure scoring functions (ported from nickel-ls-rv) ─────────────────

def score_fear_greed(fg_value: int) -> float:
    if fg_value <= 15:
        s = 65 + (15 - fg_value) * 0.2
    elif fg_value <= 25:
        s = 58 + (25 - fg_value) * 0.7
    elif fg_value <= 45:
        s = 50 + (45 - fg_value) * 0.4
    elif fg_value <= 55:
        s = 45 + (55 - fg_value) * 0.5
    elif fg_value <= 75:
        s = 35 + (75 - fg_value) * 0.5
    else:
        s = 35 - (fg_value - 75) * 0.4
    return _clamp(s)


def score_funding_rate(avg_rate: float) -> float:
    rate_pct = avg_rate * 100
    return _clamp(50 - (rate_pct / 0.05) * 15)


def score_vix(v: float) -> float:
    if v < 15:        s = 75
    elif v < 20:      s = 75 - (v - 15) * 3
    elif v < 30:      s = 60 - (v - 20) * 1.5
    elif v < 40:      s = 45 + (v - 30) * 1.0
    else:             s = 55 + min((v - 40) * 1.0, 10)
    return _clamp(s)


def score_dxy_vs_sma(current: float, sma_50: Optional[float]) -> float:
    if sma_50 is None: return 50.0
    pct = (current / sma_50 - 1) * 100
    return _clamp(50 - pct * 30)


def score_treasury_10y(change_30d_bps: float) -> float:
    return _clamp(50 - change_30d_bps * 0.5, 10, 90)


def score_spx_vs_sma(current: float, sma_200: Optional[float]) -> float:
    if sma_200 is None: return 50.0
    pct = (current / sma_200 - 1) * 100
    if pct >= 0: s = 70 + min(pct * 5, 20)
    else:        s = 30 + max(pct * 5, -20)
    return _clamp(s)


def score_move(v: float) -> float:
    if v < 80:        s = 75
    elif v < 100:     s = 75 - (v - 80) * 1.0
    elif v < 130:     s = 55 - (v - 100) * (20 / 30)
    elif v < 160:     s = 35 - (v - 130) * 0.5
    else:             s = 20
    return _clamp(s)


def score_oil(p: float) -> float:
    if p < 40:        s = 30
    elif p < 60:      s = 30 + (p - 40) * 1.25
    elif p < 80:      s = 55 + (p - 60) * 0.75
    elif p < 100:     s = 70 - (p - 80) * 1.0
    elif p < 120:     s = 50 - (p - 100) * 1.0
    else:             s = 25
    return _clamp(s)


def score_yield_curve(spread_bps: float, change_30d_bps: float) -> float:
    if spread_bps < -100:    level = 20
    elif spread_bps < -50:   level = 20 + (spread_bps + 100) * 0.4
    elif spread_bps < 0:     level = 40 + (spread_bps + 50) * 0.2
    elif spread_bps < 100:   level = 50 + spread_bps * 0.15
    elif spread_bps < 200:   level = 65 + (spread_bps - 100) * 0.1
    else:                    level = 75
    change = 50 + max(-25, min(25, change_30d_bps * 0.3))
    return _clamp(level * 0.6 + change * 0.4)


def score_treasury_2y(change_30d_bps: float) -> float:
    if change_30d_bps <= -30:    s = 75
    elif change_30d_bps <= 0:    s = 50 + (-change_30d_bps / 30) * 25
    elif change_30d_bps <= 20:   s = 50 - (change_30d_bps / 20) * 15
    elif change_30d_bps <= 50:   s = 35 - ((change_30d_bps - 20) / 30) * 20
    else:                        s = 10
    return _clamp(s, 10, 90)


def score_btc_dominance(d: float) -> float:
    if 45 <= d <= 55:   s = 65 + (5 - abs(d - 50)) * 1.5
    elif d < 45:        s = 57 - (45 - d) * 3
    else:               s = 57 - (d - 55) * 5
    return _clamp(s)


def score_hash_rate_trend(c: float) -> float:
    if c > 5:        s = 65 + min(c - 5, 10)
    elif c > 0:      s = 50 + c * 3
    elif c > -10:    s = 50 + c * 1.5
    else:            s = 35 + min(abs(c + 10) * 0.5, 10)
    return _clamp(s)


def score_open_interest_context(oi_change_7d_pct: Optional[float], avg_funding: Optional[float]) -> float:
    if oi_change_7d_pct is None: return 50.0
    rising  = oi_change_7d_pct > 2
    falling = oi_change_7d_pct < -2
    fneg = (avg_funding or 0) < -0.0001
    fpos = (avg_funding or 0) > 0.0001
    if rising and fneg:    s = 60 + min(abs(oi_change_7d_pct) * 1.5, 20)
    elif rising and fpos:  s = 40 - min(oi_change_7d_pct * 1.0, 15)
    else:                  s = 50
    return _clamp(s)


def score_miner_revenue_trend(c: float) -> float:
    if c > 5:        s = 65 + min((c - 5) * 1.5, 20)
    elif c > 0:      s = 50 + c * 3
    elif c > -15:    s = 50 + c * 1.0
    else:            s = 35
    return _clamp(s)


def score_rsi_contrarian(rsi: float) -> float:
    if rsi < 25:     s = 72
    elif rsi < 35:   s = 60 + (35 - rsi) * 1.2
    elif rsi < 50:   s = 52 + (50 - rsi) * (8 / 15)
    elif rsi < 65:   s = 42 + (65 - rsi) * (10 / 15)
    elif rsi < 75:   s = 32 + (75 - rsi) * 1.0
    else:            s = 28
    return _clamp(s)


def score_ppo_momentum(histogram: float, ppo_line: float) -> float:
    h = 50 + histogram * 12.5
    l = 50 + max(-15, min(15, ppo_line * 5))
    return _clamp(h * 0.7 + l * 0.3, 20, 80)


# ── Stdlib stats helpers (no numpy/pandas) ────────────────────────────

def _ewma(values: list[float], span: int) -> list[float]:
    """Exponentially-weighted moving average. span same as pandas .ewm(span=).
    alpha = 2 / (span + 1)."""
    if not values: return []
    alpha = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def _sma(values: list[float], window: int) -> Optional[float]:
    if len(values) < window: return None
    return sum(values[-window:]) / window


def _wilder_rsi(values: list[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1: return None
    gains = []; losses = []
    for i in range(1, len(values)):
        d = values[i] - values[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    # Wilder smoothing: first avg over `period`, then EMA-like update
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def _ppo(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[tuple[float, float]]:
    """PPO (percentage price oscillator). Returns (ppo_line, histogram).
    PPO = (EMA_fast - EMA_slow) / EMA_slow * 100; signal = EMA(PPO, 9); hist = PPO - signal."""
    if len(values) < slow + signal: return None
    ema_fast = _ewma(values, fast)
    ema_slow = _ewma(values, slow)
    ppo_series = [(f - s) / s * 100 for f, s in zip(ema_fast, ema_slow) if s != 0]
    sig_series = _ewma(ppo_series, signal)
    return ppo_series[-1], ppo_series[-1] - sig_series[-1]


# ── Free-source fetchers ──────────────────────────────────────────────

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
ALT_BASE = "https://api.alternative.me"
BINANCE_FAPI = "https://fapi.binance.com"
COINGECKO = "https://api.coingecko.com/api/v3"
BLOCKCHAIN_INFO = "https://api.blockchain.info"
COINMETRICS = "https://community-api.coinmetrics.io/v4"

# Top-20 perp symbols for funding-rate aggregate
_FUNDING_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
    "AVAXUSDT", "LINKUSDT", "DOTUSDT", "MATICUSDT", "UNIUSDT", "AAVEUSDT",
    "TRXUSDT", "LTCUSDT", "BCHUSDT", "ATOMUSDT", "INJUSDT", "SUIUSDT", "TONUSDT",
]

_USER_AGENT = {"User-Agent": "Mozilla/5.0 teroxx-portfolio-app"}


async def _yahoo_chart(client: httpx.AsyncClient, symbol: str, range_: str = "1y", interval: str = "1d") -> Optional[list[float]]:
    """Returns close prices oldest→newest, or None on failure."""
    try:
        r = await client.get(
            f"{YAHOO_BASE}/{symbol}",
            params={"range": range_, "interval": interval},
            headers=_USER_AGENT,
            timeout=15,
        )
        r.raise_for_status()
        result = r.json().get("chart", {}).get("result", [{}])[0]
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        return [c for c in closes if c is not None]
    except Exception as e:
        logger.warning(f"Yahoo {symbol} fetch failed: {e}")
        return None


async def fetch_fear_greed(client: httpx.AsyncClient) -> Optional[int]:
    try:
        r = await client.get(f"{ALT_BASE}/fng/?limit=1", timeout=10)
        r.raise_for_status()
        return int(r.json()["data"][0]["value"])
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed: {e}")
        return None


async def fetch_avg_funding(client: httpx.AsyncClient) -> Optional[float]:
    try:
        r = await client.get(f"{BINANCE_FAPI}/fapi/v1/premiumIndex", timeout=10)
        r.raise_for_status()
        rows = r.json()
        rates = []
        wanted = set(_FUNDING_SYMBOLS)
        for row in rows:
            if row.get("symbol") in wanted:
                try:
                    rates.append(float(row["lastFundingRate"]))
                except (KeyError, ValueError):
                    pass
        if not rates: return None
        return sum(rates) / len(rates)
    except Exception as e:
        logger.warning(f"Funding rate fetch failed: {e}")
        return None


async def fetch_btc_dominance(client: httpx.AsyncClient) -> Optional[float]:
    try:
        r = await client.get(f"{COINGECKO}/global", timeout=10)
        r.raise_for_status()
        return float(r.json()["data"]["market_cap_percentage"]["btc"])
    except Exception as e:
        logger.warning(f"BTC dominance fetch failed: {e}")
        return None


async def fetch_hash_rate_change_30d(client: httpx.AsyncClient) -> Optional[float]:
    try:
        r = await client.get(
            f"{BLOCKCHAIN_INFO}/charts/hash-rate",
            params={"timespan": "60days", "format": "json"},
            timeout=15,
        )
        r.raise_for_status()
        vals = [pt["y"] for pt in r.json().get("values", []) if pt.get("y", 0) > 0]
        if len(vals) < 30: return None
        last = sum(vals[-7:]) / 7
        prior = sum(vals[-37:-30]) / 7
        return (last / prior - 1) * 100 if prior > 0 else None
    except Exception as e:
        logger.warning(f"Hash rate fetch failed: {e}")
        return None


async def fetch_miner_revenue_change_30d(client: httpx.AsyncClient) -> Optional[float]:
    try:
        r = await client.get(
            f"{BLOCKCHAIN_INFO}/charts/miners-revenue",
            params={"timespan": "60days", "format": "json"},
            timeout=15,
        )
        r.raise_for_status()
        vals = [pt["y"] for pt in r.json().get("values", []) if pt.get("y", 0) > 0]
        if len(vals) < 30: return None
        last = sum(vals[-7:]) / 7
        prior = sum(vals[-37:-30]) / 7
        return (last / prior - 1) * 100 if prior > 0 else None
    except Exception as e:
        logger.warning(f"Miner revenue fetch failed: {e}")
        return None


async def fetch_open_interest_change_7d(client: httpx.AsyncClient) -> Optional[float]:
    try:
        r = await client.get(
            f"{BINANCE_FAPI}/futures/data/openInterestHist",
            params={"symbol": "BTCUSDT", "period": "1d", "limit": 8},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        if len(rows) < 8: return None
        first = float(rows[0]["sumOpenInterestValue"])
        last = float(rows[-1]["sumOpenInterestValue"])
        return (last / first - 1) * 100 if first > 0 else None
    except Exception as e:
        logger.warning(f"OI fetch failed: {e}")
        return None


async def fetch_btc_daily_closes(client: httpx.AsyncClient, days: int = 400) -> Optional[list[float]]:
    """Daily BTC closes from CryptoCompare — needed for matrix indicators."""
    try:
        r = await client.get(
            "https://min-api.cryptocompare.com/data/v2/histoday",
            params={"fsym": "BTC", "tsym": "USD", "limit": str(days)},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("Data", {}).get("Data", [])
        return [float(e["close"]) for e in data if e.get("close", 0) > 0]
    except Exception as e:
        logger.warning(f"BTC daily closes fetch failed: {e}")
        return None


async def fetch_btc_weekly_closes(client: httpx.AsyncClient, weeks: int = 250) -> Optional[list[float]]:
    """Weekly BTC closes — for 200 WMA and weekly RSI."""
    try:
        r = await client.get(
            "https://min-api.cryptocompare.com/data/v2/histoday",
            params={"fsym": "BTC", "tsym": "USD", "limit": str(weeks * 7), "aggregate": "7"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("Data", {}).get("Data", [])
        return [float(e["close"]) for e in data if e.get("close", 0) > 0]
    except Exception as e:
        logger.warning(f"BTC weekly closes fetch failed: {e}")
        return None


async def fetch_mvrv_z_score(client: httpx.AsyncClient) -> Optional[float]:
    """CoinMetrics community API: CapMVRVCur (MVRV ratio) — derive Z-score
    from the rolling 4-year mean/std of the MVRV time series."""
    try:
        r = await client.get(
            f"{COINMETRICS}/timeseries/asset-metrics",
            params={"assets": "btc", "metrics": "CapMVRVCur",
                    "frequency": "1d", "page_size": "10000",
                    "start_time": "2018-01-01"},
            timeout=20,
        )
        r.raise_for_status()
        rows = r.json().get("data", [])
        vals = [float(row["CapMVRVCur"]) for row in rows if row.get("CapMVRVCur") is not None]
        if len(vals) < 365 * 2: return None
        # Z-score over the last ~4y window
        window = vals[-365 * 4:] if len(vals) >= 365 * 4 else vals
        mean = sum(window) / len(window)
        var = sum((v - mean) ** 2 for v in window) / len(window)
        std = math.sqrt(var) if var > 0 else 1.0
        return (vals[-1] - mean) / std
    except Exception as e:
        logger.warning(f"MVRV Z-score fetch failed: {e}")
        return None


async def fetch_mvrv_ratio(client: httpx.AsyncClient) -> Optional[float]:
    """Latest MVRV ratio (raw, not Z-score) — for cycle zone classification."""
    try:
        r = await client.get(
            f"{COINMETRICS}/timeseries/asset-metrics",
            params={"assets": "btc", "metrics": "CapMVRVCur",
                    "frequency": "1d", "page_size": "1"},
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json().get("data", [])
        if not rows or rows[-1].get("CapMVRVCur") is None: return None
        return float(rows[-1]["CapMVRVCur"])
    except Exception as e:
        logger.warning(f"MVRV ratio fetch failed: {e}")
        return None


# ── Top-level fetch + score ──────────────────────────────────────────

async def fetch_macro_inputs() -> dict:
    """Concurrently fetch every input the scoring functions need."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            fetch_fear_greed(client),
            fetch_avg_funding(client),
            fetch_btc_dominance(client),
            fetch_hash_rate_change_30d(client),
            fetch_miner_revenue_change_30d(client),
            fetch_open_interest_change_7d(client),
            _yahoo_chart(client, "%5EVIX", "3mo"),       # VIX
            _yahoo_chart(client, "DX-Y.NYB", "1y"),      # DXY
            _yahoo_chart(client, "%5ETNX", "3mo"),       # 10Y yield (×10 for percent)
            _yahoo_chart(client, "%5EGSPC", "1y"),       # SPX
            _yahoo_chart(client, "%5EMOVE", "1mo"),      # MOVE
            _yahoo_chart(client, "CL=F", "1mo"),         # WTI oil
            _yahoo_chart(client, "%5EIRX", "3mo"),       # 13-week T-bill (×10)
            _yahoo_chart(client, "%5EFVX", "3mo"),       # 5Y yield (proxy for 2Y momentum)
            _yahoo_chart(client, "%5ENDX", "1y"),        # NDX (with SPX → equity composite)
            fetch_btc_daily_closes(client, 400),
            fetch_btc_weekly_closes(client, 220),
            fetch_mvrv_ratio(client),
            fetch_mvrv_z_score(client),
            return_exceptions=False,
        )
    keys = [
        "fear_greed", "avg_funding", "btc_dominance",
        "hash_rate_change_30d", "miner_revenue_change_30d", "oi_change_7d",
        "vix_closes", "dxy_closes", "tnx_closes", "spx_closes",
        "move_closes", "oil_closes", "irx_closes", "fvx_closes", "ndx_closes",
        "btc_daily", "btc_weekly", "mvrv_ratio", "mvrv_z",
    ]
    return dict(zip(keys, results))


def score_all(inputs: dict, prev_regime: Optional[str] = None) -> dict:
    """Compute every score from the raw inputs, then composite + regime."""
    scores: dict[str, Optional[float]] = {}
    raw: dict[str, Any] = {}

    # Sentiment
    fg = inputs.get("fear_greed")
    if fg is not None:
        scores["fear_greed"] = score_fear_greed(fg); raw["fear_greed"] = fg
    funding = inputs.get("avg_funding")
    if funding is not None:
        scores["funding_rate"] = score_funding_rate(funding)
        raw["funding_rate"] = round(funding, 6)

    # TradFi — VIX
    vix = inputs.get("vix_closes")
    if vix:
        scores["vix"] = score_vix(vix[-1]); raw["vix"] = vix[-1]
    # DXY vs 50d SMA
    dxy = inputs.get("dxy_closes")
    if dxy and len(dxy) >= 50:
        scores["dxy_vs_sma"] = score_dxy_vs_sma(dxy[-1], _sma(dxy, 50)); raw["dxy_vs_sma"] = dxy[-1]
    # 10Y Treasury — Yahoo ^TNX is yield × 10
    tnx = inputs.get("tnx_closes")
    if tnx and len(tnx) >= 31:
        change_bps = (tnx[-1] - tnx[-31]) * 10  # ×10 yield → bps
        scores["treasury_10y"] = score_treasury_10y(change_bps)
        raw["treasury_10y"] = round(tnx[-1] / 10, 2)  # show as %
    # SPX vs 200d SMA
    spx = inputs.get("spx_closes")
    if spx and len(spx) >= 200:
        scores["spx_vs_sma"] = score_spx_vs_sma(spx[-1], _sma(spx, 200)); raw["spx_vs_sma"] = round(spx[-1], 2)
    # MOVE
    move = inputs.get("move_closes")
    if move:
        scores["move_index"] = score_move(move[-1]); raw["move_index"] = round(move[-1], 2)
    # Oil
    oil = inputs.get("oil_closes")
    if oil:
        scores["oil_wti"] = score_oil(oil[-1]); raw["oil_wti"] = round(oil[-1], 2)
    # Yield curve (3m-10Y) via ^IRX (3m T-bill ×10) and ^TNX (10Y ×10)
    irx = inputs.get("irx_closes")
    if irx and tnx and len(irx) >= 31 and len(tnx) >= 31:
        spread_now = (tnx[-1] - irx[-1]) * 10           # bps
        spread_30d = (tnx[-31] - irx[-31]) * 10
        scores["yield_curve"] = score_yield_curve(spread_now, spread_now - spread_30d)
        raw["yield_curve"] = round(spread_now, 1)
    # 2Y momentum proxy — using ^FVX (5Y) since Yahoo doesn't expose 2Y cleanly
    fvx = inputs.get("fvx_closes")
    if fvx and len(fvx) >= 31:
        change_bps = (fvx[-1] - fvx[-31]) * 10
        scores["treasury_2y"] = score_treasury_2y(change_bps)
        # No clean raw value — leave None for the table
    # Equity weekly RSI (avg SPX + NDX) + daily PPO
    ndx = inputs.get("ndx_closes")
    if spx and ndx and len(spx) >= 100 and len(ndx) >= 100:
        # weekly = take every 5th day's close
        spx_w = spx[::-1][::5][::-1]
        ndx_w = ndx[::-1][::5][::-1]
        rsi_spx = _wilder_rsi(spx_w[-30:], 14)
        rsi_ndx = _wilder_rsi(ndx_w[-30:], 14)
        if rsi_spx is not None and rsi_ndx is not None:
            scores["equity_rsi_weekly"] = score_rsi_contrarian((rsi_spx + rsi_ndx) / 2)
            raw["equity_rsi_weekly"] = round((rsi_spx + rsi_ndx) / 2, 1)
        ppo_spx = _ppo(spx)
        ppo_ndx = _ppo(ndx)
        if ppo_spx and ppo_ndx:
            ppo_line = (ppo_spx[0] + ppo_ndx[0]) / 2
            hist = (ppo_spx[1] + ppo_ndx[1]) / 2
            scores["equity_ppo_daily"] = score_ppo_momentum(hist, ppo_line)
            raw["equity_ppo_daily"] = round(ppo_line, 4)

    # On-chain
    dom = inputs.get("btc_dominance")
    if dom is not None:
        scores["btc_dominance"] = score_btc_dominance(dom); raw["btc_dominance"] = round(dom, 2)
    hash_chg = inputs.get("hash_rate_change_30d")
    if hash_chg is not None:
        scores["hash_rate_trend"] = score_hash_rate_trend(hash_chg); raw["hash_rate_trend"] = round(hash_chg, 2)
    oi_chg = inputs.get("oi_change_7d")
    if oi_chg is not None:
        scores["open_interest_ctx"] = score_open_interest_context(oi_chg, funding)
        raw["open_interest_ctx"] = round(oi_chg, 2)
    miner = inputs.get("miner_revenue_change_30d")
    if miner is not None:
        scores["miner_revenue"] = score_miner_revenue_trend(miner); raw["miner_revenue"] = round(miner, 2)

    # Matrix — derived from BTC daily/weekly
    btc_d = inputs.get("btc_daily")
    if btc_d and len(btc_d) >= 200:
        # BTC trend: price vs EMA(168/24=7) and EMA(720/24=30) on daily — adapt to daily
        ema_short = _ewma(btc_d, 7)
        ema_long  = _ewma(btc_d, 30)
        price = btc_d[-1]
        above_s = price > ema_short[-1]
        above_l = price > ema_long[-1]
        slope = (ema_short[-1] - ema_short[-7]) / ema_short[-7] * 100 if len(ema_short) >= 7 else 0
        if above_s and above_l:       s = 70 + min(slope * 5, 15)
        elif above_s and not above_l: s = 55 + min(slope * 3, 10)
        elif not above_s and above_l: s = 35 + max(slope * 3, -10)
        else:                         s = 20 + max(slope * 2, -10)
        scores["btc_trend"] = _clamp(s)
        raw["btc_trend"] = round(price, 2)
        # Daily PPO on BTC
        ppo_btc = _ppo(btc_d)
        if ppo_btc:
            scores["btc_ppo_daily"] = score_ppo_momentum(ppo_btc[1], ppo_btc[0])
            raw["btc_ppo_daily"] = round(ppo_btc[0], 4)

    btc_w = inputs.get("btc_weekly")
    if btc_w and len(btc_w) >= 30:
        rsi_w = _wilder_rsi(btc_w[-50:], 14)
        if rsi_w is not None:
            scores["btc_rsi_weekly"] = score_rsi_contrarian(rsi_w)
            raw["btc_rsi_weekly"] = round(rsi_w, 2)

    # Cross-correlation + return dispersion + altcoin breadth need a market matrix.
    # We don't keep an hourly multi-token matrix; leave them None so weights renormalize.
    # (Future: derive from the existing CryptoCompare daily history we already cache.)

    composite, n_avail, n_total = compute_composite(scores)
    regime = classify_regime(composite, prev_regime)
    return {
        "composite_score": composite,
        "regime": regime,
        "regime_label": REGIMES[regime]["label"],
        "regime_color": REGIMES[regime]["color"],
        "regime_range": REGIMES[regime]["range"],
        "sources_available": n_avail,
        "sources_total": n_total,
        "scores": scores,
        "raw": raw,
        "indicators": INDICATORS,
        "regimes": REGIMES,
    }


def compute_composite(scores: dict[str, Optional[float]]) -> tuple[float, int, int]:
    by_key = {ind["key"]: ind for ind in INDICATORS}
    total_w = 0.0; weighted_sum = 0.0; available = 0
    for k, s in scores.items():
        if s is None or k not in by_key: continue
        w = by_key[k]["weight"]
        weighted_sum += s * w; total_w += w; available += 1
    if total_w == 0: return 50.0, 0, len(INDICATORS)
    return round(weighted_sum / total_w, 1), available, len(INDICATORS)


def classify_regime(score: float, prev: Optional[str] = None) -> str:
    if score <= 20:    raw = "deep_bear"
    elif score <= 35:  raw = "late_bear"
    elif score <= 55:  raw = "transition"
    elif score <= 75:  raw = "early_bull"
    else:              raw = "full_bull"
    if prev is None: return raw

    if prev == "deep_bear":  return raw if score >= 25 else "deep_bear"
    if prev == "full_bull":  return raw if score < 70 else "full_bull"

    order = ["deep_bear", "late_bear", "transition", "early_bull", "full_bull"]
    pi = order.index(prev); ri = order.index(raw)
    boundaries = {
        ("late_bear",  "deep_bear"):  15,
        ("late_bear",  "transition"): 40,
        ("transition", "late_bear"):  30,
        ("transition", "early_bull"): 60,
        ("early_bull", "transition"): 50,
        ("early_bull", "full_bull"):  80,
    }
    if (prev, raw) in boundaries:
        thr = boundaries[(prev, raw)]
        if ri > pi and score < thr: return prev
        if ri < pi and score > thr: return prev
    return raw


# ── Cycle zone thresholds & classification ─────────────────────────────

CYCLE_ZONES = {
    "mvrv": [
        (0.8,  "Deep Value",      "#16A34A"),
        (1.2,  "Fair Value",      "#22C55E"),
        (2.4,  "Neutral",         "#EAB308"),
        (3.6,  "Overheated",      "#F97316"),
        (999,  "Euphoria",        "#DC2626"),
    ],
    "wma200_ratio": [
        (0.8,  "Deep Value",      "#16A34A"),
        (1.2,  "Fair Value",      "#22C55E"),
        (2.0,  "Neutral",         "#EAB308"),
        (3.0,  "Overheated",      "#F97316"),
        (999,  "Euphoria",        "#DC2626"),
    ],
    "mayer_multiple": [
        (0.6,  "Deep Value",      "#16A34A"),
        (0.8,  "Fair Value",      "#22C55E"),
        (1.4,  "Neutral",         "#EAB308"),
        (2.4,  "Overheated",      "#F97316"),
        (999,  "Euphoria",        "#DC2626"),
    ],
    "drawdown_pct": [
        (-75,  "Deep Value",      "#16A34A"),
        (-60,  "Fair Value",      "#22C55E"),
        (-30,  "Neutral",         "#EAB308"),
        (-10,  "Mild Correction", "#F97316"),
        (0,    "Near ATH",        "#DC2626"),
    ],
}


def classify_cycle_zone(metric: str, value: Optional[float]) -> dict:
    if value is None: return {"label": "—", "color": "#6B7280"}
    for threshold, label, color in CYCLE_ZONES.get(metric, []):
        if value <= threshold:
            return {"label": label, "color": color}
    return {"label": "—", "color": "#6B7280"}


def compute_btc_cycle(inputs: dict) -> dict:
    """BTC price / ATH / drawdown / 200WMA / 200SMA / Mayer / MVRV from inputs."""
    btc_d = inputs.get("btc_daily") or []
    btc_w = inputs.get("btc_weekly") or []
    out: dict[str, Any] = {
        "btc_price": None, "ath_peak": None, "from_peak_pct": None,
        "drawdown_zone": None, "wma200": None, "sma200": None,
        "wma200_ratio": None, "mayer_multiple": None, "mvrv": None,
        "mvrv_zone": None, "wma200_ratio_zone": None, "mayer_zone": None,
    }
    if btc_d:
        price = btc_d[-1]
        ath = max(btc_d)
        dd_pct = (price / ath - 1) * 100
        sma200 = _sma(btc_d, 200)
        out["btc_price"] = round(price, 2)
        out["ath_peak"] = round(ath, 2)
        out["from_peak_pct"] = round(dd_pct, 2)
        out["drawdown_zone"] = classify_cycle_zone("drawdown_pct", dd_pct)
        if sma200:
            out["sma200"] = round(sma200, 2)
            mayer = price / sma200
            out["mayer_multiple"] = round(mayer, 3)
            out["mayer_zone"] = classify_cycle_zone("mayer_multiple", mayer)
    if btc_w and len(btc_w) >= 200:
        wma200 = _sma(btc_w, 200)
        if wma200 and out["btc_price"]:
            out["wma200"] = round(wma200, 2)
            ratio = out["btc_price"] / wma200
            out["wma200_ratio"] = round(ratio, 3)
            out["wma200_ratio_zone"] = classify_cycle_zone("wma200_ratio", ratio)
    mvrv = inputs.get("mvrv_ratio")
    if mvrv is not None:
        out["mvrv"] = round(mvrv, 3)
        out["mvrv_zone"] = classify_cycle_zone("mvrv", mvrv)
    out["mvrv_z"] = round(inputs["mvrv_z"], 2) if inputs.get("mvrv_z") is not None else None
    return out


# ── Module-level cache + 30d composite history ────────────────────────

_cache: dict = {"ts": 0, "result": None, "cycle": None, "regime": None}
_history: deque = deque(maxlen=30 * 24)  # one entry per refresh, ~30d at hourly cadence
MACRO_TTL = 1800  # 30 min


async def refresh_macro_regime() -> dict:
    """Refresh inputs + recompute scores; persist to cache + history."""
    inputs = await fetch_macro_inputs()
    result = score_all(inputs, prev_regime=_cache.get("regime"))
    cycle = compute_btc_cycle(inputs)
    now = time.time()
    _cache["ts"] = now
    _cache["result"] = result
    _cache["cycle"] = cycle
    _cache["regime"] = result["regime"]
    _history.append({"ts": now, "score": result["composite_score"], "regime": result["regime"]})
    return result


def get_macro_regime() -> dict:
    """Return the last cached snapshot + cycle + history. Returns empty defaults
    if not yet refreshed."""
    return {
        "result": _cache.get("result"),
        "cycle": _cache.get("cycle"),
        "history": list(_history),
        "ts": _cache.get("ts", 0),
        "indicators": INDICATORS,
        "regimes": REGIMES,
        "cycle_zones": CYCLE_ZONES,
    }
