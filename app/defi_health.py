"""
DeFi macro health score from DeFiLlama free APIs.

Composite 0-100 score from 5 sub-signals (7d growth):
  1. Total DeFi TVL
  2. Aggregate fees
  3. DEX volume
  4. Stablecoin supply
  5. Aggregate lending borrows

Regime: DEFI_CONTRACTION / DEFI_COOLING / DEFI_NEUTRAL / DEFI_EXPANDING / DEFI_BOOM
Ported from nickel-ls-rv/data/defi_health.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0

# Sub-signal weights (sum to 1.0)
WEIGHTS = {
    "tvl": 0.25,
    "fees": 0.25,
    "dex_volume": 0.20,
    "stablecoin_supply": 0.15,
    "borrowed": 0.15,
}

# What % 7d growth = max score (50 pts above neutral)
NORMALIZATION = {
    "tvl": 5.0,
    "fees": 20.0,
    "dex_volume": 30.0,
    "stablecoin_supply": 2.0,
    "borrowed": 10.0,
}

LENDING_PROTOCOLS = ["aave", "compound-v3", "morpho", "sky-lending", "euler"]

# Regime thresholds
_REGIMES = [
    (0, 30, "DEFI_CONTRACTION", None, 35),
    (30, 45, "DEFI_COOLING", 25, 50),
    (45, 55, "DEFI_NEUTRAL", 40, 60),
    (55, 70, "DEFI_EXPANDING", 50, 75),
    (70, 100, "DEFI_BOOM", 65, None),
]

# Cache
DEFI_HEALTH_TTL = 7200  # 2 hours
_defi_health_cache: Optional[dict] = None
_defi_health_ts: float = 0
_prev_regime: Optional[str] = None


def get_defi_health() -> Optional[dict]:
    """Get cached DeFi health score."""
    return _defi_health_cache


# ── Fetchers ──────────────────────────────────────────────────────────────

async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    """Fetch JSON with basic error handling."""
    try:
        resp = await client.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"DeFi health fetch failed: {url[:60]}... {e}")
        return None


async def _fetch_total_tvl(client: httpx.AsyncClient) -> list[tuple[str, float]]:
    data = await _fetch_json(client, "https://api.llama.fi/v2/historicalChainTvl")
    if not data:
        return []
    result = []
    for entry in data[-31:]:
        date_str = datetime.fromtimestamp(entry["date"], tz=timezone.utc).strftime("%Y-%m-%d")
        result.append((date_str, float(entry["tvl"])))
    return result


async def _fetch_aggregate_fees(client: httpx.AsyncClient) -> list[tuple[str, float]]:
    data = await _fetch_json(
        client, "https://api.llama.fi/overview/fees?excludeTotalDataChartBreakdown=true"
    )
    if not data:
        return []
    chart = data.get("totalDataChart", [])
    result = []
    for entry in chart[-31:]:
        date_str = datetime.fromtimestamp(entry[0], tz=timezone.utc).strftime("%Y-%m-%d")
        result.append((date_str, float(entry[1])))
    return result


async def _fetch_dex_volume(client: httpx.AsyncClient) -> list[tuple[str, float]]:
    data = await _fetch_json(
        client, "https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true"
    )
    if not data:
        return []
    chart = data.get("totalDataChart", [])
    result = []
    for entry in chart[-31:]:
        date_str = datetime.fromtimestamp(entry[0], tz=timezone.utc).strftime("%Y-%m-%d")
        result.append((date_str, float(entry[1])))
    return result


async def _fetch_stablecoin_supply(client: httpx.AsyncClient) -> list[tuple[str, float]]:
    data = await _fetch_json(client, "https://stablecoins.llama.fi/stablecoincharts/all")
    if not data:
        return []
    result = []
    for entry in data[-31:]:
        date_str = datetime.fromtimestamp(int(entry["date"]), tz=timezone.utc).strftime("%Y-%m-%d")
        total = float(entry.get("totalCirculatingUSD", {}).get("peggedUSD", 0))
        if total > 0:
            result.append((date_str, total))
    return result


async def _fetch_aggregate_borrowed(client: httpx.AsyncClient) -> list[tuple[str, float]]:
    merged: dict[str, float] = {}
    for slug in LENDING_PROTOCOLS:
        data = await _fetch_json(client, f"https://api.llama.fi/protocol/{slug}")
        if not data:
            continue
        borrows = data.get("chainTvls", {}).get("borrowed", {}).get("tvl", [])
        for entry in borrows[-31:]:
            date_str = datetime.fromtimestamp(entry["date"], tz=timezone.utc).strftime("%Y-%m-%d")
            merged[date_str] = merged.get(date_str, 0) + float(entry.get("totalLiquidityUSD", 0))
        await asyncio.sleep(0.3)  # rate limit courtesy
    return sorted(merged.items())


# ── Computation ───────────────────────────────────────────────────────────

def _compute_sub_signal(values: list[tuple[str, float]], normalization: float) -> tuple[float, float]:
    """7d growth score: 50 = neutral, 0-100 scale."""
    if len(values) < 14:
        return 50.0, 0.0

    last_7 = [v for _, v in values[-7:]]
    prev_7 = [v for _, v in values[-14:-7]]

    avg_last = sum(last_7) / len(last_7)
    avg_prev = sum(prev_7) / len(prev_7)

    if avg_prev <= 0:
        return 50.0, 0.0

    growth_pct = (avg_last - avg_prev) / avg_prev * 100.0
    raw = growth_pct / normalization * 50.0
    clamped = max(-50.0, min(50.0, raw))
    return round(50.0 + clamped, 2), round(growth_pct, 4)


def _classify_regime(score: float, prev_regime: Optional[str] = None) -> str:
    """Classify with 5-point hysteresis."""
    if prev_regime:
        for lower, upper, name, exit_down, exit_up in _REGIMES:
            if name != prev_regime:
                continue
            still_in = True
            if exit_down is not None and score < exit_down:
                still_in = False
            if exit_up is not None and score > exit_up:
                still_in = False
            if still_in:
                return prev_regime
            break

    if score <= 30:
        return "DEFI_CONTRACTION"
    elif score <= 45:
        return "DEFI_COOLING"
    elif score <= 55:
        return "DEFI_NEUTRAL"
    elif score <= 70:
        return "DEFI_EXPANDING"
    else:
        return "DEFI_BOOM"


# ── Main refresh ──────────────────────────────────────────────────────────

async def refresh_defi_health():
    """Fetch all 5 sources and compute composite score. Updates cache."""
    global _defi_health_cache, _defi_health_ts, _prev_regime

    if time.time() - _defi_health_ts < DEFI_HEALTH_TTL:
        return

    logger.info("DeFi health: refreshing...")

    async with httpx.AsyncClient() as client:
        fetchers = {
            "tvl": _fetch_total_tvl(client),
            "fees": _fetch_aggregate_fees(client),
            "dex_volume": _fetch_dex_volume(client),
            "stablecoin_supply": _fetch_stablecoin_supply(client),
            "borrowed": _fetch_aggregate_borrowed(client),
        }

        results = {}
        for name, coro in fetchers.items():
            try:
                values = await coro
                if values and len(values) >= 14:
                    results[name] = values
            except Exception as e:
                logger.warning(f"DeFi health {name} failed: {e}")

    if not results:
        logger.warning("DeFi health: no data fetched")
        return

    sub_signals = {}
    weighted_sum = 0.0
    total_weight = 0.0

    for name, weight in WEIGHTS.items():
        values = results.get(name)
        if not values:
            continue
        score, growth_pct = _compute_sub_signal(values, NORMALIZATION[name])
        sub_signals[name] = {
            "score": score,
            "growth_7d_pct": growth_pct,
            "current": values[-1][1],
        }
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return

    composite = round(weighted_sum / total_weight, 2)
    regime = _classify_regime(composite, _prev_regime)
    _prev_regime = regime

    _defi_health_cache = {
        "composite_score": composite,
        "regime": regime,
        "regime_label": regime.replace("DEFI_", "").replace("_", " ").title(),
        "sub_signals": sub_signals,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    _defi_health_ts = time.time()

    logger.info(
        f"DeFi health: composite={composite:.1f} regime={regime} "
        f"({len(sub_signals)}/{len(WEIGHTS)} signals)"
    )
