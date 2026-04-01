"""
Market data client — CoinMarketCap primary, CoinGecko fallback.
In-memory TTL cache, retry with exponential backoff.
"""
from __future__ import annotations

import asyncio
import os
import time
import logging
from typing import Optional

import httpx

from app.data import TOKEN_MAP, ASSET_UNIVERSE, DEFILLAMA_MAP, DEFILLAMA_FEES_MAP, DEFILLAMA_TVL_MAP, MESSARI_NETWORK_MAP

logger = logging.getLogger(__name__)

# ── API Configuration ──────────────────────────────────────────────────
CMC_BASE = "https://pro-api.coinmarketcap.com"
CMC_API_KEY = os.getenv("CMC_API_KEY", "92086fab50534fe78d552e3a86dfb0d7")
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE = "https://api.llama.fi"
BINANCE_FAPI = "https://fapi.binance.com/fapi/v1"

PRICE_TTL = 300        # 5 minutes
MARKET_DATA_TTL = 3600 # 1 hour
DEFILLAMA_TTL = 7200   # 2 hours
BINANCE_TTL = 300      # 5 minutes

_price_cache: dict[str, float] = {}
_price_ts: float = 0
_market_cache: dict[str, dict] = {}
_market_ts: float = 0
_defillama_cache: dict[str, dict] = {}
_defillama_ts: float = 0
_binance_cache: dict[str, dict] = {}
_binance_ts: float = 0
_supply_history: dict[str, list[tuple[float, float]]] = {}  # {cg_id: [(ts, supply), ...]}
_coingecko_dev_cache: dict[str, dict] = {}
_coingecko_dev_ts: float = 0
COINGECKO_DEV_TTL = 86400  # 24 hours

MESSARI_BASE = "https://api.messari.io"
MESSARI_TTL = 3600  # 1 hour
_messari_cache: dict[str, dict] = {}
_messari_ts: float = 0
_defillama_protocol_cache: dict[str, dict] = {}
_defillama_protocol_ts: float = 0

# ── Data Source Health Tracking ──
_source_health: dict[str, dict] = {
    "cmc": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
    "coingecko": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
    "defillama": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
    "defillama_protocol": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
    "binance": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
    "coingecko_dev": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
    "messari": {"last_ok": 0, "last_fail": 0, "consecutive_fails": 0},
}


def _mark_source_ok(source: str):
    _source_health[source]["last_ok"] = time.time()
    _source_health[source]["consecutive_fails"] = 0


def _mark_source_fail(source: str):
    _source_health[source]["last_fail"] = time.time()
    _source_health[source]["consecutive_fails"] += 1


def get_source_health() -> dict[str, dict]:
    """Get health status for all data sources."""
    now = time.time()
    ttls = {
        "cmc": PRICE_TTL, "coingecko": PRICE_TTL, "defillama": DEFILLAMA_TTL,
        "defillama_protocol": DEFILLAMA_TTL, "binance": BINANCE_TTL,
        "coingecko_dev": COINGECKO_DEV_TTL, "messari": MESSARI_TTL,
    }
    result = {}
    for source, health in _source_health.items():
        ttl = ttls.get(source, 300)
        last_ok = health["last_ok"]
        age = now - last_ok if last_ok > 0 else float("inf")
        if last_ok == 0:
            status = "unknown"
        elif age <= ttl * 2:
            status = "ok"
        elif age <= ttl * 5:
            status = "stale"
        else:
            status = "down"
        result[source] = {
            "status": status,
            "age_seconds": round(age) if last_ok > 0 else None,
            "consecutive_fails": health["consecutive_fails"],
        }
    return result

# Reverse map: CoinGecko ID → ticker (for cache lookups)
_CGID_TO_TICKER = {v: k for k, v in TOKEN_MAP.items() if v}

# CMC symbol overrides where our ticker differs from CMC
CMC_SYMBOL_OVERRIDES = {
    "ASTER": "ASTR",   # Aster on CMC is ASTR
    "RNDR": "RENDER",  # Render rebranded ticker on CMC
}


def _coingecko_ids() -> list[str]:
    return [cg_id for cg_id in TOKEN_MAP.values() if cg_id]


# ── Retry helper ─────────────────────────────────────────────────────────

async def _fetch_with_retry(client, method, url, max_retries=3, **kwargs):
    """Fetch with exponential backoff on 429/5xx errors."""
    for attempt in range(max_retries):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5
                logger.warning(f"Rate limited (429), retry in {wait}s: {url[:80]}")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                logger.warning(f"Rate limited (429), retry in {wait}s")
                await asyncio.sleep(wait)
                continue
            raise
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt * 3
                logger.warning(f"Connection error, retry in {wait}s: {e}")
                await asyncio.sleep(wait)
                continue
            raise
    return None


