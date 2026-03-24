"""
Allocation engine — factor scoring, DCA planner, rebalancer, P&L calculator.

Factor scores are computed from live CoinGecko market data rather than
static defaults. Each factor is scored 0-100 using percentile ranking
across the universe.
"""
import math
from app.data import (
    ASSET_UNIVERSE, ASSET_BY_TICKER, ASSET_UNIVERSES,
    FIXED_STRATEGIC, TIER_ALLOCATIONS,
    FIVE_FACTOR_WEIGHTS, TEN_FACTOR_WEIGHTS,
    DCA_SCOPES, get_alloc_tier,
)
from app.market_data import get_price, get_market_info, get_defillama_info, get_binance_info, get_supply_delta_pct


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


# ── Percentile scoring helper ──────────────────────────────────────────

def _percentile_rank(values: list[float]) -> list[float]:
    """Convert raw values to 0-100 percentile scores. Higher value = higher score."""
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [50.0]
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    for rank_pos, (orig_idx, _) in enumerate(indexed):
        ranks[orig_idx] = round(rank_pos / (n - 1) * 100, 1)
    return ranks


def _inverse_percentile_rank(values: list[float]) -> list[float]:
    """Lower value = higher score (e.g., for beta/volatility)."""
    ranks = _percentile_rank(values)
    return [round(100 - r, 1) for r in ranks]


# ── 5-Factor scoring from live market data ─────────────────────────────

def _get_raw_market_vectors(tickers: list[str]) -> dict:
    """Extract raw market data vectors for scoring."""
    market_caps = []
    volumes = []
    change_7d = []
    change_30d = []
    change_24h = []
    ath_drawdowns = []
    vol_mcap_ratios = []
    funding_rates = []
    open_interests_usd = []
    fdv_mcap_ratios = []
    supply_deltas = []

    for t in tickers:
        info = get_market_info(t)
        if info:
            mc = info.get("market_cap") or 0
            vol = info.get("total_volume") or 0
            c7d = info.get("price_change_7d") or 0
            c30d = info.get("price_change_30d") or 0
            c24h = info.get("price_change_24h") or 0
            ath_dd = abs(info.get("ath_change_pct") or -50)
            fdv_ratio = info.get("fdv_mcap_ratio") or 0
        else:
            mc = vol = c7d = c30d = c24h = 0
            ath_dd = 50
            fdv_ratio = 0

        market_caps.append(mc)
        volumes.append(vol)
        change_7d.append(c7d)
        change_30d.append(c30d)
        change_24h.append(c24h)
        ath_drawdowns.append(ath_dd)
        vol_mcap_ratios.append(vol / mc if mc > 0 else 0)
        fdv_mcap_ratios.append(fdv_ratio if fdv_ratio > 0 else 2.0)  # 2.0 = neutral fallback

        # Binance perp data
        bn = get_binance_info(t)
        funding_rates.append(bn.get("funding_rate", 0) if bn else 0)
        open_interests_usd.append(bn.get("open_interest_usd", 0) if bn else 0)

        # Supply delta
        sd = get_supply_delta_pct(t)
        supply_deltas.append(sd if sd is not None else 0)

    return {
        "market_caps": market_caps,
        "volumes": volumes,
        "change_7d": change_7d,
        "change_30d": change_30d,
        "change_24h": change_24h,
        "ath_drawdowns": ath_drawdowns,
        "vol_mcap_ratios": vol_mcap_ratios,
        "funding_rates": funding_rates,
        "open_interests_usd": open_interests_usd,
        "fdv_mcap_ratios": fdv_mcap_ratios,
        "supply_deltas": supply_deltas,
    }


