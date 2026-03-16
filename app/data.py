"""
Teroxx Portfolio Allocation Model v3.6 — Static data layer.
All asset universe, allocations, factor weights ported from Excel.
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

ALLOCATION_MODES = ["Standard", "Factor Model", "Fundamental Model"]

ASSET_UNIVERSES = {
    "Teroxx Core (10)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "HT"],
    "Teroxx Core+Additional (16)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "HT", "LTC", "LINK", "BCH", "TRX", "SOL", "XLM"],
    "Pre-Kraken Embed (23)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "HT", "LTC", "LINK", "BCH", "TRX", "SOL", "XLM", "DOT", "AVAX", "AAVE", "UNI", "TON", "MNT", "ASTER"],
    "Full (25)": ["USDC", "EURC", "PAXG", "BTC", "ETH", "BNB", "XRP", "ADA", "POL", "HT", "LTC", "LINK", "BCH", "TRX", "SOL", "XLM", "HYPE", "DOT", "AVAX", "SUI", "AAVE", "UNI", "TON", "MNT", "ASTER"],
    "Long (53)": None,  # computed: all non-Short tiers
    "Extended (79)": None,  # all assets
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
    {"ticker": "POL",     "name": "Polygon",           "category": "Infrastructure","tier": "Core",             "risk_tier": "Core"},
    {"ticker": "HT",      "name": "Huobi Token",       "category": "Exchange",     "tier": "Core",              "risk_tier": "Core"},
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


# 5-Factor model weights
FIVE_FACTOR_WEIGHTS = {
    "Market Beta (Low B)":    {"Conservative": 0.35, "Balanced": 0.25, "Growth": 0.10, "Aggressive": 0.10},
    "Size - SMB (Small Cap)": {"Conservative": 0.00, "Balanced": 0.05, "Growth": 0.15, "Aggressive": 0.20},
    "Value (MC/Fees)":        {"Conservative": 0.30, "Balanced": 0.25, "Growth": 0.25, "Aggressive": 0.20},
    "Momentum (Vol-Adj)":     {"Conservative": 0.15, "Balanced": 0.20, "Growth": 0.25, "Aggressive": 0.25},
    "Growth (Fee+DAU D)":     {"Conservative": 0.20, "Balanced": 0.25, "Growth": 0.25, "Aggressive": 0.25},
}

# 10-Factor fundamental model weights
TEN_FACTOR_WEIGHTS = {
    "Value (P/S)":          {"Conservative": 0.25, "Balanced": 0.20, "Growth": 0.15, "Aggressive": 0.10},
    "Fee Momentum":         {"Conservative": 0.10, "Balanced": 0.15, "Growth": 0.15, "Aggressive": 0.15},
    "TVL Health":           {"Conservative": 0.15, "Balanced": 0.10, "Growth": 0.10, "Aggressive": 0.05},
    "Revenue Quality":      {"Conservative": 0.10, "Balanced": 0.10, "Growth": 0.10, "Aggressive": 0.10},
    "Usage Growth":         {"Conservative": 0.05, "Balanced": 0.10, "Growth": 0.15, "Aggressive": 0.15},
    "Risk (Low Vol)":       {"Conservative": 0.15, "Balanced": 0.05, "Growth": 0.00, "Aggressive": 0.00},
    "Dilution Safety":      {"Conservative": 0.10, "Balanced": 0.10, "Growth": 0.10, "Aggressive": 0.10},
    "Float Quality":        {"Conservative": 0.05, "Balanced": 0.05, "Growth": 0.05, "Aggressive": 0.05},
    "Smart Money":          {"Conservative": 0.00, "Balanced": 0.10, "Growth": 0.15, "Aggressive": 0.20},
    "Developer Momentum":   {"Conservative": 0.05, "Balanced": 0.05, "Growth": 0.05, "Aggressive": 0.10},
}

# Default factor scores (0-100) — all 50 except noted
DEFAULT_FIVE_FACTOR_SCORES = {
    "Market Beta (Low B)": 100,  # BTC benchmark = 100
    "Size - SMB (Small Cap)": 50,
    "Value (MC/Fees)": 50,
    "Momentum (Vol-Adj)": 50,
    "Growth (Fee+DAU D)": 50,
}

DEFAULT_TEN_FACTOR_SCORES = {k: 50 for k in TEN_FACTOR_WEIGHTS}
# ETH has Developer Momentum = 100
ETH_TEN_FACTOR_OVERRIDES = {"Developer Momentum": 100}

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
    "HYPE": "hyperliquid", "POL": "matic-network", "HT": "huobi-token",
    "IOTA": "iota", "ONDO": "ondo-finance", "WLFI": "world-liberty-financial",
    "CRO": "crypto-com-chain", "MNT": "mantle", "PEPE": "pepe",
    "ASTER": "aster-2", "WLD": "worldcoin-wld", "ENA": "ethena",
    "QNT": "quant-network", "NEXO": "nexo", "MORPHO": "morpho",
    "BONK": "bonk", "CAKE": "pancakeswap-token", "PENGU": "pudgy-penguins",
    "CHZ": "chiliz", "VIRTUAL": "virtuals-protocol", "ZRO": "layerzero",
    "ETHFI": "ether-fi", "FLOKI": "floki", "TWT": "trust-wallet-token",
    "AXS": "axie-infinity", "PENDLE": "pendle", "COMP": "compound-governance-token",
    "1INCH": "1inch", "DEXE": "dexe", "EDU": "open-campus",
    "MYX": "myx-finance",
    "USDC": "usd-coin", "EURC": "euro-coin",
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