# ── CoinMarketCap — Primary Source ─────────────────────────────────────

async def _fetch_cmc_quotes() -> tuple[dict[str, float], dict[str, dict]]:
    """
    Fetch prices + full market data from CMC in a single call.
    Returns (prices_by_cgid, market_data_by_cgid).
    """
    if not CMC_API_KEY:
        return {}, {}

    # Build symbol list, applying overrides
    symbols = []
    ticker_to_cmc_symbol = {}
    for ticker in TOKEN_MAP.keys():
        cmc_sym = CMC_SYMBOL_OVERRIDES.get(ticker, ticker)
        symbols.append(cmc_sym)
        ticker_to_cmc_symbol[cmc_sym.upper()] = ticker

    prices: dict[str, float] = {}
    market: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        # Batch into chunks of 40 symbols (CMC free tier drops symbols on large calls)
        chunk_size = 40
        for i in range(0, len(symbols), chunk_size):
            chunk = symbols[i:i + chunk_size]
            try:
                resp = await _fetch_with_retry(
                    client, "GET",
                    f"{CMC_BASE}/v2/cryptocurrency/quotes/latest",
                    params={
                        "symbol": ",".join(chunk),
                        "convert": "USD",
                        "aux": "cmc_rank,circulating_supply,total_supply,max_supply",
                    },
                    headers={"X-CMC_PRO_API_KEY": CMC_API_KEY},
                )
                if not resp:
                    continue

                data = resp.json().get("data", {})

                for cmc_symbol, entries in data.items():
                    # v2 returns list per symbol (multiple coins can share a symbol)
                    coin_list = entries if isinstance(entries, list) else [entries]
                    if not coin_list:
                        continue
                    # Pick the highest-mcap entry
                    coin = max(coin_list, key=lambda c: (c.get("quote", {}).get("USD", {}).get("market_cap") or 0))

                    # Map back to our ticker
                    ticker = ticker_to_cmc_symbol.get(cmc_symbol.upper())
                    if not ticker:
                        continue
                    cg_id = TOKEN_MAP.get(ticker)
                    if not cg_id:
                        continue

                    quote = coin.get("quote", {}).get("USD", {})
                    usd_price = quote.get("price")
                    if usd_price is not None:
                        prices[cg_id] = usd_price

                    mc = quote.get("market_cap") or 0
                    fdv = quote.get("fully_diluted_market_cap") or 0
                    circ_supply = coin.get("circulating_supply") or 0
                    vol = quote.get("volume_24h") or 0

                    market[cg_id] = {
                        "market_cap": mc,
                        "total_volume": vol,
                        "price_change_24h": quote.get("percent_change_24h") or 0,
                        "price_change_7d": quote.get("percent_change_7d") or 0,
                        "price_change_30d": quote.get("percent_change_30d") or 0,
                        "ath": 0,  # CMC doesn't provide ATH on free tier
                        "ath_change_pct": -50,  # neutral fallback
                        "image": "",  # will use CDN fallback
                        "fdv": fdv,
                        "fdv_mcap_ratio": fdv / mc if mc > 0 else 0,
                        "circulating_supply": circ_supply,
                    }
            except Exception as e:
                logger.warning(f"CMC batch fetch failed: {e}")

    logger.info(f"CMC: {len(prices)} prices, {len(market)} market data entries")
    return prices, market


# ── CoinGecko — Fallback ──────────────────────────────────────────────

async def _fetch_prices_coingecko() -> dict[str, float]:
    ids = _coingecko_ids()
    prices: dict[str, float] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        chunk_size = 250
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i:i + chunk_size]
            try:
                resp = await _fetch_with_retry(
                    client, "GET",
                    f"{COINGECKO_BASE}/simple/price",
                    params={"ids": ",".join(chunk), "vs_currencies": "usd"},
                )
                if resp:
                    data = resp.json()
                    for cg_id, info in data.items():
                        prices[cg_id] = info.get("usd", 0)
            except Exception as e:
                logger.warning(f"CoinGecko price fetch failed: {e}")
    return prices