def compute_live_five_factor_scores(tickers: list[str]) -> dict[str, dict[str, float]]:
    """
    Compute 5-factor scores from CoinGecko data:
      Market Beta (Low B)  — lower 30d absolute change = lower beta = higher score
      Size - SMB           — smaller market cap = higher score
      Value (MC/Fees)      — higher volume/mcap ratio = better value
      Momentum (Vol-Adj)   — vol-adjusted momentum (combined change / ATH drawdown)
      Growth (Fee+DAU D)   — 7d acceleration relative to monthly pace
    """
    if not tickers:
        return {}

    raw = _get_raw_market_vectors(tickers)

    # Compute raw factor values
    beta_raw = [abs(c) for c in raw["change_30d"]]  # absolute 30d move as beta proxy
    size_raw = raw["market_caps"]
    value_raw = raw["vol_mcap_ratios"]

    # Momentum: vol-adjusted — total return scaled by how far from ATH
    # Tokens near ATH with positive momentum score highest
    momentum_raw = []
    for c7, c30, ath_dd in zip(raw["change_7d"], raw["change_30d"], raw["ath_drawdowns"]):
        total_return = c7 + c30
        vol_adj = max(ath_dd, 1.0)  # ATH drawdown as volatility proxy
        momentum_raw.append(total_return / vol_adj * 100)

    # Growth: 7d acceleration vs monthly pace (ratio, not difference)
    # High growth = weekly pace >> monthly pace (recent acceleration)
    growth_raw = []
    for c7, c30 in zip(raw["change_7d"], raw["change_30d"]):
        weekly_pace = c7
        monthly_weekly_pace = c30 / 4.0 if c30 != 0 else 0.01
        if abs(monthly_weekly_pace) > 0.1:
            # Ratio: how much faster is this week vs average week in the month
            growth_raw.append(weekly_pace / monthly_weekly_pace)
        else:
            # Monthly change is near zero — use raw 7d as acceleration
            growth_raw.append(weekly_pace)

    # Score each factor 0-100 via percentile ranking
    beta_scores = _inverse_percentile_rank(beta_raw)        # Low beta = high score
    size_scores = _inverse_percentile_rank(size_raw)         # Small cap = high score
    value_scores = _percentile_rank(value_raw)               # High turnover = high score
    momentum_scores = _percentile_rank(momentum_raw)         # High momentum = high score
    growth_scores = _percentile_rank(growth_raw)             # High growth = high score

    factor_names = list(FIVE_FACTOR_WEIGHTS.keys())
    result = {}
    for i, t in enumerate(tickers):
        mc = raw["market_caps"][i]
        has_data = mc > 0 and raw["volumes"][i] > 0
        result[t] = {
            factor_names[0]: beta_scores[i],
            factor_names[1]: size_scores[i],
            factor_names[2]: value_scores[i],
            factor_names[3]: momentum_scores[i],
            factor_names[4]: growth_scores[i],
            "_raw": {
                "market_cap": raw["market_caps"][i],
                "volume_24h": raw["volumes"][i],
                "vol_mcap_ratio": raw["vol_mcap_ratios"][i],
                "change_7d": raw["change_7d"][i],
                "change_30d": raw["change_30d"][i],
                "change_24h": raw["change_24h"][i],
                "ath_drawdown": raw["ath_drawdowns"][i],
                "momentum_raw": momentum_raw[i],
                "growth_raw": growth_raw[i],
            },
            "_data_missing": not has_data,
        }
    return result


