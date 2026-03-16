"""
Market data client with CoinGecko primary + CoinMarketCap fallback.
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

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
CMC_BASE = "https://pro-api.coinmarketcap.com/v1"
CMC_API_KEY = os.getenv("CMC_API_KEY", "")
DEFILLAMA_BASE = "https://api.llama.fi"
DEFILLAMA_FEES_BASE = "https://fees.llama.fi"
PRICE_TTL = 300        # 5 minutes
MARKET_DATA_TTL = 3600 # 1 hour
DEFILLAMA_TTL = 7200   # 2 hours

_price_cache: dict[str, float] = {}
_price_ts: float = 0
_market_cache: dict[str, dict] = {}
_market_ts: float = 0
_defillama_cache: dict[str, dict] = {}
_defillama_ts: float = 0


def _coingecko_ids() -> list[str]:
    return [cg_id for cg_id in TOKEN_MAP.values() if cg_id]


# ── Retry helper ─────────────────────────────────────────────────────────

async def _fetch_with_retry(client, method, url, max_retries=3, **kwargs):
    """Fetch with exponential backoff on 429/5xx errors."""
    for attempt in range(max_retries):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
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


# ── CoinGecko price fetch ────────────────────────────────────────────────

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


# ── CoinMarketCap fallback ───────────────────────────────────────────────

# CMC uses symbols; map our tickers to CMC-compatible symbols
def _get_cmc_symbols() -> list[str]:
    """Return list of ticker symbols for CMC API."""
    return [t for t in TOKEN_MAP.keys() if t]


async def _fetch_prices_cmc() -> dict[str, float]:
    """Fetch prices from CoinMarketCap as fallback. Returns {coingecko_id: price}."""
    if not CMC_API_KEY:
        return {}

    symbols = _get_cmc_symbols()
    prices: dict[str, float] = {}
    # CMC maps: symbol -> ticker -> coingecko_id
    ticker_to_cgid = TOKEN_MAP

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # CMC allows up to 5000 symbols per call
            resp = await client.get(
                f"{CMC_BASE}/cryptocurrency/quotes/latest",
                params={"symbol": ",".join(symbols), "convert": "USD"},
                headers={"X-CMC_PRO_API_KEY": CMC_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for symbol, entries in data.items():
                # CMC can return a list for ambiguous symbols
                coin = entries[0] if isinstance(entries, list) else entries
                usd_price = coin.get("quote", {}).get("USD", {}).get("price")
                if usd_price is not None:
                    cg_id = ticker_to_cgid.get(symbol)
                    if cg_id:
                        prices[cg_id] = usd_price
            logger.info(f"CMC fallback: {len(prices)} prices fetched")
        except Exception as e:
            logger.warning(f"CMC price fetch failed: {e}")

    return prices


# ── Public fetch functions ───────────────────────────────────────────────

async def fetch_prices() -> dict[str, float]:
    global _price_cache, _price_ts
    now = time.time()
    if _price_cache and (now - _price_ts) < PRICE_TTL:
        return _price_cache

    # Try CoinGecko first
    prices = await _fetch_prices_coingecko()

    # Fallback to CMC if CoinGecko returned nothing
    if not prices and CMC_API_KEY:
        logger.info("CoinGecko returned no prices, trying CMC fallback")
        prices = await _fetch_prices_cmc()

    if prices:
        _price_cache = prices
        _price_ts = now
    return _price_cache


async def fetch_market_data() -> dict[str, dict]:
    global _market_cache, _market_ts
    now = time.time()
    if _market_cache and (now - _market_ts) < MARKET_DATA_TTL:
        return _market_cache

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
                        result[coin["id"]] = {
                            "market_cap": coin.get("market_cap", 0),
                            "total_volume": coin.get("total_volume", 0),
                            "price_change_24h": coin.get("price_change_percentage_24h", 0),
                            "price_change_7d": coin.get("price_change_percentage_7d_in_currency", 0),
                            "price_change_30d": coin.get("price_change_percentage_30d_in_currency", 0),
                            "ath": coin.get("ath", 0),
                            "ath_change_pct": coin.get("ath_change_percentage", 0),
                            "image": coin.get("image", ""),
                        }
            except Exception as e:
                logger.warning(f"CoinGecko market data fetch failed: {e}")
                break

    if result:
        _market_cache = result
        _market_ts = now
    return _market_cache


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
    """Return CoinGecko logo URL for a ticker, or empty string."""
    cg_id = TOKEN_MAP.get(ticker)
    if not cg_id:
        return ""
    info = _market_cache.get(cg_id)
    if info and info.get("image"):
        return info["image"]
    return ""


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
            logger.info(f"Market data refreshed: {len(_price_cache)} prices")
        except Exception as e:
            logger.error(f"Background refresh error: {e}")
        try:
            await fetch_defillama_data()
        except Exception as e:
            logger.error(f"DefiLlama refresh error: {e}")
        await asyncio.sleep(PRICE_TTL)