async def _fetch_market_data_coingecko() -> dict[str, dict]:
    ids = _coingecko_ids()
    result: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for page in range(1, 4):
            try:
                resp = await _fetch_with_retry(
                    client, "GET",
                    f"{COINGECKO_BASE}/coins/markets",
                    params={
                        "vs_currency": "usd",
                        "ids": ",".join(ids),
                        "order": "market_cap_desc",
                        "per_page": 250,
                        "page": page,
                        "sparkline": "false",
                        "price_change_percentage": "7d,30d",
                    },
                )
                if resp:
                    for coin in resp.json():
                        cg_id = coin["id"]
                        mc = coin.get("market_cap") or 0
                        fdv = coin.get("fully_diluted_valuation") or 0
                        circ_supply = coin.get("circulating_supply") or 0
                        result[cg_id] = {
                            "market_cap": mc,
                            "total_volume": coin.get("total_volume", 0),
                            "price_change_24h": coin.get("price_change_percentage_24h", 0),
                            "price_change_7d": coin.get("price_change_percentage_7d_in_currency", 0),
                            "price_change_30d": coin.get("price_change_percentage_30d_in_currency", 0),
                            "ath": coin.get("ath", 0),
                            "ath_change_pct": coin.get("ath_change_percentage", 0),
                            "image": coin.get("image", ""),
                            "fdv": fdv,
                            "fdv_mcap_ratio": fdv / mc if mc > 0 else 0,
                            "circulating_supply": circ_supply,
                        }
            except Exception as e:
                logger.warning(f"CoinGecko market data fetch failed: {e}")
                break
    return result


# ── Public fetch functions ───────────────────────────────────────────────

async def fetch_prices() -> dict[str, float]:
    global _price_cache, _price_ts
    now = time.time()
    if _price_cache and (now - _price_ts) < PRICE_TTL:
        return _price_cache

    # Try CMC first (single call for all tokens)
    prices, _ = await _fetch_cmc_quotes()

    # Fallback to CoinGecko if CMC failed
    if not prices:
        logger.info("CMC returned no prices, trying CoinGecko fallback")
        prices = await _fetch_prices_coingecko()

    if prices:
        _price_cache = prices
        _price_ts = now
    return _price_cache


async def fetch_market_data() -> dict[str, dict]:
    global _market_cache, _market_ts, _price_cache, _price_ts
    now = time.time()
    if _market_cache and (now - _market_ts) < MARKET_DATA_TTL:
        return _market_cache

    # Try CMC first (single call returns prices + market data)
    prices, market = await _fetch_cmc_quotes()

    if market:
        _market_cache = market
        _market_ts = now
        # Also update price cache since CMC returns prices in the same call
        if prices:
            _price_cache = prices
            _price_ts = now

        # Track supply history
        for cg_id, info in market.items():
            circ_supply = info.get("circulating_supply", 0)
            if circ_supply > 0:
                if cg_id not in _supply_history:
                    _supply_history[cg_id] = []
                _supply_history[cg_id].append((now, circ_supply))
                _supply_history[cg_id] = _supply_history[cg_id][-288:]

        logger.info(f"Market data refreshed from CMC: {len(market)} tokens")
        return _market_cache

    # Fallback to CoinGecko
    logger.info("CMC market data failed, trying CoinGecko fallback")
    result = await _fetch_market_data_coingecko()

    if result:
        _market_cache = result
        _market_ts = now
        # Track supply history from CoinGecko
        for cg_id, info in result.items():
            circ_supply = info.get("circulating_supply", 0)
            if circ_supply > 0:
                if cg_id not in _supply_history:
                    _supply_history[cg_id] = []
                _supply_history[cg_id].append((now, circ_supply))
                _supply_history[cg_id] = _supply_history[cg_id][-288:]

    return _market_cache


# ── DefiLlama ──────────────────────────────────────────────────────────

