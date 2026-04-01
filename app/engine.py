"""
Allocation engine — factor scoring, DCA planner, rebalancer, P&L calculator.

5-Factor model: percentile-ranked market factors (beta, size, value, momentum, growth).
VA model: nickel-ls-rv aligned value accrual signals, clamped [-1,+1] then scaled to [0,100].
"""
import math
from app.data import (
    ASSET_UNIVERSE, ASSET_BY_TICKER, ASSET_UNIVERSES,
    FIXED_STRATEGIC, TIER_ALLOCATIONS,
    FIVE_FACTOR_WEIGHTS, TEN_FACTOR_WEIGHTS, VA_FACTOR_WEIGHTS,
    VA_FDV_MCAP_NEUTRAL, VA_SUPPLY_DELTA_NORMALIZE,
    VA_BUYBACK_NEUTRAL, VA_BUYBACK_MAX,
    VA_FEE_MOMENTUM_NORMALIZE, VA_FDV_FEES_NEUTRAL, VA_FDV_TVL_NEUTRAL,
    VA_REGISTRY, VA_GATE_MIN_FEES_30D, VA_NO_ACCRUAL_FLOOR, VA_NO_ACCRUAL_MCAP_FLOOR,
    DCA_SCOPES, get_alloc_tier,
    SECTOR_VA_PROFILES, CATEGORY_TO_VA_PROFILE, VA_PROFILE_OVERRIDES,
)
from app.market_data import (
    get_price, get_market_info, get_defillama_info, get_binance_info, get_supply_delta_pct,
    get_defillama_protocol_info, get_messari_info, get_dev_info,
)


def get_universe_tickers(universe_name: str) -> list[str]:
    from app.data import ASSET_UNIVERSES
    explicit = ASSET_UNIVERSES.get(universe_name)
    if isinstance(explicit, list):
        return explicit
    if "Extended" in universe_name:
        return [a["ticker"] for a in ASSET_UNIVERSE]
    if "Long" in universe_name:
        return [a["ticker"] for a in ASSET_UNIVERSE if a["tier"] not in ("Short",)]
    return [a["ticker"] for a in ASSET_UNIVERSE]


# ── Percentile scoring helper ──────────────────────────────────────────

def _percentile_rank(values: list[float]) -> list[float]:
    """Convert raw values to 0-100 percentile scores. Higher value = higher score.
    Tied values receive the average rank (fractional ranking)."""
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [50.0]
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * n
    # Group ties and assign average rank
    i = 0
    while i < n:
        j = i
        while j < n and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = sum(range(i, j)) / (j - i)
        for k in range(i, j):
            orig_idx = indexed[k][0]
            ranks[orig_idx] = round(avg_rank / (n - 1) * 100, 1)
        i = j
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


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _signal_to_score(signal: float) -> float:
    """Convert a [-1, +1] VA signal to [0, 100] display score. 0→50, +1→100, -1→0."""
    return round(_clamp(signal) * 50 + 50, 1)


