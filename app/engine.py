"""
Allocation engine — factor scoring, DCA planner, rebalancer, P&L calculator.
"""
from app.data import (
    ASSET_UNIVERSE, ASSET_BY_TICKER, ASSET_UNIVERSES,
    FIXED_STRATEGIC, TIER_ALLOCATIONS, RISK_TILT_PARAMETERS,
    FIVE_FACTOR_WEIGHTS, TEN_FACTOR_WEIGHTS,
    DEFAULT_FIVE_FACTOR_SCORES, DEFAULT_TEN_FACTOR_SCORES,
    ETH_TEN_FACTOR_OVERRIDES, DCA_SCOPES,
    get_alloc_tier,
)
from app.market_data import get_price


def get_universe_tickers(universe_name: str) -> list[str]:
    from app.data import ASSET_UNIVERSES
    explicit = ASSET_UNIVERSES.get(universe_name)
    if isinstance(explicit, list):
        return explicit
    if universe_name == "Extended (79)":
        return [a["ticker"] for a in ASSET_UNIVERSE]
    if universe_name == "Long (53)":
        return [a["ticker"] for a in ASSET_UNIVERSE if a["tier"] != "Short"]
    return [a["ticker"] for a in ASSET_UNIVERSE]


def compute_allocations(profile: str, universe: str, mode: str = "Standard") -> list[dict]:
    tickers = get_universe_tickers(universe)
    results = []
    # Fixed strategic first
    fixed_total = 0
    for ticker in tickers:
        if ticker in FIXED_STRATEGIC:
            alloc = FIXED_STRATEGIC[ticker].get(profile, 0)
            fixed_total += alloc
            asset = ASSET_BY_TICKER.get(ticker, {})
            results.append({
                "ticker": ticker,
                "name": asset.get("name", ticker),
                "tier": "Fixed",
                "risk_tier": asset.get("risk_tier", ""),
                "category": asset.get("category", ""),
                "alloc_pct": alloc,
            })

    # Crypto tickers (non-fixed)
    crypto_tickers = [t for t in tickers if t not in FIXED_STRATEGIC]
    remaining = 1.0 - fixed_total

    # Group by allocation tier
    tier_groups: dict[str, list[str]] = {}
    for t in crypto_tickers:
        atier = get_alloc_tier(t)
        tier_groups.setdefault(atier, []).append(t)

    # Get factor/fundamental scores if needed
    scores = {}
    if mode == "Factor Model":
        scores = compute_five_factor_scores(profile, crypto_tickers)
    elif mode == "Fundamental Model":
        scores = compute_ten_factor_scores(profile, crypto_tickers)

    for tier_name, tier_tickers in tier_groups.items():
        tier_budget = TIER_ALLOCATIONS.get(tier_name, {}).get(profile, 0)
        if tier_budget <= 0 or not tier_tickers:
            for t in tier_tickers:
                asset = ASSET_BY_TICKER.get(t, {})
                results.append({
                    "ticker": t,
                    "name": asset.get("name", t),
                    "tier": tier_name,
                    "risk_tier": asset.get("risk_tier", ""),
                    "category": asset.get("category", ""),
                    "alloc_pct": 0,
                })
            continue

        if mode == "Standard":
            # Equal weight within tier
            per_asset = tier_budget / len(tier_tickers)
            for t in tier_tickers:
                asset = ASSET_BY_TICKER.get(t, {})
                results.append({
                    "ticker": t,
                    "name": asset.get("name", t),
                    "tier": tier_name,
                    "risk_tier": asset.get("risk_tier", ""),
                    "category": asset.get("category", ""),
                    "alloc_pct": per_asset,
                })
        else:
            # Score-weighted within tier
            tier_scores = {t: scores.get(t, 50) for t in tier_tickers}
            total_score = sum(tier_scores.values())
            if total_score == 0:
                total_score = 1
            for t in tier_tickers:
                asset = ASSET_BY_TICKER.get(t, {})
                weight = tier_scores[t] / total_score
                results.append({
                    "ticker": t,
                    "name": asset.get("name", t),
                    "tier": tier_name,
                    "risk_tier": asset.get("risk_tier", ""),
                    "category": asset.get("category", ""),
                    "alloc_pct": tier_budget * weight,
                })

    # Sort: Fixed first, then by alloc descending
    tier_order = {"Fixed": 0, "Store of Value": 1, "Large Cap": 2, "Mid Cap": 3, "Small Cap": 4}
    results.sort(key=lambda x: (tier_order.get(x["tier"], 5), -x["alloc_pct"]))
    return results


def compute_five_factor_scores(profile: str, tickers: list[str]) -> dict[str, float]:
    scores = {}
    for t in tickers:
        composite = 0
        for factor, weights in FIVE_FACTOR_WEIGHTS.items():
            w = weights.get(profile, 0)
            s = DEFAULT_FIVE_FACTOR_SCORES.get(factor, 50)
            composite += w * s
        scores[t] = composite
    return scores


