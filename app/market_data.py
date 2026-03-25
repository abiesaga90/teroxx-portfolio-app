"""
Market data client — CoinMarketCap primary, CoinGecko fallback.
In-memory TTL cache, retry with exponential backoff.
"""
import asyncio
import os
import time
import logging
from typing import Optional

import httpx

from app.data import TOKEN_MAP, ASSET_UNIVERSE, DEFILLAMA_MAP, DEFILLAMA_FEES_MAP

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
                _supply_history[cg_id] = _supply_history[cg_id][-48:]

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
                _supply_history[cg_id] = _supply_history[cg_id][-48:]

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


# ── Public getters ─────────────────────────────────────────────────────

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
            logger.info(f"Market data refreshed: {len(_price_cache)} prices, {len(_market_cache)} market")
        except Exception as e:
            logger.error(f"Background refresh error: {e}")
        try:
            await fetch_defillama_data()
        except Exception as e:
            logger.error(f"DefiLlama refresh error: {e}")
        try:
            await fetch_binance_perp_data()
        except Exception as e:
            logger.error(f"Binance perp refresh error: {e}")
        await asyncio.sleep(PRICE_TTL)
