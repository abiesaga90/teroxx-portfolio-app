"""
CoinGecko market data client with in-memory TTL cache.
"""
import asyncio
import time
import logging
from typing import Optional

import httpx

from app.data import TOKEN_MAP, ASSET_UNIVERSE

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
PRICE_TTL = 300        # 5 minutes
MARKET_DATA_TTL = 3600 # 1 hour

_price_cache: dict[str, float] = {}
_price_ts: float = 0
_market_cache: dict[str, dict] = {}
_market_ts: float = 0


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
                    }
            except Exception as e:
                logger.warning(f"CoinGecko market data fetch failed: {e}")
                break

    if result:
        _market_cache = result
        _market_ts = now
    return _market_cache


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
        await asyncio.sleep(PRICE_TTL)