def compute_live_ten_factor_scores(tickers: list[str]) -> dict[str, dict[str, float]]:
    """
    Compute 10-factor fundamental scores using DefiLlama (fees, TVL, revenue)
    + CoinGecko (market cap, FDV, price momentum) data.

    Mirrors nickel-ls-rv VA signals (long orientation = high score is good):
      Value (P/S)          — lower P/S = better value (DefiLlama fees / CG mcap)
      Fee Momentum         — positive fee trend = good (DefiLlama fee change)
      TVL Health           — growing TVL = healthy (DefiLlama TVL change)
      Revenue Quality      — high holder rev / fees = good capture (DefiLlama)
      Usage Growth         — positive volume/price momentum (CoinGecko 7d)
      Risk (Low Vol)       — lower volatility = safer (CoinGecko 30d abs change)
      Dilution Safety      — low FDV/MCap = less dilution risk (DefiLlama/CG)
      Float Quality        — mature float, low supply growth (CoinGecko)
      Smart Money          — positive 30d momentum = SM accumulating (CG proxy)
      Developer Momentum   — 7d acceleration vs 30d trend (CG proxy)
    """
    if not tickers:
        return {}

    raw = _get_raw_market_vectors(tickers)
    factor_names = list(TEN_FACTOR_WEIGHTS.keys())

    # ── Collect raw values per factor ──
    value_raw = []       # P/S: lower is better value
    fee_mom_raw = []     # fee momentum %: higher is better
    tvl_raw = []         # TVL change %: higher is better
    rev_qual_raw = []    # revenue capture ratio: higher is better
    usage_raw = []       # 7d change: higher is better
    risk_raw = []        # abs 30d change: lower is better
    dilution_raw = []    # FDV/MCap: lower is better (safer)
    supply_raw = []      # supply delta: contracting = higher score
    smart_raw = []       # funding rate + OI: higher is better
    dev_raw = []         # 7d acceleration: higher is better

    for i, t in enumerate(tickers):
        dl = get_defillama_info(t)
        cg = get_market_info(t)
        mc = raw["market_caps"][i]

        # Value (P/S) — use DefiLlama fees if available, else vol/mcap proxy
        if dl and dl.get("fees_30d", 0) > 0:
            annual_fees = dl["fees_30d"] * 12
            ps = mc / annual_fees if annual_fees > 0 else 999
            value_raw.append(ps)
        else:
            # Fallback: vol/mcap as value proxy (higher turnover = cheaper)
            value_raw.append(1 / raw["vol_mcap_ratios"][i] if raw["vol_mcap_ratios"][i] > 0 else 999)

        # Fee Momentum — DefiLlama fee trend, fallback to 7d price change
        if dl and "fee_momentum" in dl:
            fee_mom_raw.append(dl["fee_momentum"])
        else:
            fee_mom_raw.append(raw["change_7d"][i])

        # TVL Health — DefiLlama TVL 7d change, fallback to inverse ATH drawdown
        if dl and "tvl_change_7d" in dl:
            tvl_raw.append(dl["tvl_change_7d"])
        else:
            tvl_raw.append(100 - raw["ath_drawdowns"][i])

        # Revenue Quality — DefiLlama rev capture ratio, fallback to vol/mcap
        if dl and "revenue_capture" in dl and dl["revenue_capture"] > 0:
            rev_qual_raw.append(dl["revenue_capture"] * 100)  # 0-100 scale
        else:
            rev_qual_raw.append(raw["vol_mcap_ratios"][i] * 100)

        # Usage Growth — 7d price change as usage proxy
        usage_raw.append(raw["change_7d"][i])

        # Risk (Low Vol) — absolute 30d change (lower = safer)
        risk_raw.append(abs(raw["change_30d"][i]))

        # Dilution Safety — FDV/MCap from CoinGecko (universal coverage)
        dilution_raw.append(raw["fdv_mcap_ratios"][i])

        # Supply Health — contracting supply = bullish (burns, staking lockup)
        supply_raw.append(-raw["supply_deltas"][i])  # negative delta = good → invert

        # Smart Money — perp funding rate (positive = longs paying = bullish conviction)
        # Falls back to 30d momentum if Binance data unavailable
        fr = raw["funding_rates"][i]
        if fr != 0:
            smart_raw.append(fr * 10000)  # scale: 0.0001 → 1.0
        else:
            smart_raw.append(raw["change_30d"][i] / 10)  # weak fallback

        # Developer Momentum — 7d acceleration vs 30d
        c7 = raw["change_7d"][i]
        c30 = raw["change_30d"][i]
        dev_raw.append(c7 - c30 * 0.25)

    # ── Percentile rank each factor ──
    scores_list = [
        _inverse_percentile_rank(value_raw),     # Low P/S = high score
        _percentile_rank(fee_mom_raw),            # High fee growth = high score
        _percentile_rank(tvl_raw),                # Growing TVL = high score
        _percentile_rank(rev_qual_raw),           # High rev capture = high score
        _percentile_rank(usage_raw),              # High usage growth = high score
        _inverse_percentile_rank(risk_raw),       # Low vol = high score
        _inverse_percentile_rank(dilution_raw),   # Low dilution = high score
        _percentile_rank(supply_raw),             # Contracting supply = high score
        _percentile_rank(smart_raw),              # Positive funding = high score
        _percentile_rank(dev_raw),                # High dev momentum = high score
    ]

    result = {}
    for i, t in enumerate(tickers):
        result[t] = {factor_names[j]: scores_list[j][i] for j in range(10)}
    return result


# ── Composite score computation ────────────────────────────────────────

def compute_five_factor_scores(profile: str, tickers: list[str]) -> dict[str, float]:
    """Returns {ticker: composite_score} for allocation weighting."""
    individual = compute_live_five_factor_scores(tickers)
    composites = {}
    for t in tickers:
        scores = individual.get(t, {})
        composite = 0
        for factor, weights in FIVE_FACTOR_WEIGHTS.items():
            w = weights.get(profile, 0)
            s = scores.get(factor, 50)
            composite += w * s
        composites[t] = composite
    return composites


