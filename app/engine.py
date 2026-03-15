"""
Allocation engine — factor scoring, DCA planner, rebalancer, P&L calculator.

Factor scores are computed from live CoinGecko market data rather than
static defaults. Each factor is scored 0-100 using percentile ranking
across the universe.
"""
import math
from app.data import (
    ASSET_UNIVERSE, ASSET_BY_TICKER, ASSET_UNIVERSES,
    FIXED_STRATEGIC, TIER_ALLOCATIONS, RISK_TILT_PARAMETERS,
    FIVE_FACTOR_WEIGHTS, TEN_FACTOR_WEIGHTS,
    DCA_SCOPES, get_alloc_tier,
)
from app.market_data import get_price, get_market_info, get_defillama_info


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

    for t in tickers:
        info = get_market_info(t)
        if info:
            mc = info.get("market_cap") or 0
            vol = info.get("total_volume") or 0
            c7d = info.get("price_change_7d") or 0
            c30d = info.get("price_change_30d") or 0
            c24h = info.get("price_change_24h") or 0
            ath_dd = abs(info.get("ath_change_pct") or -50)
        else:
            mc = vol = c7d = c30d = c24h = 0
            ath_dd = 50

        market_caps.append(mc)
        volumes.append(vol)
        change_7d.append(c7d)
        change_30d.append(c30d)
        change_24h.append(c24h)
        ath_drawdowns.append(ath_dd)
        vol_mcap_ratios.append(vol / mc if mc > 0 else 0)

    return {
        "market_caps": market_caps,
        "volumes": volumes,
        "change_7d": change_7d,
        "change_30d": change_30d,
        "change_24h": change_24h,
        "ath_drawdowns": ath_drawdowns,
        "vol_mcap_ratios": vol_mcap_ratios,
    }


def compute_live_five_factor_scores(tickers: list[str]) -> dict[str, dict[str, float]]:
    """
    Compute 5-factor scores from CoinGecko data:
      Market Beta (Low B)  — lower 30d absolute change = lower beta = higher score
      Size - SMB           — smaller market cap = higher score
      Value (MC/Fees)      — higher volume/mcap ratio = better value
      Momentum (Vol-Adj)   — higher 7d+30d momentum = higher score
      Growth (Fee+DAU D)   — higher 7d change relative to 30d = faster growth
    """
    if not tickers:
        return {}

    raw = _get_raw_market_vectors(tickers)

    # Compute raw factor values
    beta_raw = [abs(c) for c in raw["change_30d"]]  # absolute 30d move as beta proxy
    size_raw = raw["market_caps"]
    value_raw = raw["vol_mcap_ratios"]
    momentum_raw = [c7 + c30 for c7, c30 in zip(raw["change_7d"], raw["change_30d"])]
    growth_raw = []
    for c7, c30 in zip(raw["change_7d"], raw["change_30d"]):
        # Growth = 7d acceleration vs 30d (if 7d is positive while 30d less so)
        growth_raw.append(c7 - c30 * 0.25 if c30 != 0 else c7)

    # Score each factor 0-100 via percentile ranking
    beta_scores = _inverse_percentile_rank(beta_raw)        # Low beta = high score
    size_scores = _inverse_percentile_rank(size_raw)         # Small cap = high score
    value_scores = _percentile_rank(value_raw)               # High turnover = high score
    momentum_scores = _percentile_rank(momentum_raw)         # High momentum = high score
    growth_scores = _percentile_rank(growth_raw)             # High growth = high score

    factor_names = list(FIVE_FACTOR_WEIGHTS.keys())
    result = {}
    for i, t in enumerate(tickers):
        result[t] = {
            factor_names[0]: beta_scores[i],
            factor_names[1]: size_scores[i],
            factor_names[2]: value_scores[i],
            factor_names[3]: momentum_scores[i],
            factor_names[4]: growth_scores[i],
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
    float_raw = []       # higher is better quality
    smart_raw = []       # 30d momentum: higher is better
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

        # Dilution Safety — FDV/MCap ratio (lower = safer)
        if dl and dl.get("fdv_mcap_ratio", 0) > 0:
            dilution_raw.append(dl["fdv_mcap_ratio"])
        elif cg and cg.get("market_cap", 0) > 0:
            # Use ATH drawdown as dilution proxy (closer to ATH = less diluted)
            dilution_raw.append(raw["ath_drawdowns"][i] / 10)  # normalize
        else:
            dilution_raw.append(2.0)  # neutral

        # Float Quality — inverse of supply growth / dilution
        # Higher vol/mcap = more liquid float
        float_raw.append(raw["vol_mcap_ratios"][i])

        # Smart Money — 30d momentum (proxy: SM follows strong trends)
        smart_raw.append(raw["change_30d"][i])

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
        _percentile_rank(float_raw),              # High float quality = high score
        _percentile_rank(smart_raw),              # Positive SM trend = high score
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