async def fetch_defillama_data() -> dict[str, dict]:
    """Fetch TVL and fee data from DefiLlama (free, no API key)."""
    global _defillama_cache, _defillama_ts
    now = time.time()
    if _defillama_cache and (now - _defillama_ts) < DEFILLAMA_TTL:
        return _defillama_cache

    result: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Fetch TVL data from /protocols (single call, all protocols)
        try:
            resp = await client.get(f"{DEFILLAMA_BASE}/protocols")
            resp.raise_for_status()
            protocols = resp.json()
            slug_data = {}
            for p in protocols:
                slug_data[p.get("slug", "").lower()] = p

            for ticker, slug in DEFILLAMA_MAP.items():
                pdata = slug_data.get(slug.lower())
                if pdata:
                    tvl = pdata.get("tvl") or 0
                    tvl_prev = pdata.get("tvlPrevDay") or tvl
                    tvl_week = pdata.get("tvlPrevWeek") or tvl
                    tvl_month = pdata.get("tvlPrevMonth") or tvl
                    mcap = pdata.get("mcap") or 0
                    fdv = pdata.get("fdv") or 0

                    result[ticker] = {
                        "tvl": tvl,
                        "tvl_change_1d": ((tvl - tvl_prev) / tvl_prev * 100) if tvl_prev else 0,
                        "tvl_change_7d": ((tvl - tvl_week) / tvl_week * 100) if tvl_week else 0,
                        "tvl_change_1m": ((tvl - tvl_month) / tvl_month * 100) if tvl_month else 0,
                        "mcap": mcap,
                        "fdv": fdv,
                        "fdv_mcap_ratio": fdv / mcap if mcap else 0,
                    }
        except Exception as e:
            logger.warning(f"DefiLlama protocols fetch failed: {e}")

        # 2. Fetch fee overview (single call, all protocols)
        try:
            resp = await client.get(f"https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true")
            resp.raise_for_status()
            fee_data = resp.json()
            fee_protocols = fee_data.get("protocols", [])

            fee_by_slug = {}
            for fp in fee_protocols:
                s = (fp.get("slug") or fp.get("module") or fp.get("name", "")).lower()
                fee_by_slug[s] = fp
                name_lower = fp.get("name", "").lower().replace(" ", "-")
                fee_by_slug[name_lower] = fp

            for ticker, slug in DEFILLAMA_FEES_MAP.items():
                fdata = fee_by_slug.get(slug.lower())
                if not fdata:
                    continue
                if ticker not in result:
                    result[ticker] = {}

                total_30d = fdata.get("total30d") or 0
                total_7d = fdata.get("total7d") or 0
                total_1d = fdata.get("total24h") or 0
                revenue_30d = fdata.get("revenue30d") or 0
                revenue_7d = fdata.get("revenue7d") or 0

                fees_30d_ann = total_30d * 12
                fees_7d_ann = total_7d * 52
                fee_momentum = 0
                if fees_30d_ann > 0:
                    fee_momentum = ((fees_7d_ann - fees_30d_ann) / fees_30d_ann) * 100

                rev_capture = 0
                if total_30d > 0:
                    rev_capture = min(1.0, revenue_30d / total_30d)

                result[ticker].update({
                    "fees_30d": total_30d,
                    "fees_7d": total_7d,
                    "fees_1d": total_1d,
                    "revenue_30d": revenue_30d,
                    "fee_momentum": fee_momentum,
                    "revenue_capture": rev_capture,
                })
        except Exception as e:
            logger.warning(f"DefiLlama fees fetch failed: {e}")

    if result:
        _defillama_cache = result
        _defillama_ts = now
        logger.info(f"DefiLlama data refreshed: {len(result)} protocols")
    return _defillama_cache


# ── DefiLlama Per-Protocol TVL History ────────────────────────────────

def _find_tvl_at_offset(entries: list[dict], target_ts: float, ts_key: str = "date", val_key: str = "tvl") -> float | None:
    """Find TVL value closest to target_ts from a list of {date, tvl} entries."""
    if not entries:
        return None
    best = None
    best_diff = float("inf")
    for e in entries:
        diff = abs(e.get(ts_key, 0) - target_ts)
        if diff < best_diff:
            best_diff = diff
            best = e.get(val_key, 0)
    # Only accept if within 2 days of target
    if best_diff > 2 * 86400:
        return None
    return best


async def _fetch_chain_tvl_history(client: httpx.AsyncClient, chain: str) -> list[dict]:
    """Fetch historical TVL for an L1 chain. Returns [{date, tvl}, ...]."""
    try:
        resp = await _fetch_with_retry(
            client, "GET",
            f"{DEFILLAMA_BASE}/v2/historicalChainTvl/{chain}",
        )
        if resp:
            return resp.json()  # [{date: unix_ts, tvl: float}, ...]
    except Exception as e:
        logger.warning(f"DefiLlama chain TVL fetch failed for {chain}: {e}")
    return []


async def _fetch_protocol_tvl_history(client: httpx.AsyncClient, slug: str) -> dict:
    """Fetch protocol detail. Returns full protocol object."""
    try:
        resp = await _fetch_with_retry(
            client, "GET",
            f"{DEFILLAMA_BASE}/protocol/{slug}",
        )
        if resp:
            return resp.json()
    except Exception as e:
        logger.warning(f"DefiLlama protocol fetch failed for {slug}: {e}")
    return {}


