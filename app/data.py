"""
Teroxx Portfolio Allocation Model v5.0 — Static data layer.
Asset universe, tier allocations, and VA / sector signal config aligned with nickel-ls-rv.
"""

RISK_PROFILES = ["Conservative", "Balanced", "Growth", "Aggressive"]

ASSET_CLASS_ALLOCATIONS = {
    "Stablecoins (USDC/USDT)": {"Conservative": 0.40, "Balanced": 0.15, "Growth": 0.05, "Aggressive": 0.00},
    "Gold Hedge (PAXG)":       {"Conservative": 0.15, "Balanced": 0.08, "Growth": 0.03, "Aggressive": 0.01},
    "Store of Value (BTC)":    {"Conservative": 0.30, "Balanced": 0.35, "Growth": 0.25, "Aggressive": 0.20},
    "Large Cap Crypto":        {"Conservative": 0.10, "Balanced": 0.25, "Growth": 0.35, "Aggressive": 0.35},
    "Mid Cap Crypto":          {"Conservative": 0.05, "Balanced": 0.12, "Growth": 0.22, "Aggressive": 0.29},
    "Small Cap / Thematic":    {"Conservative": 0.00, "Balanced": 0.05, "Growth": 0.10, "Aggressive": 0.15},
}

DRAWDOWN_IMPACT = {
    "Crypto -50%": {"Conservative": -0.225, "Balanced": -0.385, "Growth": -0.460, "Aggressive": -0.495},
    "Crypto -30%": {"Conservative": -0.135, "Balanced": -0.231, "Growth": -0.276, "Aggressive": -0.297},
}

ALLOCATION_MODES = ["Standard", "Fundamental"]

ASSET_UNIVERSES = {
    # Teroxx Core: live 9-token roster (active offering).
    # Teroxx Expanded: confirmed next-step 21-token roster (MVP add-ons).
    # Teroxx Extended: full combined universe — Current + MVP + AB & Leo adds (40 tokens).
    "Teroxx Core (9)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL"],
    "Teroxx Expanded (21)": [
        "USDC", "EURC", "PAXG",
        "BTC", "ETH", "BNB", "XRP", "ADA",
        "POL", "MNT",
        "AAVE", "UNI", "COMP", "EUL", "PENDLE", "SYRUP", "ENA",
        "ONDO",
        "LINK", "QNT",
        "CHZ",
    ],
    "Teroxx Extended (40)": [
        # Defensive
        "USDC", "EURC", "PAXG", "BUIDL",
        # Core L1s
        "BTC", "ETH", "BNB", "XRP", "ADA", "POL",
        # MVP DeFi + infra
        "AAVE", "UNI", "COMP", "EUL", "PENDLE", "SYRUP", "ENA",
        "ONDO", "LINK", "QNT", "CHZ", "MNT",
        # AB adds
        "SOL", "HYPE", "TRX", "CRV", "SKY", "AERO", "AR", "AKT", "RENDER", "VVV",
        # Leo adds
        "AVAX", "DOT", "ARB", "SUI", "LTC", "BCH", "DOGE", "ASTER",
    ],
}