def compute_live_ten_factor_scores(tickers: list[str]) -> dict[str, dict[str, float]]:
    """
    Compute Value Accrual (VA) scores aligned with nickel-ls-rv three-pillar framework.
    Each signal is computed using the same formula and normalization constants as the
    live trading bot, clamped to [-1, +1], then scaled to [0, 100] for display.

    7 signals (unlock excluded — no Messari data):
      Dilution          — (neutral - FDV/MCap) / (neutral - 1), neutral=2.0
      Supply Delta      — -blended_delta / 3%, contracting = positive
      Buyback Intensity — (BI% - 5%) / 15%, annualized holder yield
      Rev Capture       — holders_revenue / fees_30d, clamped
      Fee Momentum      — (fee_mom - median) / 50%, market-relative
      FDV / Fees        — log-scaled P/E, neutral=100
      FDV / TVL         — log-scaled capital efficiency, neutral=10
    """
    if not tickers:
        return {}

    raw = _get_raw_market_vectors(tickers)
    factor_names = list(VA_FACTOR_WEIGHTS.keys())

    # Collect fee momentum values across universe to compute median (market-relative)
    all_fee_moms = []
    for t in tickers:
        dl = get_defillama_info(t)
        if dl and "fee_momentum" in dl:
            all_fee_moms.append(dl["fee_momentum"])
    median_fee_mom = sorted(all_fee_moms)[len(all_fee_moms) // 2] if all_fee_moms else 0

    result = {}
    for i, t in enumerate(tickers):
        dl = get_defillama_info(t) or {}
        mc = raw["market_caps"][i]
        fdv = mc * raw["fdv_mcap_ratios"][i] if raw["fdv_mcap_ratios"][i] > 0 else mc

        # ── 1. Dilution: (neutral - FDV/MCap) / (neutral - 1) ──
        fdv_mcap = raw["fdv_mcap_ratios"][i] if raw["fdv_mcap_ratios"][i] > 0 else VA_FDV_MCAP_NEUTRAL
        dilution_sig = _clamp((VA_FDV_MCAP_NEUTRAL - fdv_mcap) / (VA_FDV_MCAP_NEUTRAL - 1.0))

        # ── 2. Supply Delta: -delta / normalize ──
        sd = raw["supply_deltas"][i]
        supply_sig = _clamp(-sd / VA_SUPPLY_DELTA_NORMALIZE) if sd != 0 else 0.0

        # ── 3. Buyback Intensity: annualized holder yield vs neutral/max ──
        holders_rev = dl.get("revenue_30d", 0)
        free_float_mc = mc  # approximate (no float data without Messari)
        if holders_rev > 0 and free_float_mc > 0:
            bi_pct = (holders_rev * 12) / free_float_mc * 100
            if bi_pct >= VA_BUYBACK_NEUTRAL:
                buyback_sig = _clamp((bi_pct - VA_BUYBACK_NEUTRAL) / (VA_BUYBACK_MAX - VA_BUYBACK_NEUTRAL))
            else:
                buyback_sig = _clamp((bi_pct - VA_BUYBACK_NEUTRAL) / VA_BUYBACK_NEUTRAL)
        else:
            buyback_sig = 0.0  # no data = neutral

        # ── 4. Rev Capture: holders_revenue / fees ──
        fees_30d = dl.get("fees_30d", 0)
        if fees_30d > 0 and holders_rev > 0:
            rev_capture_sig = _clamp(holders_rev / fees_30d)
        else:
            rev_capture_sig = 0.0

        # ── 5. Fee Momentum: market-relative, normalized ──
        if dl and "fee_momentum" in dl:
            relative_mom = dl["fee_momentum"] - median_fee_mom
            fee_mom_sig = _clamp(relative_mom / VA_FEE_MOMENTUM_NORMALIZE)
        else:
            fee_mom_sig = 0.0  # no data = neutral

        # ── 6. FDV / Fees (P/E): log-scaled, neutral=100 ──
        if fees_30d > 0 and fdv > 0:
            annual_fees = fees_30d * 12
            pe = fdv / annual_fees if annual_fees > 0 else 9999
            if pe > 0:
                log_pe = math.log(pe)
                log_neutral = math.log(VA_FDV_FEES_NEUTRAL)
                fdv_fees_sig = _clamp((log_neutral - log_pe) / log_neutral)
            else:
                fdv_fees_sig = 1.0
        else:
            fdv_fees_sig = -1.0  # no fees = worst

        # ── 7. FDV / TVL: log-scaled, neutral=10 ──
        tvl = dl.get("tvl", 0)
        if tvl > 0 and fdv > 0:
            ratio = fdv / tvl
            if ratio > 0:
                log_ratio = math.log(ratio)
                log_neutral = math.log(VA_FDV_TVL_NEUTRAL)
                fdv_tvl_sig = _clamp((log_neutral - log_ratio) / log_neutral)
            else:
                fdv_tvl_sig = 1.0
        else:
            fdv_tvl_sig = 0.0  # no TVL = neutral

        # ── VA Registry gating (nickel-ls-rv aligned) ──
        registry = VA_REGISTRY.get(t, {})
        mechanism = registry.get("mechanism", "unknown")
        has_accrual_mechanism = mechanism not in ("none", "unknown")

        # Gate: If mechanism is "none" → zero out buyback and rev_capture
        if mechanism == "none":
            buyback_sig = 0.0
            rev_capture_sig = 0.0

        # Gate 1: Extractive protocol — has fees but no holder revenue and no known mechanism
        has_meaningful_fees = fees_30d >= VA_GATE_MIN_FEES_30D
        has_holder_revenue = holders_rev > 0
        if has_meaningful_fees and not has_holder_revenue and not has_accrual_mechanism:
            dilution_sig = min(dilution_sig, 0.0)
            supply_sig = min(supply_sig, 0.0)
            buyback_sig = min(buyback_sig, 0.0)
            rev_capture_sig = min(rev_capture_sig, 0.0)
            fee_mom_sig = min(fee_mom_sig, 0.0)
            fdv_fees_sig = min(fdv_fees_sig, 0.0)
            fdv_tvl_sig = min(fdv_tvl_sig, 0.0)

        # Gate 2: No-accrual floor for large caps ($1B+)
        if mechanism == "none" and mc >= VA_NO_ACCRUAL_MCAP_FLOOR:
            buyback_sig = VA_NO_ACCRUAL_FLOOR
            rev_capture_sig = VA_NO_ACCRUAL_FLOOR
            if abs(fee_mom_sig) < 0.05:
                fee_mom_sig = VA_NO_ACCRUAL_FLOOR

        # Gate 3: Fee momentum haircut if no revenue mechanism
        if fee_mom_sig > 0 and not has_accrual_mechanism:
            fee_mom_sig *= 0.2

        # Store as 0-100 scores + raw signals for the data tab
        result[t] = {
            factor_names[0]: _signal_to_score(dilution_sig),
            factor_names[1]: _signal_to_score(supply_sig),
            factor_names[2]: _signal_to_score(buyback_sig),
            factor_names[3]: _signal_to_score(rev_capture_sig),
            factor_names[4]: _signal_to_score(fee_mom_sig),
            factor_names[5]: _signal_to_score(fdv_fees_sig),
            factor_names[6]: _signal_to_score(fdv_tvl_sig),
            "_va_signals": {
                "dilution": round(dilution_sig, 3),
                "supply_delta": round(supply_sig, 3),
                "buyback": round(buyback_sig, 3),
                "rev_capture": round(rev_capture_sig, 3),
                "fee_momentum": round(fee_mom_sig, 3),
                "fdv_fees": round(fdv_fees_sig, 3),
                "fdv_tvl": round(fdv_tvl_sig, 3),
            },
            "_va_raw": {
                "fdv_mcap": round(fdv_mcap, 2),
                "supply_delta_pct": round(sd, 3),
                "buyback_yield_pct": round((holders_rev * 12) / free_float_mc * 100, 2) if holders_rev > 0 and free_float_mc > 0 else 0,
                "rev_capture_ratio": round(holders_rev / fees_30d, 3) if fees_30d > 0 and holders_rev > 0 else 0,
                "fee_momentum_pct": round(dl.get("fee_momentum", 0), 1),
                "pe_ratio": round(fdv / (fees_30d * 12), 1) if fees_30d > 0 else None,
                "fdv_tvl_ratio": round(fdv / tvl, 2) if tvl > 0 else None,
                "fees_30d": fees_30d,
                "holders_revenue_30d": holders_rev,
                "tvl": tvl,
                "mechanism": mechanism,
                "has_accrual": has_accrual_mechanism,
            },
        }
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


def _get_va_weights_for_ticker(ticker: str, profile: str) -> dict[str, float]:
    """Get sector-aware VA weights for a token. Returns {factor_name: weight}."""
    # Check per-token override first
    profile_key = VA_PROFILE_OVERRIDES.get(ticker)
    if not profile_key:
        # Look up category → sector profile
        asset = ASSET_BY_TICKER.get(ticker, {})
        category = asset.get("category", "")
        profile_key = CATEGORY_TO_VA_PROFILE.get(category)

    if profile_key and profile_key in SECTOR_VA_PROFILES:
        # Use sector-specific weights (same for all risk profiles)
        return SECTOR_VA_PROFILES[profile_key]
    else:
        # Use default profile-specific weights
        return {factor: weights.get(profile, 0) for factor, weights in VA_FACTOR_WEIGHTS.items()}


def compute_ten_factor_scores(profile: str, tickers: list[str]) -> dict[str, float]:
    """Returns {ticker: composite_score} for allocation weighting. Uses sector-aware VA weights."""
    individual = compute_live_ten_factor_scores(tickers)
    composites = {}
    for t in tickers:
        scores = individual.get(t, {})
        weights = _get_va_weights_for_ticker(t, profile)
        composite = 0
        for factor, w in weights.items():
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
    # Also get raw market data for charts/underlying data view
    five_individual = compute_live_five_factor_scores(tickers)
    results = []
    for t in tickers:
        scores = individual.get(t, {})
        row = {"ticker": t, "name": ASSET_BY_TICKER.get(t, {}).get("name", t)}
        # Sector-aware VA weights
        weights = _get_va_weights_for_ticker(t, profile)
        composite = 0
        for factor, w in weights.items():
            s = scores.get(factor, 50)
            row[factor] = round(s, 1)
            composite += w * s
        row["composite"] = round(composite, 1)
        # Record which sector profile was used
        asset = ASSET_BY_TICKER.get(t, {})
        sector_key = VA_PROFILE_OVERRIDES.get(t) or CATEGORY_TO_VA_PROFILE.get(asset.get("category", ""))
        row["_va_profile"] = sector_key or "default"
        row["_raw"] = five_individual.get(t, {}).get("_raw", {})
        row["_data_missing"] = five_individual.get(t, {}).get("_data_missing", False)
        row["_va_signals"] = scores.get("_va_signals", {})
        row["_va_raw"] = scores.get("_va_raw", {})
        results.append(row)
    results.sort(key=lambda x: -x["composite"])
    return results


# ── P3 (Protocol Performance) Pillar ──────────────────────────────────

P3_FACTOR_WEIGHTS = {
    "TVL Growth 7d":      {"Conservative": 0.40, "Balanced": 0.35, "Growth": 0.30, "Aggressive": 0.25},
    "Borrowed Growth 7d": {"Conservative": 0.20, "Balanced": 0.20, "Growth": 0.15, "Aggressive": 0.10},
    "Fee Growth 7d":      {"Conservative": 0.25, "Balanced": 0.25, "Growth": 0.30, "Aggressive": 0.35},
    "Network Activity":   {"Conservative": 0.15, "Balanced": 0.20, "Growth": 0.25, "Aggressive": 0.30},
}


def compute_p3_scores(tickers: list[str]) -> dict[str, dict]:
    """Protocol Performance pillar: TVL growth, borrowed growth, fee growth, network activity.
    Each signal normalized [-1, +1] → [0, 100]. Returns {ticker: {sub_scores + composite}}."""
    if not tickers:
        return {}

    result = {}
    for t in tickers:
        proto = get_defillama_protocol_info(t) or {}
        messari = get_messari_info(t) or {}
        dl = get_defillama_info(t) or {}

        signals = {}
        n_signals = 0

        # 1. TVL Growth 7d — from protocol detail
        tvl_g = proto.get("tvl_growth_7d")
        if tvl_g is not None:
            signals["tvl_growth_7d"] = _clamp(tvl_g / 0.10)  # ±10% = max signal
            n_signals += 1
        else:
            # Fallback to aggregate DeFiLlama tvl_change_7d
            tvl_c = dl.get("tvl_change_7d")
            if tvl_c and tvl_c != 0:
                signals["tvl_growth_7d"] = _clamp(tvl_c / 10.0)  # tvl_change_7d is already %
                n_signals += 1
            else:
                signals["tvl_growth_7d"] = 0.0

        # 2. Borrowed Growth 7d — lending protocols only
        borrowed = proto.get("borrowed_current", 0)
        if borrowed and borrowed > 0:
            # Use TVL growth as proxy for borrowed growth (both move together for lending)
            signals["borrowed_growth_7d"] = signals["tvl_growth_7d"]
            n_signals += 1
        else:
            signals["borrowed_growth_7d"] = 0.0

        # 3. Fee Growth 7d — from DeFiLlama fee momentum
        fee_mom = dl.get("fee_momentum", 0)
        if fee_mom != 0:
            signals["fee_growth_7d"] = _clamp(fee_mom / 50.0)  # ±50% = max signal
            n_signals += 1
        else:
            signals["fee_growth_7d"] = 0.0

        # 4. Network Activity — from Messari
        active_addrs = messari.get("active_addresses", 0)
        txn_count = messari.get("txn_count", 0)
        if active_addrs > 0 or txn_count > 0:
            # Normalize: 100K active addresses = max signal
            addr_sig = _clamp(active_addrs / 100_000) if active_addrs else 0
            # Normalize: 1M daily txns = max signal
            txn_sig = _clamp(txn_count / 1_000_000) if txn_count else 0
            signals["network_activity"] = _clamp((addr_sig + txn_sig) / 2)
            n_signals += 1
        else:
            signals["network_activity"] = 0.0

        # Convert to scores
        scores = {name: _signal_to_score(sig) for name, sig in signals.items()}
        scores["_n_signals"] = n_signals
        scores["_has_p3"] = n_signals > 0

        result[t] = scores

    return result


def compute_p3_composite(profile: str, tickers: list[str]) -> dict[str, float]:
    """Returns {ticker: p3_composite_score}."""
    p3 = compute_p3_scores(tickers)
    composites = {}
    p3_names = list(P3_FACTOR_WEIGHTS.keys())
    signal_keys = ["tvl_growth_7d", "borrowed_growth_7d", "fee_growth_7d", "network_activity"]
    for t in tickers:
        scores = p3.get(t, {})
        composite = 0
        total_w = 0
        for p3_name, sig_key in zip(p3_names, signal_keys):
            s = scores.get(sig_key, 50)
            w = P3_FACTOR_WEIGHTS[p3_name].get(profile, 0)
            composite += w * s
            total_w += w
        composites[t] = composite / total_w * total_w if total_w > 0 else 50.0
    return composites


# ── Red Flag / Conviction Quality Filter ─────────────────────────────

def compute_red_flag_scores(tickers: list[str]) -> dict[str, dict]:
    """Detect value-extractive tokens. Score 0-100 where 100 = worst red flags.
    Inverted nickel-ls-rv conviction scoring for long-only use.

    4 pillars:
      1. Dilution Overhang (30%): High FDV/MCap + low float
      2. Revenue Void (25%): No fees, no holder value
      3. Valuation Absurdity (25%): Extreme PE, thin volume
      4. Unlock Pressure (20%): Supply inflation
    """
    if not tickers:
        return {}

    result = {}
    for t in tickers:
        info = get_market_info(t) or {}
        dl = get_defillama_info(t) or {}
        mc = info.get("market_cap") or 0
        vol = info.get("total_volume") or 0
        fdv_ratio = info.get("fdv_mcap_ratio") or 1.0
        fees_30d = dl.get("fees_30d", 0)
        holders_rev = dl.get("revenue_30d", 0)
        sd = get_supply_delta_pct(t) or 0
        registry = VA_REGISTRY.get(t, {})
        mechanism = registry.get("mechanism", "unknown")

        # 1. Dilution Overhang: FDV/MCap [1x, 10x] → [0, 100]
        dilution = min(100, max(0, (fdv_ratio - 1.0) / 9.0 * 100))

        # 2. Revenue Void: no fees + no accrual mechanism
        if fees_30d > 50_000 and mechanism not in ("none", "unknown"):
            rev_void = 0  # has real revenue + mechanism
        elif fees_30d > 50_000:
            rev_void = 30  # has fees but no mechanism
        elif fees_30d > 0:
            rev_void = 60  # minimal fees
        else:
            rev_void = 90  # zero fees

        # Adjust: if has accrual mechanism, reduce severity
        if mechanism not in ("none", "unknown") and holders_rev > 0:
            rev_void = max(0, rev_void - 40)

        # 3. Valuation Absurdity: extreme PE + thin volume
        if fees_30d > 0 and mc > 0:
            annual_fees = fees_30d * 12
            pe = mc / annual_fees if annual_fees > 0 else 9999
            pe_score = min(100, max(0, (math.log(max(pe, 1)) - math.log(10)) / (math.log(1000) - math.log(10)) * 100))
        else:
            pe_score = 80  # no fees = high valuation concern

        # Volume thinness: low vol/mcap = illiquid
        vol_mcap = vol / mc if mc > 0 else 0
        thin_score = min(100, max(0, (1 - vol_mcap / 0.10) * 100)) if vol_mcap < 0.10 else 0

        valuation = (pe_score * 0.6 + thin_score * 0.4)

        # 4. Unlock Pressure: positive supply delta = inflationary
        unlock = min(100, max(0, sd / 5.0 * 100)) if sd > 0 else 0

        # Composite
        total = dilution * 0.30 + rev_void * 0.25 + valuation * 0.25 + unlock * 0.20

        result[t] = {
            "total": round(total, 1),
            "dilution": round(dilution, 1),
            "revenue_void": round(rev_void, 1),
            "valuation": round(valuation, 1),
            "unlock": round(unlock, 1),
            "is_flagged": total > 60,
        }

    return result


# ── Enhanced Model (VA + P3 two-pillar composite) ────────────────────

PILLAR_WEIGHTS = {
    "VA":  {"Conservative": 0.80, "Balanced": 0.70, "Growth": 0.65, "Aggressive": 0.60},
    "P3":  {"Conservative": 0.20, "Balanced": 0.30, "Growth": 0.35, "Aggressive": 0.40},
}


def compute_enhanced_scores(profile: str, tickers: list[str]) -> dict[str, float]:
    """Two-pillar composite: VA (sector-aware) + P3, with red flag haircuts."""
    va_composites = compute_ten_factor_scores(profile, tickers)
    p3_composites = compute_p3_composite(profile, tickers)
    red_flags = compute_red_flag_scores(tickers)

    va_w = PILLAR_WEIGHTS["VA"].get(profile, 0.70)
    p3_w = PILLAR_WEIGHTS["P3"].get(profile, 0.30)

    composites = {}
    for t in tickers:
        va_score = va_composites.get(t, 50)
        p3_score = p3_composites.get(t, 50)
        enhanced = va_w * va_score + p3_w * p3_score

        # Red flag haircut: >60 red flag → 0.5x allocation multiplier
        rf = red_flags.get(t, {})
        if rf.get("is_flagged", False):
            enhanced *= 0.5

        composites[t] = enhanced

    return composites


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


# ── Full data breakdown for Data tab ──────────────────────────────────

def full_data_breakdown(tickers: list[str], profile: str) -> list[dict]:
    """
    Return per-token rows with ALL raw inputs, intermediate computations,
    and final scores — so users can trace every number.
    """
    if not tickers:
        return []

    raw = _get_raw_market_vectors(tickers)

    # ── P3 scores (pre-compute for all tickers) ──
    p3_all = compute_p3_scores(tickers)

    # ── 5-Factor intermediates ──
    beta_raw = [abs(c) for c in raw["change_30d"]]
    size_raw = raw["market_caps"]
    value_raw = raw["vol_mcap_ratios"]
    momentum_raw = []
    growth_raw = []
    for i in range(len(tickers)):
        c7, c30, ath_dd = raw["change_7d"][i], raw["change_30d"][i], raw["ath_drawdowns"][i]
        total_return = c7 + c30
        vol_adj = max(ath_dd, 1.0)
        momentum_raw.append(total_return / vol_adj * 100)
        weekly_pace = c7
        monthly_weekly_pace = c30 / 4.0 if c30 != 0 else 0.01
        if abs(monthly_weekly_pace) > 0.1:
            growth_raw.append(weekly_pace / monthly_weekly_pace)
        else:
            growth_raw.append(weekly_pace)

    beta_scores = _inverse_percentile_rank(beta_raw)
    size_scores = _inverse_percentile_rank(size_raw)
    value_scores = _percentile_rank(value_raw)
    momentum_scores = _percentile_rank(momentum_raw)
    growth_scores = _percentile_rank(growth_raw)

    # ── VA model scores (uses nickel-ls-rv aligned signals) ──
    va_scores = compute_live_ten_factor_scores(tickers)

    five_factor_names = list(FIVE_FACTOR_WEIGHTS.keys())
    va_factor_names = list(VA_FACTOR_WEIGHTS.keys())

    rows = []
    for i, t in enumerate(tickers):
        dl = get_defillama_info(t) or {}
        bn = get_binance_info(t) or {}
        asset = ASSET_BY_TICKER.get(t, {})
        va = va_scores.get(t, {})
        va_sigs = va.get("_va_signals", {})
        va_raw = va.get("_va_raw", {})

        # 5-factor composite
        five_composite = sum([
            beta_scores[i] * FIVE_FACTOR_WEIGHTS[five_factor_names[0]].get(profile, 0),
            size_scores[i] * FIVE_FACTOR_WEIGHTS[five_factor_names[1]].get(profile, 0),
            value_scores[i] * FIVE_FACTOR_WEIGHTS[five_factor_names[2]].get(profile, 0),
            momentum_scores[i] * FIVE_FACTOR_WEIGHTS[five_factor_names[3]].get(profile, 0),
            growth_scores[i] * FIVE_FACTOR_WEIGHTS[five_factor_names[4]].get(profile, 0),
        ])

        # VA composite
        va_composite = sum(
            va.get(f, 50) * VA_FACTOR_WEIGHTS[f].get(profile, 0)
            for f in va_factor_names
        )

        rows.append({
            "ticker": t,
            "name": asset.get("name", t),
            "category": asset.get("category", ""),
            # ── Raw Market Data (CMC) ──
            "price": get_price(t) or 0,
            "market_cap": raw["market_caps"][i],
            "volume_24h": raw["volumes"][i],
            "vol_mcap_ratio": raw["vol_mcap_ratios"][i],
            "change_24h": raw["change_24h"][i],
            "change_7d": raw["change_7d"][i],
            "change_30d": raw["change_30d"][i],
            "ath_drawdown": raw["ath_drawdowns"][i],
            "fdv_mcap_ratio": raw["fdv_mcap_ratios"][i],
            # ── DeFiLlama ──
            "tvl": dl.get("tvl", 0),
            "tvl_change_7d": dl.get("tvl_change_7d", 0),
            "fees_30d": dl.get("fees_30d", 0),
            "fees_7d": dl.get("fees_7d", 0),
            "revenue_30d": dl.get("revenue_30d", 0),
            "fee_momentum": dl.get("fee_momentum", 0),
            "revenue_capture": dl.get("revenue_capture", 0),
            "has_defi": bool(dl),
            # ── Binance ──
            "funding_rate": bn.get("funding_rate", 0),
            "open_interest_usd": bn.get("open_interest_usd", 0),
            "has_perp": bool(bn),
            # ── Supply ──
            "supply_delta": raw["supply_deltas"][i],
            # ── 5-Factor: raw input → score ──
            "f5_beta_raw": beta_raw[i],
            "f5_beta_score": beta_scores[i],
            "f5_size_raw": size_raw[i],
            "f5_size_score": size_scores[i],
            "f5_value_raw": value_raw[i],
            "f5_value_score": value_scores[i],
            "f5_momentum_raw": momentum_raw[i],
            "f5_momentum_score": momentum_scores[i],
            "f5_growth_raw": growth_raw[i],
            "f5_growth_score": growth_scores[i],
            "f5_composite": round(five_composite, 1),
            # ── VA Model: signal [-1,+1] → score [0,100] ──
            "va_dilution_sig": va_sigs.get("dilution", 0),
            "va_dilution_score": va.get("Dilution", 50),
            "va_supply_sig": va_sigs.get("supply_delta", 0),
            "va_supply_score": va.get("Supply Delta", 50),
            "va_buyback_sig": va_sigs.get("buyback", 0),
            "va_buyback_score": va.get("Buyback Intensity", 50),
            "va_revcap_sig": va_sigs.get("rev_capture", 0),
            "va_revcap_score": va.get("Rev Capture", 50),
            "va_feemom_sig": va_sigs.get("fee_momentum", 0),
            "va_feemom_score": va.get("Fee Momentum", 50),
            "va_fdvfees_sig": va_sigs.get("fdv_fees", 0),
            "va_fdvfees_score": va.get("FDV / Fees", 50),
            "va_fdvtvl_sig": va_sigs.get("fdv_tvl", 0),
            "va_fdvtvl_score": va.get("FDV / TVL", 50),
            "va_composite": round(va_composite, 1),
            # ── VA raw inputs ──
            "va_pe_ratio": va_raw.get("pe_ratio"),
            "va_fdv_tvl_ratio": va_raw.get("fdv_tvl_ratio"),
            "va_buyback_yield": va_raw.get("buyback_yield_pct", 0),
            "va_rev_capture_ratio": va_raw.get("rev_capture_ratio", 0),
            "va_mechanism": va_raw.get("mechanism", "unknown"),
            "va_has_accrual": va_raw.get("has_accrual", False),
            # ── Developer & Community (CoinGecko) ──
            "dev_info": get_dev_info(t),
            # ── P3 Protocol Performance ──
            "p3_tvl_growth": p3_all.get(t, {}).get("tvl_growth_7d", 0),
            "p3_borrowed_growth": p3_all.get(t, {}).get("borrowed_growth_7d", 0),
            "p3_fee_growth": p3_all.get(t, {}).get("fee_growth_7d", 0),
            "p3_network": p3_all.get(t, {}).get("network_activity", 0),
            "p3_has_data": p3_all.get(t, {}).get("_has_p3", False),
            # ── Messari Network Metrics ──
            "messari_info": get_messari_info(t),
        })

    rows.sort(key=lambda x: -x["market_cap"])
    return rows


# ── Volatility Regime Detection ──────────────────────────────────────

_VOL_REGIME_LOW = 10.0    # BTC |30d change| < 10% = low vol
_VOL_REGIME_HIGH = 20.0   # BTC |30d change| > 20% = high vol
_VOL_HYSTERESIS = 3.0     # 3% buffer
_prev_vol_regime = "NORMAL"


def detect_vol_regime() -> dict:
    """Detect market vol regime from BTC 30d price change."""
    global _prev_vol_regime
    info = get_market_info("BTC") or {}
    change_30d = abs(info.get("price_change_30d") or 0)

    # With hysteresis
    if _prev_vol_regime == "LOW_VOL":
        if change_30d > _VOL_REGIME_LOW + _VOL_HYSTERESIS:
            regime = "HIGH_VOL" if change_30d > _VOL_REGIME_HIGH else "NORMAL"
        else:
            regime = "LOW_VOL"
    elif _prev_vol_regime == "HIGH_VOL":
        if change_30d < _VOL_REGIME_HIGH - _VOL_HYSTERESIS:
            regime = "LOW_VOL" if change_30d < _VOL_REGIME_LOW else "NORMAL"
        else:
            regime = "HIGH_VOL"
    else:
        if change_30d < _VOL_REGIME_LOW:
            regime = "LOW_VOL"
        elif change_30d > _VOL_REGIME_HIGH:
            regime = "HIGH_VOL"
        else:
            regime = "NORMAL"

    _prev_vol_regime = regime

    suggestions = {
        "LOW_VOL": "Low volatility — favorable for risk-on allocations",
        "NORMAL": "Normal market conditions",
        "HIGH_VOL": "High volatility — consider increasing stablecoin allocation",
    }

    return {
        "regime": regime,
        "btc_30d_change": round(change_30d, 1),
        "suggestion": suggestions[regime],
    }


# ── Drawdown Scenario Analysis ───────────────────────────────────────

STRESS_SCENARIOS = {
    "COVID Crash (Mar 2020)":    -50,
    "FTX Collapse (Nov 2022)":   -25,
    "Japan Carry (Aug 2024)":    -15,
    "China Ban (May 2021)":      -55,
    "Flash Crash (-35%)":        -35,
}


def compute_stress_scenarios(allocations: list[dict], portfolio_value: float) -> list[dict]:
    """Apply BTC shock scenarios to portfolio. Uses 30d change as beta proxy."""
    results = []
    for scenario_name, btc_shock in STRESS_SCENARIOS.items():
        total_impact_pct = 0
        for pos in allocations:
            if pos["alloc_pct"] <= 0:
                continue
            t = pos["ticker"]
            if t in ("USDC", "EURC"):
                continue  # stablecoins don't move
            if t == "PAXG":
                # Gold typically rises ~5% in crypto crashes
                total_impact_pct += pos["alloc_pct"] * 5 / 100
                continue
            # Estimate beta from 30d change
            info = get_market_info(t) or {}
            btc_info = get_market_info("BTC") or {}
            btc_30d = abs(btc_info.get("price_change_30d") or 10)
            token_30d = abs(info.get("price_change_30d") or 10)
            beta = token_30d / btc_30d if btc_30d > 0 else 1.0
            beta = min(beta, 3.0)  # cap at 3x
            token_impact = btc_shock / 100 * beta
            total_impact_pct += pos["alloc_pct"] * token_impact

        results.append({
            "scenario": scenario_name,
            "btc_shock_pct": btc_shock,
            "portfolio_impact_pct": round(total_impact_pct * 100, 1),
            "portfolio_impact_usd": round(total_impact_pct * portfolio_value, 0),
        })
    return results


# ── Diversification Score ────────────────────────────────────────────

# Category pairwise correlation proxy
_CORR_PROXY = {
    ("Layer 1", "Layer 1"): 0.85,
    ("Layer 1", "DeFi"): 0.70,
    ("Layer 1", "Layer 2"): 0.80,
    ("Layer 1", "AI / Compute"): 0.60,
    ("Layer 1", "Gaming"): 0.55,
    ("Layer 1", "Privacy"): 0.65,
    ("DeFi", "DeFi"): 0.80,
    ("DeFi", "DEX"): 0.85,
    ("DeFi", "Layer 2"): 0.70,
    ("AI / Compute", "AI / Compute"): 0.75,
    ("Gaming", "Gaming"): 0.70,
    ("Privacy", "Privacy"): 0.65,
}


def _get_corr_proxy(cat1: str, cat2: str) -> float:
    """Symmetric lookup with default 0.50."""
    return _CORR_PROXY.get((cat1, cat2)) or _CORR_PROXY.get((cat2, cat1)) or 0.50


def compute_diversification_score(allocations: list[dict]) -> dict:
    """Portfolio-level diversification grade from category correlations."""
    crypto_pos = [p for p in allocations if p["alloc_pct"] > 0 and p["ticker"] not in ("USDC", "EURC", "PAXG")]
    if len(crypto_pos) < 2:
        return {"score": 100, "grade": "A", "avg_corr": 0.0, "n_assets": len(crypto_pos)}

    # Weighted average pairwise correlation
    total_corr = 0
    total_weight = 0
    for i, p1 in enumerate(crypto_pos):
        for j, p2 in enumerate(crypto_pos):
            if i >= j:
                continue
            cat1 = ASSET_BY_TICKER.get(p1["ticker"], {}).get("category", "Other")
            cat2 = ASSET_BY_TICKER.get(p2["ticker"], {}).get("category", "Other")
            corr = _get_corr_proxy(cat1, cat2)
            w = p1["alloc_pct"] * p2["alloc_pct"]
            total_corr += corr * w
            total_weight += w

    avg_corr = total_corr / total_weight if total_weight > 0 else 0.50

    # Score: lower correlation = better (0-100)
    score = max(0, min(100, round((1 - avg_corr) * 100)))

    # Grade
    if score >= 60:
        grade = "A"
    elif score >= 45:
        grade = "B"
    elif score >= 30:
        grade = "C"
    elif score >= 15:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "avg_corr": round(avg_corr, 3),
        "n_assets": len(crypto_pos),
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
    elif mode == "VA Model":
        scores = compute_ten_factor_scores(profile, crypto_tickers)
    elif mode == "Enhanced Model":
        scores = compute_enhanced_scores(profile, crypto_tickers)

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
                weight = tier_scores[t] / total_score if total_score > 0 else 1 / len(tier_tickers)
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