def _compute_tvl_growth(entries: list[dict], ts_key: str = "date", val_key: str = "tvl") -> dict:
    """Compute TVL growth metrics from a time series of TVL entries."""
    now_ts = time.time()
    ts_7d = now_ts - 7 * 86400
    ts_30d = now_ts - 30 * 86400

    tvl_current = entries[-1].get(val_key, 0) if entries else 0
    tvl_7d_ago = _find_tvl_at_offset(entries, ts_7d, ts_key, val_key)
    tvl_30d_ago = _find_tvl_at_offset(entries, ts_30d, ts_key, val_key)

    result: dict = {"tvl_current": tvl_current}
    if tvl_7d_ago and tvl_7d_ago > 0:
        result["tvl_7d_ago"] = tvl_7d_ago
        result["tvl_growth_7d"] = (tvl_current - tvl_7d_ago) / tvl_7d_ago
    if tvl_30d_ago and tvl_30d_ago > 0:
        result["tvl_30d_ago"] = tvl_30d_ago
        result["tvl_growth_30d"] = (tvl_current - tvl_30d_ago) / tvl_30d_ago

    return result


async def fetch_defillama_protocol_detail() -> dict[str, dict]:
    """Fetch per-protocol TVL history with 7d/30d growth from DeFiLlama."""
    global _defillama_protocol_cache, _defillama_protocol_ts
    now = time.time()
    if _defillama_protocol_cache and (now - _defillama_protocol_ts) < DEFILLAMA_TTL:
        return _defillama_protocol_cache

    result: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        for ticker, source in DEFILLAMA_TVL_MAP.items():
            try:
                if source.startswith("chain:"):
                    chain_name = source[len("chain:"):]
                    entries = await _fetch_chain_tvl_history(client, chain_name)
                    if entries:
                        metrics = _compute_tvl_growth(entries)
                        result[ticker] = metrics

                elif source.startswith("protocol:"):
                    slugs = source[len("protocol:"):].split(",")
                    # Single-slug protocol
                    if len(slugs) == 1:
                        proto = await _fetch_protocol_tvl_history(client, slugs[0])
                        if proto:
                            tvl_entries = proto.get("tvl", [])
                            # Protocol TVL uses totalLiquidityUSD
                            normalized = [
                                {"date": e.get("date", 0), "tvl": e.get("totalLiquidityUSD", 0)}
                                for e in tvl_entries
                            ]
                            metrics = _compute_tvl_growth(normalized)

                            # Extract borrowed and staking from currentChainTvls
                            chain_tvls = proto.get("currentChainTvls", {})
                            borrowed = sum(
                                v for k, v in chain_tvls.items()
                                if k.endswith("-borrowed") and isinstance(v, (int, float))
                            )
                            staking = sum(
                                v for k, v in chain_tvls.items()
                                if k.endswith("-staking") and isinstance(v, (int, float))
                            )
                            if borrowed > 0:
                                metrics["borrowed_current"] = borrowed
                            if staking > 0:
                                metrics["staking_current"] = staking

                            result[ticker] = metrics
                    else:
                        # Multi-slug: fetch each, aggregate TVL by date
                        all_tvl_by_date: dict[int, float] = {}
                        total_borrowed = 0.0
                        total_staking = 0.0
                        for slug in slugs:
                            proto = await _fetch_protocol_tvl_history(client, slug.strip())
                            if not proto:
                                continue
                            for e in proto.get("tvl", []):
                                d = e.get("date", 0)
                                all_tvl_by_date[d] = all_tvl_by_date.get(d, 0) + e.get("totalLiquidityUSD", 0)
                            chain_tvls = proto.get("currentChainTvls", {})
                            total_borrowed += sum(
                                v for k, v in chain_tvls.items()
                                if k.endswith("-borrowed") and isinstance(v, (int, float))
                            )
                            total_staking += sum(
                                v for k, v in chain_tvls.items()
                                if k.endswith("-staking") and isinstance(v, (int, float))
                            )
                            await asyncio.sleep(0.5)  # rate limit between slugs

                        if all_tvl_by_date:
                            sorted_entries = [
                                {"date": d, "tvl": v}
                                for d, v in sorted(all_tvl_by_date.items())
                            ]
                            metrics = _compute_tvl_growth(sorted_entries)
                            if total_borrowed > 0:
                                metrics["borrowed_current"] = total_borrowed
                            if total_staking > 0:
                                metrics["staking_current"] = total_staking
                            result[ticker] = metrics

            except Exception as e:
                logger.warning(f"DefiLlama protocol detail failed for {ticker}: {e}")

            # Rate limit: 0.5s between requests
            await asyncio.sleep(0.5)

    if result:
        _defillama_protocol_cache = result
        _defillama_protocol_ts = now
        logger.info(f"DefiLlama protocol detail refreshed: {len(result)} tokens")
    return _defillama_protocol_cache