# Complete asset universe — 79 tokens
ASSET_UNIVERSE = [
    {"ticker": "USDC",    "name": "USD Coin",          "category": "Stablecoin",   "tier": "Fixed",             "risk_tier": "Defensive"},
    {"ticker": "EURC",    "name": "Euro Coin",         "category": "Stablecoin",   "tier": "Fixed",             "risk_tier": "Defensive"},
    {"ticker": "PAXG",    "name": "Pax Gold",          "category": "Gold Hedge",   "tier": "Fixed",             "risk_tier": "Defensive"},
    {"ticker": "BTC",     "name": "Bitcoin",           "category": "Store of Value","tier": "Core",             "risk_tier": "Core"},
    {"ticker": "ETH",     "name": "Ethereum",          "category": "Layer 1",      "tier": "Core",              "risk_tier": "Core"},
    {"ticker": "BNB",     "name": "BNB",               "category": "Exchange",     "tier": "Core",              "risk_tier": "Core"},
    {"ticker": "XRP",     "name": "XRP",               "category": "Layer 1",      "tier": "Core",              "risk_tier": "Core"},
    {"ticker": "ADA",     "name": "Cardano",           "category": "Layer 1",      "tier": "Core",              "risk_tier": "Core"},
    {"ticker": "POL",     "name": "Polygon",           "category": "Layer 2",      "tier": "Core",              "risk_tier": "Core"},
    {"ticker": "LTC",     "name": "Litecoin",          "category": "Payment",      "tier": "Additional",        "risk_tier": "Growth"},
    {"ticker": "LINK",    "name": "Chainlink",         "category": "Infrastructure","tier": "Additional",       "risk_tier": "Growth"},
    {"ticker": "BCH",     "name": "Bitcoin Cash",      "category": "Payment",      "tier": "Additional",        "risk_tier": "Growth"},
    {"ticker": "TRX",     "name": "TRON",              "category": "Layer 1",      "tier": "Additional",        "risk_tier": "Growth"},
    {"ticker": "SOL",     "name": "Solana",            "category": "Layer 1",      "tier": "Additional",        "risk_tier": "Core"},
    {"ticker": "XLM",     "name": "Stellar",           "category": "Payment",      "tier": "Additional",        "risk_tier": "Growth"},
    {"ticker": "HYPE",    "name": "Hyperliquid",       "category": "DeFi",         "tier": "Potential",         "risk_tier": "Growth"},
    {"ticker": "DOT",     "name": "Polkadot",          "category": "Layer 0",      "tier": "Pre-Kraken Embed",  "risk_tier": "Growth"},
    {"ticker": "IOTA",    "name": "IOTA",              "category": "IoT",          "tier": "Potential",         "risk_tier": "Speculative"},
    {"ticker": "AVAX",    "name": "Avalanche",         "category": "Layer 1",      "tier": "Pre-Kraken Embed",  "risk_tier": "Growth"},
    {"ticker": "ONDO",    "name": "Ondo Finance",      "category": "RWA",          "tier": "Pre-Kraken Embed",  "risk_tier": "Speculative"},
    {"ticker": "WLFI",    "name": "World Liberty Fi",  "category": "DeFi",         "tier": "Potential",         "risk_tier": "Speculative"},
    {"ticker": "SUI",     "name": "Sui",               "category": "Layer 1",      "tier": "Potential",         "risk_tier": "Growth"},
    {"ticker": "AAVE",    "name": "Aave",              "category": "DeFi",         "tier": "Pre-Kraken Embed",  "risk_tier": "Speculative"},
    {"ticker": "UNI",     "name": "Uniswap",           "category": "DeFi",         "tier": "Pre-Kraken Embed",  "risk_tier": "Speculative"},
    {"ticker": "ATOM",    "name": "Cosmos",            "category": "Layer 1",      "tier": "Extended",          "risk_tier": "Growth"},
    {"ticker": "NEAR",    "name": "NEAR Protocol",     "category": "Layer 1",      "tier": "Extended",          "risk_tier": "Growth"},
    {"ticker": "APT",     "name": "Aptos",             "category": "Layer 1",      "tier": "Extended",          "risk_tier": "Growth"},
    {"ticker": "ALGO",    "name": "Algorand",          "category": "Layer 1",      "tier": "Extended",          "risk_tier": "Growth"},
    {"ticker": "HBAR",    "name": "Hedera",            "category": "Layer 1",      "tier": "Extended",          "risk_tier": "Growth"},
    {"ticker": "ICP",     "name": "Internet Computer", "category": "Layer 1",      "tier": "Extended",          "risk_tier": "Growth"},
    {"ticker": "MKR",     "name": "Maker",             "category": "DeFi",         "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "CRV",     "name": "Curve",             "category": "DeFi",         "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "LDO",     "name": "Lido DAO",          "category": "DeFi",         "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "GRT",     "name": "The Graph",         "category": "DeFi",         "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "SNX",     "name": "Synthetix",         "category": "DeFi",         "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "ARB",     "name": "Arbitrum",          "category": "Layer 2",      "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "OP",      "name": "Optimism",          "category": "Layer 2",      "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "IMX",     "name": "Immutable X",       "category": "Layer 2",      "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "RENDER",  "name": "Render",            "category": "AI / Compute", "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "FET",     "name": "Fetch.ai",          "category": "AI / Compute", "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "TAO",     "name": "Bittensor",         "category": "AI / Compute", "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "FIL",     "name": "Filecoin",          "category": "AI / Compute", "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "SAND",    "name": "The Sandbox",       "category": "Gaming",       "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "MANA",    "name": "Decentraland",      "category": "Gaming",       "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "GALA",    "name": "Gala Games",        "category": "Gaming",       "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "ETC",     "name": "Ethereum Classic",  "category": "Legacy",       "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "DOGE",    "name": "Dogecoin",          "category": "Legacy",       "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "ZEC",     "name": "Zcash",             "category": "Privacy",      "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "XMR",     "name": "Monero",            "category": "Privacy",      "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "DASH",    "name": "Dash",              "category": "Privacy",      "tier": "Extended",          "risk_tier": "Speculative"},
    {"ticker": "SHIB",    "name": "Shiba Inu",         "category": "Meme",         "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "TON",     "name": "Toncoin",           "category": "Layer 1",      "tier": "Pre-Kraken Embed",  "risk_tier": "Growth"},
    {"ticker": "CRO",     "name": "Cronos",            "category": "Layer 1",      "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "MNT",     "name": "Mantle",            "category": "Layer 2",      "tier": "Pre-Kraken Embed",  "risk_tier": "Growth"},
    {"ticker": "PEPE",    "name": "Pepe",              "category": "Meme",         "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "ASTER",   "name": "Aster",             "category": "Layer 1",      "tier": "Pre-Kraken Embed",  "risk_tier": "Growth"},
    {"ticker": "WLD",     "name": "Worldcoin",         "category": "AI/Identity",  "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "ENA",     "name": "Ethena",            "category": "DeFi",         "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "MYX",     "name": "MYX Finance",       "category": "DeFi",         "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "QNT",     "name": "Quant",             "category": "Enterprise",   "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "NEXO",    "name": "NEXO",              "category": "CeFi",         "tier": "Short",             "risk_tier": "Growth"},
    {"ticker": "MORPHO",  "name": "Morpho",            "category": "DeFi",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "BONK",    "name": "Bonk",              "category": "Meme",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "CAKE",    "name": "PancakeSwap",       "category": "DEX",          "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "PENGU",   "name": "Pudgy Penguins",    "category": "Meme/NFT",     "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "CHZ",     "name": "Chiliz",            "category": "Sports",       "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "VIRTUAL", "name": "Virtuals Protocol", "category": "AI",           "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "INJ",     "name": "Injective",         "category": "Layer 1",      "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "ZRO",     "name": "LayerZero",         "category": "Infrastructure","tier": "Long",             "risk_tier": "Speculative"},
    {"ticker": "ETHFI",   "name": "Ether.fi",          "category": "DeFi",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "FLOKI",   "name": "FLOKI",             "category": "Meme",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "TWT",     "name": "Trust Wallet",      "category": "Wallet",       "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "AXS",     "name": "Axie Infinity",     "category": "Gaming",       "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "PENDLE",  "name": "Pendle",            "category": "DeFi",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "COMP",    "name": "Compound",          "category": "DeFi",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "1INCH",   "name": "1inch",             "category": "DEX",          "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "DEXE",    "name": "DeXe",              "category": "DeFi",         "tier": "Long",              "risk_tier": "Speculative"},
    {"ticker": "EDU",     "name": "Open Campus",       "category": "Education",    "tier": "Long",              "risk_tier": "Speculative"},
    # ── Teroxx Research basket (nickel-ls-rv curated long basket) ──
    {"ticker": "SKY",     "name": "Sky",               "category": "DeFi",         "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "SYRUP",   "name": "Maple Finance",     "category": "DeFi",         "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "AR",      "name": "Arweave",           "category": "AI / Compute", "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "AERO",    "name": "Aerodrome",         "category": "DEX",          "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "VVV",     "name": "Venice",            "category": "AI / Compute", "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "EUL",     "name": "Euler",             "category": "DeFi",         "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "AKT",     "name": "Akash Network",     "category": "AI / Compute", "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "ATH",     "name": "Aethir",            "category": "AI / Compute", "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "MON",     "name": "Mon Protocol",      "category": "Gaming",       "tier": "Research",          "risk_tier": "Speculative"},
    {"ticker": "BUIDL",   "name": "BlackRock USD IDLF","category": "RWA",          "tier": "Research",          "risk_tier": "Defensive"},
]

# Build lookup
ASSET_BY_TICKER = {a["ticker"]: a for a in ASSET_UNIVERSE}

# ── Thematic sector baskets ───────────────────────────────────────────────
# Index-style products (cf. Bitwise / Grayscale / BitPanda): a curated,
# 100%-in-theme allocation with NO defensive sleeve. Token weighting is
# selectable via the existing Allocation Mode toggle:
#   Standard     → market-cap weighted, single-name capped
#   Fundamental  → factor-score weighted (compute_enhanced_scores)
#
# Constraint: every basket ticker must already live in one of the three
# Teroxx model portfolios (Core 9 / Expanded 21 / Extended 40) — the 40-token
# union — so baskets only hold assets the firm can actually acquire today.
# `cap` is the per-name weight ceiling; the engine uses max(cap, 1/n) so thin
# baskets (n<=2) stay fillable.
THEMATIC_BASKETS = {
    "DeFi Basket": {
        "tickers": ["AAVE", "UNI", "COMP", "EUL", "PENDLE", "SYRUP",
                    "ENA", "HYPE", "CRV", "SKY", "AERO"],
        "cap": 0.35,
        "blurb": "Decentralised finance: lending, DEXs, perps and yield infrastructure.",
    },
    "Smart-Contract L1 Basket": {
        "tickers": ["ETH", "XRP", "ADA", "SOL", "TRX", "AVAX", "SUI", "ASTER", "DOT"],
        "cap": 0.35,
        "blurb": "Layer-1 smart-contract platforms and settlement networks.",
    },
    "AI & Compute Basket": {
        "tickers": ["AR", "AKT", "RENDER", "VVV"],
        "cap": 0.35,
        "blurb": "Decentralised AI, GPU compute and permanent storage.",
    },
    "RWA Basket": {
        # 2-name basket: cap > 0.5 so the weighting mode still tilts
        # (a 0.50 cap would force a flat 50/50 in every mode).
        "tickers": ["ONDO", "BUIDL"],
        "cap": 0.70,
        "blurb": "Tokenised real-world assets and on-chain treasuries.",
    },
    "Layer 2 Basket": {
        "tickers": ["POL", "MNT", "ARB"],
        "cap": 0.50,
        "blurb": "Ethereum scaling networks and rollups.",
    },
    "Payments Basket": {
        "tickers": ["LTC", "BCH"],
        "cap": 0.70,
        "blurb": "Established peer-to-peer payment networks.",
    },
}

# Fail fast on a typo'd ticker or one that escaped the 40-token pool.
_BASKET_ELIGIBLE_POOL = {
    t for u in ("Teroxx Core (9)", "Teroxx Expanded (21)", "Teroxx Extended (40)")
    for t in ASSET_UNIVERSES[u]
}
for _bname, _b in THEMATIC_BASKETS.items():
    for _t in _b["tickers"]:
        assert _t in ASSET_BY_TICKER, f"{_bname}: unknown ticker {_t}"
        assert _t in _BASKET_ELIGIBLE_POOL, f"{_bname}: {_t} not in 40-token pool"

# Fixed strategic allocations (stablecoins + gold)
FIXED_STRATEGIC = {
    "USDC": {"Conservative": 0.35, "Balanced": 0.12, "Growth": 0.04, "Aggressive": 0.00},
    "EURC": {"Conservative": 0.05, "Balanced": 0.03, "Growth": 0.01, "Aggressive": 0.00},
    "PAXG": {"Conservative": 0.15, "Balanced": 0.08, "Growth": 0.03, "Aggressive": 0.01},
}

# Tier allocation buckets
TIER_ALLOCATIONS = {
    "Store of Value": {"Conservative": 0.30, "Balanced": 0.35, "Growth": 0.25, "Aggressive": 0.20},
    "Large Cap":      {"Conservative": 0.10, "Balanced": 0.25, "Growth": 0.35, "Aggressive": 0.35},
    "Mid Cap":        {"Conservative": 0.05, "Balanced": 0.12, "Growth": 0.22, "Aggressive": 0.29},
    "Small Cap":      {"Conservative": 0.00, "Balanced": 0.05, "Growth": 0.10, "Aggressive": 0.15},
}


# Value Accrual (VA) model weights — aligned with nickel-ls-rv three-pillar framework.
# 7 signals (unlock excluded — no Messari data). Weights sum to 1.0 per profile.
# Conservative tilts toward valuation safety; Aggressive tilts toward accrual/growth.
VA_FACTOR_WEIGHTS = {
    "Dilution":          {"Conservative": 0.20, "Balanced": 0.15, "Growth": 0.12, "Aggressive": 0.10},
    "Supply Delta":      {"Conservative": 0.15, "Balanced": 0.15, "Growth": 0.13, "Aggressive": 0.10},
    "Buyback Intensity": {"Conservative": 0.10, "Balanced": 0.15, "Growth": 0.18, "Aggressive": 0.20},
    "Rev Capture":       {"Conservative": 0.08, "Balanced": 0.10, "Growth": 0.12, "Aggressive": 0.15},
    "Fee Momentum":      {"Conservative": 0.07, "Balanced": 0.10, "Growth": 0.12, "Aggressive": 0.15},
    "FDV / Fees":        {"Conservative": 0.25, "Balanced": 0.20, "Growth": 0.18, "Aggressive": 0.15},
    "FDV / TVL":         {"Conservative": 0.15, "Balanced": 0.15, "Growth": 0.15, "Aggressive": 0.15},
}

# VA normalization constants (from nickel-ls-rv config.py)
VA_FDV_MCAP_NEUTRAL = 2.0         # FDV/MCap = 2.0 → signal = 0 (neutral)
VA_SUPPLY_DELTA_NORMALIZE = 3.0   # ±3% = max signal
VA_BUYBACK_NEUTRAL = 5.0          # 5% annualized yield = neutral
VA_BUYBACK_MAX = 20.0             # 20%+ = max positive
VA_FEE_MOMENTUM_NORMALIZE = 50.0  # ±50% fee growth = max signal
VA_FDV_FEES_NEUTRAL = 100.0       # P/E = 100 = neutral (log scale)
VA_FDV_TVL_NEUTRAL = 10.0         # FDV/TVL = 10 = neutral (log scale)

# VA gating constants (from nickel-ls-rv config.py)
VA_GATE_MIN_FEES_30D = 50_000              # $50K/mo = meaningful fee threshold
VA_NO_ACCRUAL_FLOOR = -0.40               # Signal floor for large caps with no mechanism
VA_NO_ACCRUAL_MCAP_FLOOR = 1_000_000_000  # $1B MCap threshold for floor

# VA Registry — token accrual mechanism mapping (ported from nickel-ls-rv data/value_accrual.py)
# mechanism: buyback_burn | buyback_treasury | fee_distribution | fee_switch_partial | staking_rewards | none
# defillama_accurate: whether DeFiLlama holders_revenue is trustworthy for this token
VA_REGISTRY = {
    # ── Verified buyback/burn ──
    "HYPE":  {"mechanism": "buyback_burn",      "defillama_accurate": True},
    "TRX":   {"mechanism": "buyback_burn",      "defillama_accurate": True},
    "ETH":   {"mechanism": "buyback_burn",      "defillama_accurate": True},   # EIP-1559 burn
    "BNB":   {"mechanism": "buyback_burn",      "defillama_accurate": True},
    # ── Fee distribution / partial fee switch ──
    "AAVE":  {"mechanism": "fee_switch_partial", "defillama_accurate": True},
    "UNI":   {"mechanism": "fee_switch_partial", "defillama_accurate": True},
    "MNT":   {"mechanism": "fee_distribution",   "defillama_accurate": True},
    # ── Staking rewards (validator/protocol level) ──
    "SOL":   {"mechanism": "staking_rewards",    "defillama_accurate": True},
    "AVAX":  {"mechanism": "staking_rewards",    "defillama_accurate": True},
    "DOT":   {"mechanism": "staking_rewards",    "defillama_accurate": True},
    "SUI":   {"mechanism": "staking_rewards",    "defillama_accurate": True},
    "TON":   {"mechanism": "staking_rewards",    "defillama_accurate": True},
    "ASTER": {"mechanism": "staking_rewards",    "defillama_accurate": True},
    # ── No accrual mechanism ──
    "BTC":   {"mechanism": "none"},
    "XRP":   {"mechanism": "none"},
    "ADA":   {"mechanism": "none"},   # has staking but no protocol revenue to holders
    "POL":   {"mechanism": "none"},   # minimal holder revenue
    "LTC":   {"mechanism": "none"},
    "LINK":  {"mechanism": "none"},
    "BCH":   {"mechanism": "none"},
    "XLM":   {"mechanism": "none"},
    # ── Extended tokens with Research basket overlap ──
    "ZEC":   {"mechanism": "none"},                                              # PoW, no accrual
    "XMR":   {"mechanism": "none"},                                              # PoW, no accrual
    "PENDLE":{"mechanism": "fee_distribution",   "defillama_accurate": True},    # vePENDLE fee share
    "RENDER":{"mechanism": "buyback_burn",       "defillama_accurate": False},   # Render burn-and-mint
    "TAO":   {"mechanism": "staking_rewards",    "defillama_accurate": False},   # Subnet staking
    # ── Teroxx Research additions ──
    "SKY":   {"mechanism": "buyback_burn",       "defillama_accurate": True},   # MKR burn via surplus auctions
    "SYRUP": {"mechanism": "fee_distribution",   "defillama_accurate": True},   # Maple lending fees to stakers
    "AR":    {"mechanism": "none"},                                              # Storage endowment, no direct accrual
    "AERO":  {"mechanism": "fee_distribution",   "defillama_accurate": True},   # veAERO fee distribution
    "VVV":   {"mechanism": "buyback_burn",       "defillama_accurate": False},  # Venice AI revenue buyback
    "EUL":   {"mechanism": "fee_switch_partial", "defillama_accurate": True},   # Euler DAO fee switch
    "AKT":   {"mechanism": "fee_distribution",   "defillama_accurate": False},  # Compute lease fees to stakers
    "ATH":   {"mechanism": "staking_rewards",    "defillama_accurate": False},  # GPU node staking rewards
    "MON":   {"mechanism": "none"},
}

# Keep reference to old name for backward compat
TEN_FACTOR_WEIGHTS = VA_FACTOR_WEIGHTS

# ── Sector-Differentiated Scoring ──
# Each sector has its own 7 signals with sector-appropriate data sources.
# Signal names, weights, and compute functions differ per sector.

SECTOR_SIGNAL_NAMES = {
    "l1_platform": ["Dilution", "Network Activity", "Fee Revenue", "Ecosystem TVL", "Dev Activity", "DEX Volume", "Momentum"],
    "l2_platform": ["Dilution", "Network Activity", "Sequencer Fees", "Ecosystem TVL", "Dev Activity", "DEX Volume", "Momentum"],
    "defi":        ["Dilution", "Buyback Yield", "Rev Capture", "Fee Momentum", "FDV / Fees", "TVL Growth", "Dev Activity"],
    "ai_compute":  ["Dilution", "Dev Activity", "Momentum", "Volume Intensity", "TVL / Usage", "Fee Revenue", "Funding Rate"],
    "pow_monetary": ["Scarcity", "Txn Activity", "Fee Revenue", "Adoption", "Dev Activity", "Volume / MCap", "Momentum"],
    "speculative": ["Dilution", "Volume Intensity", "Momentum 7d", "Momentum 30d", "Dev Activity", "Liquidity Depth", "Funding Rate"],
}

# L2s differ from L1s in fee economics (sequencer fees vs gas, TVL bridged from L1):
# weight TVL more heavily and momentum less, since L2 narrative-rotation is noisier.
SECTOR_WEIGHTS = {
    "l1_platform": [0.15, 0.20, 0.15, 0.20, 0.10, 0.10, 0.10],
    "l2_platform": [0.15, 0.15, 0.15, 0.25, 0.10, 0.10, 0.10],
    "defi":        [0.15, 0.20, 0.15, 0.15, 0.15, 0.10, 0.10],
    "ai_compute":  [0.15, 0.25, 0.15, 0.10, 0.10, 0.10, 0.15],
    "pow_monetary": [0.25, 0.15, 0.15, 0.15, 0.10, 0.10, 0.10],
    "speculative": [0.15, 0.15, 0.20, 0.20, 0.10, 0.10, 0.10],
}

SECTOR_LABELS = {
    "l1_platform": "Layer 1",
    "l2_platform": "Layer 2",
    "defi": "DeFi",
    "ai_compute": "AI / Compute",
    "pow_monetary": "PoW / Monetary",
    "speculative": "Speculative",
}

# Map teroxx categories → sector key
CATEGORY_TO_VA_PROFILE = {
    "Layer 1": "l1_platform",
    "Layer 0": "l1_platform",
    "Layer 2": "l2_platform",
    "DeFi": "defi",
    "DEX": "defi",
    "Exchange": "defi",
    "AI / Compute": "ai_compute",
    "AI": "ai_compute",
    "AI/Identity": "ai_compute",
    "Store of Value": "pow_monetary",
    "Payment": "pow_monetary",
    "Privacy": "pow_monetary",
    "Legacy": "pow_monetary",
    "Infrastructure": "l1_platform",
    "Gaming": "speculative",
    "Meme": "speculative",
    "Meme/NFT": "speculative",
    "IoT": "speculative",
    "RWA": "defi",
    "CeFi": "defi",
    "Enterprise": "speculative",
    "Sports": "speculative",
    "Education": "speculative",
    "Wallet": "speculative",
}

# Per-token overrides (takes precedence over category mapping)
VA_PROFILE_OVERRIDES = {
    "BTC": "pow_monetary",
    "LINK": "l1_platform",   # Infrastructure/oracle, has Messari data
}

# Keep old SECTOR_VA_PROFILES for backward compat (used by allocation engine)
SECTOR_VA_PROFILES = {
    sector: dict(zip(SECTOR_SIGNAL_NAMES[sector], SECTOR_WEIGHTS[sector]))
    for sector in SECTOR_SIGNAL_NAMES
}

# CoinGecko ID mapping
TOKEN_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "DOT": "polkadot",
    "AVAX": "avalanche-2", "LINK": "chainlink", "ATOM": "cosmos", "UNI": "uniswap",
    "LTC": "litecoin", "BCH": "bitcoin-cash", "NEAR": "near", "APT": "aptos",
    "ALGO": "algorand", "HBAR": "hedera-hashgraph", "ICP": "internet-computer",
    "FIL": "filecoin", "ARB": "arbitrum", "OP": "optimism", "SUI": "sui",
    "INJ": "injective-protocol", "IMX": "immutable-x", "MKR": "maker",
    "AAVE": "aave", "GRT": "the-graph", "SNX": "havven", "LDO": "lido-dao",
    "CRV": "curve-dao-token", "RENDER": "render-token", "FET": "artificial-superintelligence-alliance",
    "BUIDL": "blackrock-usd-institutional-digital-liquidity-fund",
    "TAO": "bittensor", "SAND": "the-sandbox", "MANA": "decentraland",
    "GALA": "gala", "ETC": "ethereum-classic", "XLM": "stellar",
    "TRX": "tron", "SHIB": "shiba-inu", "TON": "toncoin",
    "PAXG": "pax-gold", "ZEC": "zcash", "XMR": "monero", "DASH": "dash",
    "HYPE": "hyperliquid", "POL": "matic-network",
    "IOTA": "iota", "ONDO": "ondo-finance", "WLFI": "world-liberty-financial",
    "CRO": "crypto-com-chain", "MNT": "mantle", "PEPE": "pepe",
    "ASTER": "aster-2", "WLD": "worldcoin-wld", "ENA": "ethena",
    "QNT": "quant-network", "NEXO": "nexo", "MORPHO": "morpho",
    "BONK": "bonk", "CAKE": "pancakeswap-token", "PENGU": "pudgy-penguins",
    "CHZ": "chiliz", "VIRTUAL": "virtual-protocol", "ZRO": "layerzero",
    "ETHFI": "ether-fi", "FLOKI": "floki", "TWT": "trust-wallet-token",
    "AXS": "axie-infinity", "PENDLE": "pendle", "COMP": "compound-governance-token",
    "1INCH": "1inch", "DEXE": "dexe", "EDU": "edu-coin",
    "MYX": "myx-finance",
    "USDC": "usd-coin", "EURC": "euro-coin",
    # Teroxx Research additions
    "SKY": "sky", "SYRUP": "syrup", "AR": "arweave",
    "AERO": "aerodrome-finance", "VVV": "venice-token", "EUL": "euler",
    "AKT": "akash-network", "ATH": "aethir", "MON": "monad",
}

# DefiLlama protocol slug mapping (for fees/TVL data)
# Slugs match the /protocols endpoint; versioned slugs used where DeFiLlama split by version
DEFILLAMA_MAP = {
    "ETH": "ethereum", "SOL": "solana", "BNB": "bsc", "AVAX": "avalanche",
    "DOT": "polkadot", "ATOM": "cosmos", "ADA": "cardano", "NEAR": "near",
    "APT": "aptos", "ALGO": "algorand", "ICP": "icp", "SUI": "sui",
    "ARB": "arbitrum", "OP": "optimism", "TRX": "tron", "HBAR": "hedera",
    "FIL": "filecoin", "IOTA": "iota",
    # DeFi protocols — versioned slugs (DeFiLlama dropped unversioned slugs)
    "AAVE": "aave-v3", "UNI": "uniswap-v3", "MKR": "sky-lending", "CRV": "curve-dex",
    "LDO": "lido", "GRT": "the-graph", "COMP": "compound-v3",
    "PENDLE": "pendle", "MORPHO": "morpho-blue", "ETHFI": "ether.fi-stake", "ENA": "ethena-usde",
    "CAKE": "pancakeswap-amm", "HYPE": "hyperliquid-hlp",
    # Gaming / other
    "SAND": "sandbox", "MANA": "decentraland", "GALA": "gala",
    "IMX": "immutable-x", "RENDER": "render", "FET": "fetch-ai",
    # Teroxx Research additions
    "SKY": "sky-lending", "SYRUP": "maple", "AR": "arweave",
    "AERO": "aerodrome-slipstream", "EUL": "euler-v2", "AKT": "akash-network",
}

# Ticker -> DeFiLlama chain name (as returned by /v2/chains). The /protocols
# slugs in DEFILLAMA_MAP only cover DeFi *protocols*, so L1/L2 chains (Polygon,
# Mantle, XRP Ledger, ...) would otherwise show NO TVL on the Data tab. This map
# fills chain-level TVL. Names not present in /v2/chains are skipped silently.
DEFILLAMA_CHAIN_MAP = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "BNB": "BSC",
    "POL": "Polygon", "MNT": "Mantle", "XRP": "XRPL", "ADA": "Cardano",
    "AVAX": "Avalanche", "ARB": "Arbitrum", "SUI": "Sui", "TRX": "Tron",
    "TON": "TON", "NEAR": "Near", "APT": "Aptos", "HYPE": "Hyperliquid L1",
    "OP": "OP Mainnet", "ATOM": "Cosmos", "FIL": "Filecoin", "ALGO": "Algorand",
    "HBAR": "Hedera", "ICP": "ICP",
}

# DefiLlama per-protocol TVL history mapping
# "chain:{name}" for L1 chain TVL (historicalChainTvl endpoint)
# "protocol:{slug}" for protocol TVL (/protocol/{slug} endpoint)
# Comma-separated slugs are summed (multi-version protocols)
DEFILLAMA_TVL_MAP = {
    # L1 chains — use historicalChainTvl endpoint
    "BTC": "chain:Bitcoin", "ETH": "chain:Ethereum", "SOL": "chain:Solana",
    "BNB": "chain:BSC", "AVAX": "chain:Avalanche", "DOT": "chain:Polkadot",
    "ADA": "chain:Cardano", "NEAR": "chain:Near", "APT": "chain:Aptos",
    "ALGO": "chain:Algorand", "ICP": "chain:ICP", "SUI": "chain:Sui",
    "ARB": "chain:Arbitrum", "OP": "chain:Optimism", "TRX": "chain:Tron",
    "HBAR": "chain:Hedera", "TON": "chain:TON", "ASTER": "chain:Astar",
    "MNT": "chain:Mantle",
    # DeFi protocols — use /protocol/{slug} endpoint (versioned slugs, multi-slug sums TVL)
    "AAVE": "protocol:aave-v3,aave-v2",
    "UNI": "protocol:uniswap-v3,uniswap-v2,uniswap-v4",
    "MKR": "protocol:sky-lending", "SKY": "protocol:sky-lending",
    "CRV": "protocol:curve-dex",
    "LDO": "protocol:lido",
    "COMP": "protocol:compound-v3,compound-v2",
    "PENDLE": "protocol:pendle",
    "MORPHO": "protocol:morpho-blue",
    "ETHFI": "protocol:ether.fi-stake,ether.fi-liquid",
    "ENA": "protocol:ethena-usde,ethena-usdtb",
    "CAKE": "protocol:pancakeswap-amm,pancakeswap-amm-v3",
    "HYPE": "protocol:hyperliquid-bridge,hyperliquid-hlp",
    "SYRUP": "protocol:maple",
    "AERO": "protocol:aerodrome-slipstream,aerodrome-v1",
    "EUL": "protocol:euler-v2",
    "AKT": "protocol:akash-network",
}

# DefiLlama fees slug mapping (separate from protocol slugs)
# Versioned slugs required — DeFiLlama dropped unversioned fee entries
DEFILLAMA_FEES_MAP = {
    "AAVE": "aave-v3", "UNI": "uniswap-v3", "CRV": "curve-dex",
    "LDO": "lido", "COMP": "compound-v3",
    "PENDLE": "pendle", "MORPHO": "morpho-blue", "ETHFI": "ether.fi-liquid",
    "CAKE": "pancakeswap-amm", "HYPE": "hyperliquid-hlp",
    "MKR": "sky-lending", "GRT": "the-graph",
    "ENA": "ethena-usde", "ETH": "ethereum", "SOL": "solana",
    "BNB": "bsc", "AVAX": "avalanche", "ARB": "arbitrum",
    "TRX": "tron", "SUI": "sui",
    # Teroxx Research additions
    "SKY": "sky-lending", "SYRUP": "maple", "AERO": "aerodrome-slipstream",
    "EUL": "euler-v2", "AKT": "akash-network",
}

# Messari network slug mapping (for free metrics API)
# Slugs verified from Messari /metrics/v2/networks endpoint
MESSARI_NETWORK_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "BNB": "binance-smart-chain", "ADA": "cardano", "AVAX": "avalanche",
    "DOT": "polkadot", "NEAR": "near", "APT": "aptos",
    "ALGO": "algorand", "SUI": "sui", "TRX": "tron",
    "HBAR": "hedera", "ICP": "internet-computer", "TON": "the-open-network",
    "ARB": "arbitrum-one", "OP": "optimism",
    "ATOM": "cosmos", "FIL": "filecoin",
    "XLM": "stellar", "FTM": "fantom", "POL": "polygon-pos",
    "ASTER": "astar",
}

# DCA scope options
DCA_SCOPES = {
    "BTC Only": ["BTC"],
    "BTC + Large Cap": ["BTC", "ETH", "BNB", "XRP", "SOL"],
    "All Crypto": "all",
}

# Mapping tickers to allocation tiers for the engine
def get_alloc_tier(ticker: str) -> str:
    if ticker in ("USDC", "EURC", "PAXG"):
        return "Fixed"
    if ticker == "BTC":
        return "Store of Value"
    asset = ASSET_BY_TICKER.get(ticker)
    if not asset:
        return "Small Cap"
    rt = asset["risk_tier"]
    if rt == "Core":
        return "Large Cap"
    if rt == "Growth":
        return "Mid Cap"
    return "Small Cap"


# ── Proposal copy: rationale tags, paragraph library, disclaimers ──
#
# RATIONALE_TAGS is the short label that appears next to each ticker in
# the allocation table on the Recommended Allocation page of the PDF.
# Two-word maximum. Sourced from the Teroxx PAM v5.0 framework and the
# Expanded universe valuation models in
# `~/teroxx-research/altcoin-alpha-q2-2026/data_layer/`.

RATIONALE_TAGS = {
    "USDC":   "Liquidity buffer",
    "EURC":   "EUR liquidity",
    "PAXG":   "Gold hedge",
    "BTC":    "Strategic anchor",
    "ETH":    "Settlement layer",
    "BNB":    "Exchange utility",
    "XRP":    "Payments rail",
    "ADA":    "L1 alternative",
    "POL":    "L2 incumbent",
    "MNT":    "L2 challenger",
    "AAVE":   "Lending leader",
    "UNI":    "DEX incumbent",
    "COMP":   "Lending classic",
    "EUL":    "Lending growth",
    "PENDLE": "Yield infra",
    "SYRUP":  "Institutional credit",
    "ENA":    "Synthetic dollar",
    "ONDO":   "RWA tokenisation",
    "LINK":   "Oracle backbone",
    "QNT":    "Enterprise rails",
    "CHZ":    "Consumer brand",
}

# German rationale tags, keyed to RATIONALE_TAGS. Common crypto anglicisms
# (DEX, L1/L2, Lending, Yield, Oracle, RWA, Enterprise) are kept as-is, which
# is idiomatic in German financial writing for an HNW digital-asset audience.
RATIONALE_TAGS_DE = {
    "USDC":   "Liquiditätspuffer",
    "EURC":   "EUR-Liquidität",
    "PAXG":   "Gold-Absicherung",
    "BTC":    "Strategischer Anker",
    "ETH":    "Abwicklungsschicht",
    "BNB":    "Exchange-Token",
    "XRP":    "Zahlungsnetz",
    "ADA":    "L1-Alternative",
    "POL":    "L2-Etabliert",
    "MNT":    "L2-Herausforderer",
    "AAVE":   "Lending-Marktführer",
    "UNI":    "DEX-Marktführer",
    "COMP":   "Lending-Klassiker",
    "EUL":    "Lending-Wachstum",
    "PENDLE": "Yield-Infrastruktur",
    "SYRUP":  "Institutioneller Kredit",
    "ENA":    "Synthetischer Dollar",
    "ONDO":   "RWA-Tokenisierung",
    "LINK":   "Oracle-Rückgrat",
    "QNT":    "Enterprise-Infrastruktur",
    "CHZ":    "Verbrauchermarke",
}


def rationale_tag(ticker: str, lang: str = "en") -> str:
    """Short allocation-table role label for a ticker, localized. Falls back
    to the English tag (then empty) when no German entry exists."""
    en = RATIONALE_TAGS.get(ticker, "")
    if lang == "de":
        return RATIONALE_TAGS_DE.get(ticker, en)
    return en

# RATIONALE_LIBRARY holds the per-ticker paragraph templates used on the
# Per-asset Rationale pages of the PDF. Placeholders in curly braces are
# filled at render time by `app.pdf.narrative.rationale_paragraph()`;
# missing values collapse to "n/a" so the prose still flows.
#
# Tone: factual, no superlatives, no em dashes, no marketing language.
# Each entry has:
#   tag         : short label (also in RATIONALE_TAGS).
#   headline    : 3-6 word headline above the paragraph.
#   body        : 2-3 sentence body with optional {placeholders}.

RATIONALE_LIBRARY = {
    "USDC": {
        "tag": "Liquidity buffer",
        "headline": "Operational liquidity, MiCA-compliant",
        "body": (
            "USDC anchors the liquidity sleeve and serves as the staging account for "
            "rebalances and inflows. Circle's authorisation under MiCA constrains the "
            "messaging on yield, so this position is held flat against USD rather than "
            "lent or staked."
        ),
    },
    "EURC": {
        "tag": "EUR liquidity",
        "headline": "EUR-denominated liquidity",
        "body": (
            "EURC provides EUR-native dry powder for European clients and reduces FX "
            "drag on funding and withdrawal. Treated identically to USDC for risk and "
            "yield messaging purposes."
        ),
    },
    "PAXG": {
        "tag": "Gold hedge",
        "headline": "Tokenised gold, defensive sleeve",
        "body": (
            "PAXG references physical allocated gold held by Paxos and behaves as a "
            "non-correlated hedge against crypto drawdowns. Used as a substitute for "
            "the traditional gold sleeve in client portfolios where direct bullion is "
            "operationally impractical."
        ),
    },
    "BTC": {
        "tag": "Strategic anchor",
        "headline": "Programmatic scarcity, monetary base",
        "body": (
            "Bitcoin remains the strategic anchor of any digital-asset allocation: "
            "deepest liquidity, highest institutional adoption, lowest counterparty "
            "complexity. Position sizing scales with risk profile rather than view; "
            "we never recommend zero BTC."
        ),
    },
    "ETH": {
        "tag": "Settlement layer",
        "headline": "Programmable settlement, fee-bearing asset",
        "body": (
            "Ether captures the settlement value of the dominant smart-contract "
            "platform and accrues fee revenue through the EIP-1559 burn. Holdings "
            "earn staking yield where the client mandate allows; otherwise held in "
            "spot form."
        ),
    },
    "BNB": {
        "tag": "Exchange utility",
        "headline": "Exchange-tied L1 and utility token",
        "body": (
            "BNB combines exchange utility (trading-fee discounts) with the BNB Chain "
            "L1. We treat the position as exchange-exposure first and L1 second; "
            "concentration is capped accordingly."
        ),
    },
    "XRP": {
        "tag": "Payments rail",
        "headline": "Cross-border payments infrastructure",
        "body": (
            "XRP serves cross-border value transfer for banks and remittance providers. "
            "The asset's correlation with the broader market has tightened post-2024, "
            "but it retains differentiated catalysts tied to payment-rail adoption."
        ),
    },
    "ADA": {
        "tag": "L1 alternative",
        "headline": "Research-driven L1 with measured cadence",
        "body": (
            "Cardano's slower release cadence trades execution speed for verifiable "
            "engineering. We hold a measured allocation that reflects long-term "
            "optionality rather than near-term catalysts."
        ),
    },
    "POL": {
        "tag": "L2 incumbent",
        "headline": "L2 incumbent in the Polygon 2.0 transition",
        "body": (
            "POL is the upgraded gas and staking token of the Polygon ecosystem. The "
            "thesis hinges on the AggLayer and CDK adoption; near-term price action is "
            "tied to migration milestones rather than user metrics."
        ),
    },
    "MNT": {
        "tag": "L2 challenger",
        "headline": "Mantle L2, treasury-anchored",
        "body": (
            "Mantle pairs an OP-stack L2 with one of the largest on-chain treasuries. "
            "We size the position to the treasury-coverage ratio rather than market "
            "capitalisation to reflect the implicit floor."
        ),
    },
    "AAVE": {
        "tag": "Lending leader",
        "headline": "Lending market leader, fee-accruing",
        "body": (
            "Aave V3 captures the largest share of non-custodial lending across chains. "
            "Fee capture {fees_30d_change} over the trailing 30 days, TVL {tvl}. The "
            "GHO stablecoin module is incremental optionality rather than core thesis."
        ),
    },
    "UNI": {
        "tag": "DEX incumbent",
        "headline": "Dominant DEX with pending fee switch",
        "body": (
            "Uniswap remains the spot DEX of record on-chain by volume. The thesis is "
            "fee-switch optionality: when (not if) governance activates protocol-level "
            "fees, the cash-flow profile changes materially. Position sized to that "
            "tail rather than today's economics."
        ),
    },
    "COMP": {
        "tag": "Lending classic",
        "headline": "Compound, conservative lending exposure",
        "body": (
            "Compound is the OG lending market and remains a benchmark counterparty "
            "for risk-managed lending exposure. Useful as a paired position alongside "
            "AAVE for advisors wanting two-name diversification within the sub-sector."
        ),
    },
    "EUL": {
        "tag": "Lending growth",
        "headline": "Euler, growth lender post-restart",
        "body": (
            "Euler V2 returned in 2024 with a vault architecture that compares "
            "favourably to legacy money markets on isolation. Earlier-stage than Aave; "
            "sized accordingly."
        ),
    },
    "PENDLE": {
        "tag": "Yield infra",
        "headline": "Yield tokenisation infrastructure",
        "body": (
            "Pendle splits yield-bearing assets into principal and yield tokens, "
            "letting users trade fixed and floating yield separately. The protocol "
            "rides any growth in tokenised yield (LSTs, stablecoin yield, RWA) and "
            "compounds when rates are volatile."
        ),
    },
    "SYRUP": {
        "tag": "Institutional credit",
        "headline": "Maple Finance, institutional credit on-chain",
        "body": (
            "Maple originates fixed-term loans to credit-worthy borrowers and "
            "distributes yield to lenders. SYRUP represents fee accrual; pair with "
            "rigorous monitoring of underwriting quality and default rates."
        ),
    },
    "ENA": {
        "tag": "Synthetic dollar",
        "headline": "Ethena's USDe and the funding-rate carry",
        "body": (
            "Ethena issues USDe, a synthetic dollar collateralised by ETH long-short "
            "positions earning the perp funding spread. ENA is the governance and "
            "fee token; exposure should be sized to comfort with the funding-cycle "
            "tail risk."
        ),
    },
    "ONDO": {
        "tag": "RWA tokenisation",
        "headline": "RWA tokenisation, tradfi bridge",
        "body": (
            "Ondo brings tokenised T-bills and money-market funds on-chain through "
            "OUSG and USDY. The franchise depends on continued institutional "
            "willingness to settle on-chain; track AUM rather than token-velocity "
            "metrics."
        ),
    },
    "LINK": {
        "tag": "Oracle backbone",
        "headline": "Chainlink, oracle and cross-chain backbone",
        "body": (
            "Chainlink is the oracle layer the largest part of DeFi depends on, and "
            "with CCIP it now also serves cross-chain messaging. Fee capture has "
            "historically lagged usage; we hold for strategic optionality rather than "
            "near-term yield."
        ),
    },
    "QNT": {
        "tag": "Enterprise rails",
        "headline": "Quant, enterprise integration narrative",
        "body": (
            "Quant pursues enterprise integration through Overledger and has measured "
            "but persistent partnerships in financial-infrastructure RFPs. Sized small "
            "to the speculative tier; the proof is in book-of-business, not announcements."
        ),
    },
    "CHZ": {
        "tag": "Consumer brand",
        "headline": "Chiliz, consumer-brand crypto rails",
        "body": (
            "Chiliz operates the Socios fan-token platform and the Chiliz Chain "
            "consumer L1. Most adjacent to consumer-brand utility; volatility tracks "
            "sports-calendar catalysts more than crypto-native flows."
        ),
    },
}


# DISCLAIMERS is keyed by ISO-3166 alpha-2 country code. The PDF picks the
# matching block based on the client's `domicile_country`; everything
# falls back to "default" if no match. Wording is intentionally
# conservative and aligned with the Teroxx CASP scope (advisory + RTO,
# no fund wrapper, no tax/estate advice).

_TAX_PARAGRAPH = (
    "This document does not constitute tax advice. Crypto-asset transactions "
    "may trigger taxable events under local law. Teroxx Advisory provides "
    "tax-ready data on request; clients should consult a qualified tax "
    "advisor (in Germany, a Steuerberater) for personalised guidance."
)

_ESTATE_PARAGRAPH = (
    "This document does not constitute estate, succession, or inheritance "
    "advice. Clients should consult a qualified notary or lawyer in their "
    "jurisdiction for planning related to digital-asset succession."
)

DISCLAIMERS = {
    "default": {
        "title": "Important information",
        "body": (
            "This proposal is provided by Teroxx Advisory as part of a "
            "non-discretionary advisory mandate. It is not an offer or "
            "solicitation, nor investment advice tailored to a particular "
            "jurisdiction other than as expressly stated. Past performance "
            "is not indicative of future results. All allocations are "
            "subject to market and operational risks; capital is at risk."
        ),
        "tax": _TAX_PARAGRAPH,
        "estate": _ESTATE_PARAGRAPH,
    },
    "DE": {
        "title": "Important information (Germany / EU)",
        "body": (
            "Teroxx operates as a regulated crypto-asset service provider "
            "under MiCA (Markets in Crypto-Assets Regulation). The "
            "recommendations in this proposal are advisory in nature and "
            "do not constitute portfolio management on a discretionary "
            "basis. References to e-money tokens (USDC, EURC) reflect "
            "their classification under MiCA Art. 40 and Art. 50; Teroxx "
            "does not pay interest or yield on EMT holdings, and the "
            "client should disregard third-party offers that imply "
            "otherwise. Capital is at risk; past performance is not "
            "indicative of future results."
        ),
        "tax": _TAX_PARAGRAPH,
        "estate": _ESTATE_PARAGRAPH,
    },
    "AT": {
        "title": "Important information (Austria / EU)",
        "body": (
            "Teroxx operates as a regulated crypto-asset service provider "
            "under MiCA. References to e-money tokens (USDC, EURC) "
            "reflect their classification under MiCA Art. 40 and Art. 50; "
            "Teroxx does not pay interest or yield on EMT holdings. "
            "Capital is at risk."
        ),
        "tax": _TAX_PARAGRAPH,
        "estate": _ESTATE_PARAGRAPH,
    },
    "CH": {
        "title": "Important information (Switzerland)",
        "body": (
            "This proposal is provided to a Swiss-domiciled client by "
            "Teroxx Advisory under its advisory mandate. Swiss FinSA "
            "client-segmentation rules apply; suitability and "
            "appropriateness checks are documented separately. Capital is "
            "at risk."
        ),
        "tax": _TAX_PARAGRAPH,
        "estate": _ESTATE_PARAGRAPH,
    },
    "AE": {
        "title": "Important information (UAE)",
        "body": (
            "This proposal is provided to a UAE-domiciled client. Teroxx "
            "Advisory is not regulated by the UAE Securities and Commodities "
            "Authority for the purposes of this engagement; the client "
            "acknowledges the cross-border nature of the relationship. "
            "Capital is at risk."
        ),
        "tax": _TAX_PARAGRAPH,
        "estate": _ESTATE_PARAGRAPH,
    },
}


# Regulatory flags rendered as inline badges next to a ticker. EMT badge
# fires on MiCA-classified e-money tokens regardless of client domicile
# so advisors do not stray into yield messaging on those names.
ASSET_REGULATORY_FLAGS = {
    "USDC": ["EMT"],
    "EURC": ["EMT"],
    "PAXG": ["ART"],   # Asset-Referenced Token under MiCA
}
