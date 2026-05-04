"""
Teroxx Portfolio Allocation Model v4.0 — Static data layer.
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
    "Teroxx Core (9)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL"],
    "Teroxx Core+Additional (15)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "LTC", "LINK", "BCH", "TRX", "SOL", "XLM"],
    "Pre-Kraken Embed (22)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "LTC", "LINK", "BCH", "TRX", "SOL", "XLM", "DOT", "AVAX", "AAVE", "UNI", "TON", "MNT", "ASTER"],
    "Full (24)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "LTC", "LINK", "BCH", "TRX", "SOL", "XLM", "HYPE", "DOT", "AVAX", "SUI", "AAVE", "UNI", "TON", "MNT", "ASTER"],
    "Teroxx Research (21)": ["BTC", "ETH", "AAVE", "BNB", "UNI", "HYPE", "ZEC", "SKY", "TRX", "SYRUP", "XMR", "AR", "PENDLE", "AERO", "VVV", "EUL", "RNDR", "AKT", "TAO", "ATH", "MON"],
    "Long (79)": None,  # computed: all non-Short tiers
    "Extended (87)": None,  # all assets
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
    {"ticker": "RNDR",    "name": "Render",            "category": "AI / Compute", "tier": "Extended",          "risk_tier": "Speculative"},
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
]

# Build lookup
ASSET_BY_TICKER = {a["ticker"]: a for a in ASSET_UNIVERSE}

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
    "RNDR":  {"mechanism": "buyback_burn",       "defillama_accurate": False},   # Render burn-and-mint
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
    "CRV": "curve-dao-token", "RNDR": "render-token", "FET": "artificial-superintelligence-alliance",
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
DEFILLAMA_MAP = {
    "ETH": "ethereum", "SOL": "solana", "BNB": "bsc", "AVAX": "avalanche",
    "DOT": "polkadot", "ATOM": "cosmos", "ADA": "cardano", "NEAR": "near",
    "APT": "aptos", "ALGO": "algorand", "ICP": "icp", "SUI": "sui",
    "ARB": "arbitrum", "OP": "optimism", "TRX": "tron", "HBAR": "hedera",
    "FIL": "filecoin", "POL": "polygon", "IOTA": "iota",
    # DeFi protocols (have fee/TVL data)
    "AAVE": "aave", "UNI": "uniswap", "MKR": "maker", "CRV": "curve-dex",
    "LDO": "lido", "GRT": "the-graph", "SNX": "synthetix", "COMP": "compound-finance",
    "PENDLE": "pendle", "MORPHO": "morpho", "ETHFI": "ether.fi", "ENA": "ethena",
    "CAKE": "pancakeswap", "1INCH": "1inch-network", "DEXE": "dexe",
    "HYPE": "hyperliquid", "INJ": "injective",
    # Gaming / other
    "SAND": "sandbox", "MANA": "decentraland", "GALA": "gala",
    "IMX": "immutable-x", "RNDR": "render", "FET": "fetch-ai",
    # Teroxx Research additions
    "SKY": "maker", "SYRUP": "maple", "AR": "arweave",
    "AERO": "aerodrome", "EUL": "euler", "AKT": "akash-network",
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
    # DeFi protocols — use /protocol/{slug} endpoint
    "AAVE": "protocol:aave",
    "UNI": "protocol:uniswap-v3,uniswap-v2,uniswap-v4",  # multi-slug: sum TVL
    "MKR": "protocol:maker", "SKY": "protocol:maker",
    "CRV": "protocol:curve-dex",
    "LDO": "protocol:lido",
    "SNX": "protocol:synthetix",
    "COMP": "protocol:compound-finance",
    "PENDLE": "protocol:pendle",
    "MORPHO": "protocol:morpho",
    "ETHFI": "protocol:ether.fi",
    "ENA": "protocol:ethena",
    "CAKE": "protocol:pancakeswap-amm-v3,pancakeswap-amm",
    "1INCH": "protocol:1inch-network",
    "HYPE": "protocol:hyperliquid",
    "INJ": "protocol:injective",
    "SYRUP": "protocol:maple",
    "AERO": "protocol:aerodrome-slipstream,aerodrome",
    "EUL": "protocol:euler",
    "AKT": "protocol:akash-network",
}

# DefiLlama fees slug mapping (separate from protocol slugs)
DEFILLAMA_FEES_MAP = {
    "AAVE": "aave", "UNI": "uniswap", "CRV": "curve-finance",
    "LDO": "lido", "SNX": "synthetix", "COMP": "compound-finance",
    "PENDLE": "pendle", "MORPHO": "morpho", "ETHFI": "ether.fi",
    "CAKE": "pancakeswap", "1INCH": "1inch", "HYPE": "hyperliquid",
    "INJ": "injective", "MKR": "maker", "GRT": "the-graph",
    "ENA": "ethena", "ETH": "ethereum", "SOL": "solana",
    "BNB": "bsc", "AVAX": "avalanche", "ARB": "arbitrum",
    "OP": "optimism", "TRX": "tron", "SUI": "sui",
    # Teroxx Research additions
    "SKY": "maker", "SYRUP": "maple", "AERO": "aerodrome-slipstream",
    "EUL": "euler", "AKT": "akash-network",
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