def get_defillama_protocol_info(ticker: str) -> dict | None:
    """Return per-protocol TVL history and growth metrics for a ticker."""
    return _defillama_protocol_cache.get(ticker)


# ── Binance Futures ────────────────────────────────────────────────────

async def fetch_binance_perp_data() -> dict[str, dict]:
    """Fetch funding rates + OI from Binance Futures public API (free, no auth)."""
    global _binance_cache, _binance_ts
    now = time.time()
    if _binance_cache and (now - _binance_ts) < BINANCE_TTL:
        return _binance_cache

    result: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=15) as client:
        # Funding rates for ALL perps in one call
        try:
            resp = await client.get(f"{BINANCE_FAPI}/premiumIndex")
            resp.raise_for_status()
            for item in resp.json():
                symbol = item.get("symbol", "")
                if not symbol.endswith("USDT"):
                    continue
                ticker = symbol.replace("USDT", "")
                result[ticker] = {
                    "funding_rate": float(item.get("lastFundingRate", 0)),
                    "mark_price": float(item.get("markPrice", 0)),
                    "index_price": float(item.get("indexPrice", 0)),
                }
            logger.info(f"Binance perp data: {len(result)} symbols (funding rates)")
        except Exception as e:
            logger.warning(f"Binance premiumIndex fetch failed: {e}")

        # Open Interest for tokens in our universe
        tickers_with_perps = [t for t in TOKEN_MAP.keys() if t in result]
        for ticker in tickers_with_perps[:30]:
            try:
                resp = await client.get(
                    f"{BINANCE_FAPI}/openInterest",
                    params={"symbol": f"{ticker}USDT"},
                )
                if resp.status_code == 200:
                    oi_data = resp.json()
                    result[ticker]["open_interest"] = float(oi_data.get("openInterest", 0))
                    price = result[ticker].get("mark_price", 0)
                    result[ticker]["open_interest_usd"] = result[ticker]["open_interest"] * price
            except Exception:
                pass

    if result:
        _binance_cache = result
        _binance_ts = now
    return _binance_cache


# ── CoinGecko Historical Prices (for DCA backtest) ───────────────────

_historical_cache: dict[str, list[tuple[float, float]]] = {}  # {cg_id: [(ts, price), ...]}
_historical_cache_ts: float = 0
HISTORICAL_TTL = 86400  # 24h — historical data doesn't change


CRYPTOCOMPARE_BASE = "https://min-api.cryptocompare.com"
_SKIP_HISTORICAL = {"USDC", "EURC"}  # stablecoins — constant $1


async def fetch_historical_prices(tickers: list[str], days: int = 365) -> dict[str, list[tuple[float, float]]]:
    """Fetch daily historical prices from CryptoCompare for DCA backtesting.

    Uses CryptoCompare /data/v2/histoday — free, no API key, generous rate limits.
    Returns {ticker: [(unix_ts, price_usd), ...]} sorted ascending by date.
    Cached 24h.
    """
    global _historical_cache, _historical_cache_ts

    days = min(days, 1100)  # CryptoCompare supports up to 2000
    fetch_tickers = [t for t in tickers if t not in _SKIP_HISTORICAL]

    now = time.time()
    missing = [t for t in fetch_tickers if t not in _historical_cache
               or now - _historical_cache_ts > HISTORICAL_TTL]

    if not missing:
        return {t: _historical_cache[t] for t in fetch_tickers if t in _historical_cache}

    logger.info(f"Fetching historical prices from CryptoCompare for {len(missing)} tokens ({days} days)")

    async with httpx.AsyncClient() as client:
        for t in missing:
            sym = CMC_SYMBOL_OVERRIDES.get(t, t)
            try:
                resp = await _fetch_with_retry(
                    client, "GET",
                    f"{CRYPTOCOMPARE_BASE}/data/v2/histoday",
                    params={"fsym": sym, "tsym": "USD", "limit": str(days)},
                    timeout=15,
                )
                data = resp.json()
                entries = data.get("Data", {}).get("Data", [])
                daily = []
                for e in entries:
                    ts = e.get("time", 0)
                    close = e.get("close", 0)
                    if ts > 0 and close > 0:
                        daily.append((float(ts), float(close)))
                if daily:
                    _historical_cache[t] = daily
                    logger.info(f"  {t}: {len(daily)} daily prices")
                else:
                    logger.warning(f"  {t}: no data from CryptoCompare")
            except Exception as e:
                logger.warning(f"CryptoCompare historical failed for {t}: {e}")
            await asyncio.sleep(0.3)  # CryptoCompare is generous but be polite

    _historical_cache_ts = now
    return {t: _historical_cache[t] for t in fetch_tickers if t in _historical_cache}

    result = {}
    for t in tickers:
        cg_id = TOKEN_MAP.get(t)
        if cg_id and cg_id in _historical_cache:
            result[t] = _historical_cache[cg_id]
    return result


