"""
CoinGecko market data client with in-memory TTL cache.
"""
import asyncio
import time
import logging
from typing import Optional

import httpx

from app.data import TOKEN_MAP, ASSET_UNIVERSE, DEFILLAMA_MAP, DEFILLAMA_FEES_MAP

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE = "https://api.llama.fi"
DEFILLAMA_FEES_BASE = "https://fees.llama.fi"
PRICE_TTL = 300        # 5 minutes
MARKET_DATA_TTL = 3600 # 1 hour
DEFILLAMA_TTL = 7200   # 2 hours

_price_cache: dict[str, float] = {}
_price_ts: float = 0
_market_cache: dict[str, dict] = {}
_market_ts: float = 0
_defillama_cache: dict[str, dict] = {}  # ticker -> {tvl, tvl_change, fees_30d, ...}
_defillama_ts: float = 0


def _coingecko_ids() -> list[str]:
    return [cg_id for cg_id in TOKEN_MAP.values() if cg_id]


async def fetch_prices() -> dict[str, float]:
    global _price_cache, _price_ts
    now = time.time()
    if _price_cache and (now - _price_ts) < PRICE_TTL:
        return _price_cache

    ids = _coingecko_ids()
    prices: dict[str, float] = {}
    # CoinGecko allows batching all IDs
    chunk_size = 250
    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i:i + chunk_size]
            try:
                resp = await client.get(
                    f"{COINGECKO_BASE}/simple/price",
                    params={"ids": ",".join(chunk), "vs_currencies": "usd"},
                )
                resp.raise_for_status()
                data = resp.json()
                for cg_id, info in data.items():
                    prices[cg_id] = info.get("usd", 0)
            except Exception as e:
                logger.warning(f"CoinGecko price fetch failed: {e}")

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
        for page in range(1, 4):  # 3 pages x 250 = enough for 79 tokens
            try:
                resp = await client.get(
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
                resp.raise_for_status()
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
            # Build slug -> protocol data lookup
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

            # Build slug -> fee data
            fee_by_slug = {}
            for fp in fee_protocols:
                s = (fp.get("slug") or fp.get("module") or fp.get("name", "")).lower()
                fee_by_slug[s] = fp
                # Also index by defillamaId or name
                name_lower = fp.get("name", "").lower().replace(" ", "-")
                fee_by_slug[name_lower] = fp

            for ticker, slug in DEFILLAMA_FEES_MAP.items():
                fdata = fee_by_slug.get(slug.lower())
                if not fdata:
                    # Try alternate lookups
                    continue
                if ticker not in result:
                    result[ticker] = {}

                total_30d = fdata.get("total30d") or 0
                total_7d = fdata.get("total7d") or 0
                total_1d = fdata.get("total24h") or 0
                revenue_30d = fdata.get("revenue30d") or 0
                revenue_7d = fdata.get("revenue7d") or 0

                # Fee momentum: compare 7d annualized vs 30d annualized
                fees_30d_ann = total_30d * 12
                fees_7d_ann = total_7d * 52
                fee_momentum = 0
                if fees_30d_ann > 0:
                    fee_momentum = ((fees_7d_ann - fees_30d_ann) / fees_30d_ann) * 100

                # Revenue capture: what % of fees go to holders
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
        # Fetch DefiLlama less frequently (every 2 hours via its own TTL)
        try:
            await fetch_defillama_data()
        except Exception as e:
            logger.error(f"DefiLlama refresh error: {e}")
        await asyncio.sleep(PRICE_TTL)