def compute_ten_factor_scores(profile: str, tickers: list[str]) -> dict[str, float]:
    """Returns {ticker: composite_score} for allocation weighting."""
    individual = compute_live_ten_factor_scores(tickers)
    composites = {}
    for t in tickers:
        scores = individual.get(t, {})
        composite = 0
        for factor, weights in TEN_FACTOR_WEIGHTS.items():
            w = weights.get(profile, 0)
            s = scores.get(factor, 50)
            composite += w * s
        composites[t] = composite
    return composites


# ── Detail views for Factor Scores / Fundamentals tabs ─────────────────

def five_factor_detail(profile: str, tickers: list[str]) -> list[dict]:
    individual = compute_live_five_factor_scores(tickers)
    results = []
    for t in tickers:
        scores = individual.get(t, {})
        row = {"ticker": t, "name": ASSET_BY_TICKER.get(t, {}).get("name", t)}
        composite = 0
        for factor, weights in FIVE_FACTOR_WEIGHTS.items():
            s = scores.get(factor, 50)
            row[factor] = round(s, 1)
            composite += weights.get(profile, 0) * s
        row["composite"] = round(composite, 1)
        row["_raw"] = scores.get("_raw", {})
        row["_data_missing"] = scores.get("_data_missing", False)
        results.append(row)
    results.sort(key=lambda x: -x["composite"])
    return results


def ten_factor_detail(profile: str, tickers: list[str]) -> list[dict]:
    individual = compute_live_ten_factor_scores(tickers)
    results = []
    for t in tickers:
        scores = individual.get(t, {})
        row = {"ticker": t, "name": ASSET_BY_TICKER.get(t, {}).get("name", t)}
        composite = 0
        for factor, weights in TEN_FACTOR_WEIGHTS.items():
            s = scores.get(factor, 50)
            row[factor] = round(s, 1)
            composite += weights.get(profile, 0) * s
        row["composite"] = round(composite, 1)
        results.append(row)
    results.sort(key=lambda x: -x["composite"])
    return results


# ── Token scorecard ────────────────────────────────────────────────────