# ── CoinGecko Developer & Community Data ──────────────────────────────

async def fetch_coingecko_dev_data() -> dict[str, dict]:
    """Fetch developer activity and community data from CoinGecko (per-coin endpoint)."""
    global _coingecko_dev_cache, _coingecko_dev_ts
    now = time.time()
    if _coingecko_dev_cache and (now - _coingecko_dev_ts) < COINGECKO_DEV_TTL:
        return _coingecko_dev_cache

    result: dict[str, dict] = {}
    ids = _coingecko_ids()

    async with httpx.AsyncClient(timeout=30) as client:
        for cg_id in ids:
            ticker = _CGID_TO_TICKER.get(cg_id)
            if not ticker:
                continue
            try:
                resp = await _fetch_with_retry(
                    client, "GET",
                    f"{COINGECKO_BASE}/coins/{cg_id}",
                    params={
                        "localization": "false",
                        "tickers": "false",
                        "market_data": "false",
                        "community_data": "true",
                        "developer_data": "true",
                    },
                )
                if resp:
                    data = resp.json()
                    dev = data.get("developer_data") or {}
                    community = data.get("community_data") or {}
                    result[ticker] = {
                        "commit_count_4_weeks": dev.get("commit_count_4_weeks", 0),
                        "forks": dev.get("forks", 0),
                        "pull_requests_merged": dev.get("pull_requests_merged", 0),
                        "pull_request_contributors": dev.get("pull_request_contributors", 0),
                        "reddit_subscribers": community.get("reddit_subscribers", 0),
                        "telegram_channel_user_count": community.get("telegram_channel_user_count", 0),
                    }
            except Exception as e:
                logger.warning(f"CoinGecko dev data fetch failed for {cg_id}: {e}")

            # Rate limit: 1 request per 2 seconds (CoinGecko free tier = 30/min)
            await asyncio.sleep(2)

    if result:
        _coingecko_dev_cache = result
        _coingecko_dev_ts = now
        logger.info(f"CoinGecko dev/community data refreshed: {len(result)} tokens")
    return _coingecko_dev_cache


# ── Messari Free Network Metrics ─────────────────────────────────────

# Reverse map: slug → ticker (for matching API response to our universe)
_MESSARI_SLUG_TO_TICKER = {v: k for k, v in MESSARI_NETWORK_MAP.items()}


async def fetch_messari_networks() -> dict[str, dict]:
    """Fetch network metrics from Messari free API (no auth required)."""
    global _messari_cache, _messari_ts
    now = time.time()
    if _messari_cache and (now - _messari_ts) < MESSARI_TTL:
        return _messari_cache

    result: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await _fetch_with_retry(
                client, "GET",
                f"{MESSARI_BASE}/metrics/v2/networks",
                params={"limit": 200},
            )
            if not resp:
                return _messari_cache

            raw = resp.json()
            # Response structure: {"data": {"data": [...]}}
            networks = raw.get("data", {})
            if isinstance(networks, dict):
                networks = networks.get("data", [])

            for net in networks:
                slug = net.get("slug", "")
                ticker = _MESSARI_SLUG_TO_TICKER.get(slug)
                if not ticker:
                    continue

                metrics = net.get("metrics", {})
                activity = metrics.get("activity", {}) or {}
                financial = metrics.get("financial", {}) or {}
                ecosystem = metrics.get("ecosystem", {}) or {}
                stablecoin = metrics.get("stablecoin", {}) or {}

                result[ticker] = {
                    "active_addresses": activity.get("activeAddresses24Hour"),
                    "txn_count": activity.get("txnCount24Hour"),
                    "fees_24h_usd": financial.get("feesTotal24HourUsd"),
                    "revenue_24h_usd": financial.get("revenue24HourUsd"),
                    "fees_7d_avg_usd": financial.get("rolling7dAvgFeeUsd"),
                    "dev_commits": ecosystem.get("coreCommits24Hour"),
                    "active_devs": ecosystem.get("activeDevelopers24Hour"),
                    "tvl_usd": ecosystem.get("tvl24HourUsd"),
                    "dex_volume_usd": ecosystem.get("dexVolume24HourUsd"),
                    "stablecoin_supply_usd": stablecoin.get("outstandingSupplyUsd"),
                }

            logger.info(f"Messari networks: fetched {len(result)} chains")
        except Exception as e:
            logger.warning(f"Messari networks fetch failed: {e}")

    if result:
        _messari_cache = result
        _messari_ts = now
    return _messari_cache