def compute_ten_factor_scores(profile: str, tickers: list[str]) -> dict[str, float]:
    scores = {}
    for t in tickers:
        composite = 0
        for factor, weights in TEN_FACTOR_WEIGHTS.items():
            w = weights.get(profile, 0)
            base = DEFAULT_TEN_FACTOR_SCORES.get(factor, 50)
            if t == "ETH":
                base = ETH_TEN_FACTOR_OVERRIDES.get(factor, base)
            composite += w * base
        scores[t] = composite
    return scores


def compute_portfolio(profile: str, universe: str, mode: str, portfolio_value: float) -> list[dict]:
    allocs = compute_allocations(profile, universe, mode)
    for a in allocs:
        a["dollar_amount"] = portfolio_value * a["alloc_pct"]
        price = get_price(a["ticker"])
        a["price"] = price
    return allocs


def compute_dca(
    profile: str, universe: str, mode: str,
    monthly_amount: float, dca_scope: str, horizon_months: int, min_order: float
) -> list[dict]:
    allocs = compute_allocations(profile, universe, mode)
    # Filter to DCA-eligible tickers
    scope_def = DCA_SCOPES.get(dca_scope, "all")
    if isinstance(scope_def, list):
        eligible = [a for a in allocs if a["ticker"] in scope_def]
    else:
        eligible = [a for a in allocs if a["ticker"] not in ("USDC", "EURC")]

    # Normalize weights among eligible
    total_alloc = sum(a["alloc_pct"] for a in eligible)
    if total_alloc == 0:
        return []

    results = []
    for a in eligible:
        dca_weight = a["alloc_pct"] / total_alloc
        monthly_buy = monthly_amount * dca_weight
        if monthly_buy < min_order:
            continue
        results.append({
            "ticker": a["ticker"],
            "name": a["name"],
            "tier": a["tier"],
            "portfolio_pct": a["alloc_pct"],
            "dca_weight": dca_weight,
            "monthly_buy": monthly_buy,
            "horizon_total": monthly_buy * horizon_months,
            "price": get_price(a["ticker"]),
        })

    results.sort(key=lambda x: -x["dca_weight"])
    return results


def compute_rebalance(
    profile: str, universe: str, mode: str,
    portfolio_value: float, current_holdings: dict[str, float]
) -> list[dict]:
    allocs = compute_allocations(profile, universe, mode)
    results = []
    for a in allocs:
        target_usd = portfolio_value * a["alloc_pct"]
        current_usd = current_holdings.get(a["ticker"], 0)
        diff = target_usd - current_usd
        action = ""
        if abs(diff) > 1:
            action = "BUY" if diff > 0 else "SELL"
        results.append({
            "ticker": a["ticker"],
            "name": a["name"],
            "tier": a["tier"],
            "target_pct": a["alloc_pct"],
            "target_usd": target_usd,
            "current_usd": current_usd,
            "difference": diff,
            "action": action,
        })
    return results


def compute_pnl(positions: list[dict]) -> list[dict]:
    results = []
    total_cost = 0
    total_value = 0
    for pos in positions:
        ticker = pos.get("ticker", "")
        qty = pos.get("quantity", 0)
        entry_price = pos.get("entry_price", 0)
        current_price = get_price(ticker) or 0
        cost_basis = qty * entry_price
        current_value = qty * current_price
        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0
        total_cost += cost_basis
        total_value += current_value
        asset = ASSET_BY_TICKER.get(ticker, {})
        results.append({
            "ticker": ticker,
            "name": asset.get("name", ticker),
            "quantity": qty,
            "entry_price": entry_price,
            "current_price": current_price,
            "cost_basis": cost_basis,
            "current_value": current_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
    return results


def five_factor_detail(profile: str, tickers: list[str]) -> list[dict]:
    results = []
    for t in tickers:
        row = {"ticker": t, "name": ASSET_BY_TICKER.get(t, {}).get("name", t)}
        composite = 0
        for factor, weights in FIVE_FACTOR_WEIGHTS.items():
            score = DEFAULT_FIVE_FACTOR_SCORES.get(factor, 50)
            row[factor] = score
            composite += weights.get(profile, 0) * score
        row["composite"] = round(composite, 1)
        results.append(row)
    results.sort(key=lambda x: -x["composite"])
    return results


def ten_factor_detail(profile: str, tickers: list[str]) -> list[dict]:
    results = []
    for t in tickers:
        row = {"ticker": t, "name": ASSET_BY_TICKER.get(t, {}).get("name", t)}
        composite = 0
        for factor, weights in TEN_FACTOR_WEIGHTS.items():
            base = DEFAULT_TEN_FACTOR_SCORES.get(factor, 50)
            if t == "ETH":
                base = ETH_TEN_FACTOR_OVERRIDES.get(factor, base)
            row[factor] = base
            composite += weights.get(profile, 0) * base
        row["composite"] = round(composite, 1)
        results.append(row)
    results.sort(key=lambda x: -x["composite"])
    return results