def token_scorecard(ticker: str, profile: str, universe_tickers: list[str] = None) -> dict:
    """Build a complete scorecard for a single token."""
    asset = ASSET_BY_TICKER.get(ticker, {})
    info = get_market_info(ticker) or {}
    bn = get_binance_info(ticker) or {}
    dl = get_defillama_info(ticker) or {}

    # Market data
    mc = info.get("market_cap") or 0
    market = {
        "price": get_price(ticker),
        "market_cap": mc,
        "volume_24h": info.get("total_volume") or 0,
        "change_24h": info.get("price_change_24h") or 0,
        "change_7d": info.get("price_change_7d") or 0,
        "change_30d": info.get("price_change_30d") or 0,
        "ath": info.get("ath") or 0,
        "ath_pct": round(100 + (info.get("ath_change_pct") or -100), 1),
        "vol_mcap": round(info.get("total_volume", 0) / mc, 4) if mc > 0 else 0,
        "fdv_mcap": round(info.get("fdv_mcap_ratio") or 0, 2),
        "funding_rate": bn.get("funding_rate"),
        "open_interest_usd": bn.get("open_interest_usd"),
    }

    # Factor scores (5-factor)
    if not universe_tickers:
        universe_tickers = [a["ticker"] for a in ASSET_UNIVERSE if a["tier"] not in ("Fixed",)]
    # Filter to exclude stablecoins
    score_tickers = [t for t in universe_tickers if t not in ("USDC", "EURC", "PAXG")]
    if ticker not in score_tickers:
        score_tickers.append(ticker)

    five_scores = compute_live_five_factor_scores(score_tickers)
    ten_scores = compute_live_ten_factor_scores(score_tickers)
    token_five = five_scores.get(ticker, {})
    token_ten = ten_scores.get(ticker, {})

    # Compute medians for radar comparison
    factor_names_5 = list(FIVE_FACTOR_WEIGHTS.keys())
    medians_5 = {}
    for f in factor_names_5:
        vals = [five_scores[t].get(f, 50) for t in score_tickers if t in five_scores]
        medians_5[f] = sorted(vals)[len(vals) // 2] if vals else 50

    # Composite
    composite_5 = sum(token_five.get(f, 50) * FIVE_FACTOR_WEIGHTS[f].get(profile, 0) for f in factor_names_5)

    return {
        "ticker": ticker,
        "name": asset.get("name", ticker),
        "category": asset.get("category", ""),
        "tier": asset.get("tier", ""),
        "risk_tier": asset.get("risk_tier", ""),
        "market": market,
        "five_factor": {f: round(token_five.get(f, 50), 1) for f in factor_names_5},
        "five_medians": {f: round(medians_5[f], 1) for f in factor_names_5},
        "composite_5": round(composite_5, 1),
        "factor_names_5": factor_names_5,
    }


# ── Allocation engine (unchanged) ──────────────────────────────────────

def compute_allocations(profile: str, universe: str, mode: str = "Standard") -> list[dict]:
    tickers = get_universe_tickers(universe)
    results = []
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

    crypto_tickers = [t for t in tickers if t not in FIXED_STRATEGIC]

    tier_groups: dict[str, list[str]] = {}
    for t in crypto_tickers:
        atier = get_alloc_tier(t)
        tier_groups.setdefault(atier, []).append(t)

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
            tier_scores = {t: max(scores.get(t, 50), 1) for t in tier_tickers}
            total_score = sum(tier_scores.values())
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

    tier_order = {"Fixed": 0, "Store of Value": 1, "Large Cap": 2, "Mid Cap": 3, "Small Cap": 4}
    results.sort(key=lambda x: (tier_order.get(x["tier"], 5), -x["alloc_pct"]))
    return results


# ── Portfolio, DCA, Rebalancing, P&L (unchanged) ──────────────────────

def compute_portfolio(profile: str, universe: str, mode: str, portfolio_value: float) -> list[dict]:
    allocs = compute_allocations(profile, universe, mode)
    for a in allocs:
        a["dollar_amount"] = portfolio_value * a["alloc_pct"]
        a["price"] = get_price(a["ticker"])
    return allocs


def compute_dca(
    profile: str, universe: str, mode: str,
    monthly_amount: float, dca_scope: str, horizon_months: int, min_order: float
) -> list[dict]:
    allocs = compute_allocations(profile, universe, mode)
    scope_def = DCA_SCOPES.get(dca_scope, "all")
    if isinstance(scope_def, list):
        eligible = [a for a in allocs if a["ticker"] in scope_def]
    else:
        eligible = [a for a in allocs if a["ticker"] not in ("USDC", "EURC")]

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
    for pos in positions:
        ticker = pos.get("ticker", "")
        qty = pos.get("quantity", 0)
        entry_price = pos.get("entry_price", 0)
        current_price = get_price(ticker) or 0
        cost_basis = qty * entry_price
        current_value = qty * current_price
        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0
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


def compute_rebalance_pnl(
    profile: str, universe: str, mode: str,
    portfolio_value: float, positions: dict,
) -> list[dict]:
    """Combined rebalance + P&L: one row per asset with target, current, entry, live price, P&L, and action."""
    allocs = compute_allocations(profile, universe, mode)
    results = []
    total_target = 0
    total_current = 0
    total_cost = 0
    total_value = 0

    for a in allocs:
        ticker = a["ticker"]
        target_usd = portfolio_value * a["alloc_pct"]
        pos = positions.get(ticker, {})
        current_usd = pos.get("current_usd", 0)
        entry_price = pos.get("entry_price", 0)
        live_price = get_price(ticker) or 0

        # P&L from entry price
        if entry_price > 0 and current_usd > 0:
            qty = current_usd / entry_price
            current_value = qty * live_price
            pnl = current_value - current_usd
            pnl_pct = (pnl / current_usd * 100) if current_usd else 0
        else:
            current_value = current_usd
            pnl = 0
            pnl_pct = 0

        diff = target_usd - current_usd
        action = ""
        if abs(diff) > 1:
            action = "BUY" if diff > 0 else "SELL"

        total_target += target_usd
        total_current += current_usd
        total_cost += current_usd
        total_value += current_value

        results.append({
            "ticker": ticker,
            "name": a["name"],
            "tier": a["tier"],
            "target_pct": a["alloc_pct"],
            "target_usd": target_usd,
            "current_usd": current_usd,
            "entry_price": entry_price,
            "live_price": live_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "difference": diff,
            "action": action,
        })

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0

    return {
        "rows": results,
        "total_target": total_target,
        "total_current": total_current,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "net_rebalance": total_target - total_current,
    }