# ── Public getters ─────────────────────────────────────────────────────

def get_messari_info(ticker: str) -> dict | None:
    """Return Messari network metrics for a ticker."""
    return _messari_cache.get(ticker)


def get_dev_info(ticker: str) -> dict | None:
    """Return developer & community data for a ticker."""
    return _coingecko_dev_cache.get(ticker)


def get_binance_info(ticker: str) -> Optional[dict]:
    return _binance_cache.get(ticker)


def get_supply_delta_pct(ticker: str) -> Optional[float]:
    """Compute supply delta % from in-memory history. Returns None if insufficient data."""
    cg_id = TOKEN_MAP.get(ticker)
    if not cg_id or cg_id not in _supply_history:
        return None
    history = _supply_history[cg_id]
    if len(history) < 2:
        return None
    oldest_ts, oldest_supply = history[0]
    latest_ts, latest_supply = history[-1]
    if oldest_supply <= 0 or (latest_ts - oldest_ts) < 1800:
        return None
    return (latest_supply - oldest_supply) / oldest_supply * 100


def get_defillama_info(ticker: str) -> Optional[dict]:
    return _defillama_cache.get(ticker)


def get_price(ticker: str) -> Optional[float]:
    cg_id = TOKEN_MAP.get(ticker)
    if not cg_id:
        return None
    return _price_cache.get(cg_id)


def get_market_info(ticker: str) -> Optional[dict]:
    cg_id = TOKEN_MAP.get(ticker)
    if not cg_id:
        return None
    return _market_cache.get(cg_id)


def get_logo_url(ticker: str) -> str:
    """Return logo URL for a ticker. Uses cached image or CDN fallback."""
    cg_id = TOKEN_MAP.get(ticker)
    if not cg_id:
        return ""
    # Try cached image (CoinGecko fallback may have populated this)
    info = _market_cache.get(cg_id)
    if info and info.get("image"):
        return info["image"]
    # CDN fallback (free, no API key)
    return f"https://cryptofonts.com/img/icons/{ticker.lower()}.svg"


def price_age_str() -> str:
    if not _price_ts:
        return "No data"
    age = int(time.time() - _price_ts)
    if age < 60:
        return f"{age}s ago"
    return f"{age // 60}m ago"


async def background_refresh():
    while True:
        try:
            await fetch_prices()
            await fetch_market_data()
            _mark_source_ok("cmc")
            logger.info(f"Market data refreshed: {len(_price_cache)} prices, {len(_market_cache)} market")
        except Exception as e:
            _mark_source_fail("cmc")
            logger.error(f"Background refresh error: {e}")
        try:
            await fetch_defillama_data()
            _mark_source_ok("defillama")
        except Exception as e:
            _mark_source_fail("defillama")
            logger.error(f"DefiLlama refresh error: {e}")
        try:
            await fetch_binance_perp_data()
            _mark_source_ok("binance")
        except Exception as e:
            _mark_source_fail("binance")
            logger.error(f"Binance perp refresh error: {e}")
        try:
            if time.time() - _coingecko_dev_ts >= COINGECKO_DEV_TTL:
                await fetch_coingecko_dev_data()
                _mark_source_ok("coingecko_dev")
        except Exception as e:
            _mark_source_fail("coingecko_dev")
            logger.error(f"CoinGecko dev data refresh error: {e}")
        try:
            if time.time() - _messari_ts >= MESSARI_TTL:
                await fetch_messari_networks()
                _mark_source_ok("messari")
        except Exception as e:
            _mark_source_fail("messari")
            logger.error(f"Messari networks refresh error: {e}")
        try:
            if time.time() - _defillama_protocol_ts >= DEFILLAMA_TTL:
                await fetch_defillama_protocol_detail()
                _mark_source_ok("defillama_protocol")
        except Exception as e:
            _mark_source_fail("defillama_protocol")
            logger.error(f"DefiLlama protocol detail refresh error: {e}")
        await asyncio.sleep(PRICE_TTL)
