"""
Demo client portfolios — imaginary HNW clients for the CRM portfolio view.

Not real client data. Entry prices and dates are plausible historical values
chosen so the resulting P&L is realistic (mix of winners and losers).
"""
from __future__ import annotations

# Each client: id, name, profile (risk profile), positions list.
# A position: ticker, qty, entry_price (USD), entry_date (ISO YYYY-MM-DD), notes.

DEMO_CLIENTS: dict[str, dict] = {
    "mueller_hnw": {
        "id": "mueller_hnw",
        "name": "Familie Müller",
        "profile": "Conservative",
        "domicile": "Munich, DE",
        "tagline": "Conservative HNW — wealth preservation, gold-anchored",
        "inception_date": "2025-04-15",
        "currency": "EUR",
        "starting_capital_usd": 750_000,
        "positions": [
            {"ticker": "USDC", "quantity": 200_000,    "entry_price": 1.00,      "entry_date": "2025-04-15", "notes": "EUR liquidity buffer"},
            {"ticker": "PAXG", "quantity": 35.0,       "entry_price": 2_350.00,  "entry_date": "2025-04-15", "notes": "Gold sleeve"},
            {"ticker": "BTC",  "quantity": 2.40,       "entry_price": 92_000.00, "entry_date": "2025-04-15", "notes": "Core position"},
            {"ticker": "ETH",  "quantity": 30.0,       "entry_price": 3_100.00,  "entry_date": "2025-04-15", "notes": ""},
            {"ticker": "BNB",  "quantity": 80.0,       "entry_price": 610.00,    "entry_date": "2025-06-02", "notes": "Top-up after Q2 review"},
            {"ticker": "PAXG", "quantity": 8.0,        "entry_price": 2_710.00,  "entry_date": "2025-09-10", "notes": "Gold add on rate-cut signal"},
        ],
    },
    "schmidt_balanced": {
        "id": "schmidt_balanced",
        "name": "Dr. Schmidt",
        "profile": "Balanced",
        "domicile": "Hamburg, DE",
        "tagline": "Mid-50s professional — balanced majors with staking yield",
        "inception_date": "2024-11-12",
        "currency": "EUR",
        "starting_capital_usd": 380_000,
        "positions": [
            {"ticker": "USDC", "quantity": 60_000,     "entry_price": 1.00,      "entry_date": "2024-11-12", "notes": ""},
            {"ticker": "PAXG", "quantity": 12.0,       "entry_price": 2_620.00,  "entry_date": "2024-11-12", "notes": ""},
            {"ticker": "BTC",  "quantity": 1.80,       "entry_price": 81_000.00, "entry_date": "2024-11-12", "notes": "Initial allocation"},
            {"ticker": "ETH",  "quantity": 28.0,       "entry_price": 3_300.00,  "entry_date": "2024-11-12", "notes": ""},
            {"ticker": "SOL",  "quantity": 320.0,      "entry_price": 175.00,    "entry_date": "2024-11-12", "notes": ""},
            {"ticker": "BNB",  "quantity": 50.0,       "entry_price": 595.00,    "entry_date": "2024-11-12", "notes": ""},
            {"ticker": "ETH",  "quantity": 6.5,        "entry_price": 2_400.00,  "entry_date": "2025-04-08", "notes": "DCA buy on 30% drawdown"},
            {"ticker": "ADA",  "quantity": 12_000,     "entry_price": 0.62,      "entry_date": "2025-02-14", "notes": ""},
        ],
    },
    "weber_growth": {
        "id": "weber_growth",
        "name": "Anna Weber",
        "profile": "Growth",
        "domicile": "Berlin, DE",
        "tagline": "Tech-fluent founder — majors plus AI/DeFi tilt",
        "inception_date": "2025-01-22",
        "currency": "EUR",
        "starting_capital_usd": 220_000,
        "positions": [
            {"ticker": "USDC", "quantity": 18_000,     "entry_price": 1.00,      "entry_date": "2025-01-22", "notes": ""},
            {"ticker": "BTC",  "quantity": 0.85,       "entry_price": 102_000.00, "entry_date": "2025-01-22", "notes": ""},
            {"ticker": "ETH",  "quantity": 22.0,       "entry_price": 3_400.00,  "entry_date": "2025-01-22", "notes": ""},
            {"ticker": "SOL",  "quantity": 280.0,      "entry_price": 235.00,    "entry_date": "2025-01-22", "notes": "Underwater after Q1 drawdown"},
            {"ticker": "BNB",  "quantity": 35.0,       "entry_price": 660.00,    "entry_date": "2025-01-22", "notes": ""},
            {"ticker": "AAVE", "quantity": 90.0,       "entry_price": 280.00,    "entry_date": "2025-03-04", "notes": "DeFi lending exposure"},
            {"ticker": "LINK", "quantity": 1_200,      "entry_price": 14.50,     "entry_date": "2025-05-18", "notes": ""},
            {"ticker": "TAO",  "quantity": 28.0,       "entry_price": 305.00,    "entry_date": "2025-07-09", "notes": "AI/compute thematic"},
        ],
    },
    "alkhouri_aggressive": {
        "id": "alkhouri_aggressive",
        "name": "S. Al-Khouri",
        "profile": "Aggressive",
        "domicile": "Dubai, AE",
        "tagline": "Dubai family office — high-conviction crypto-native",
        "inception_date": "2025-06-30",
        "currency": "USD",
        "starting_capital_usd": 1_400_000,
        "positions": [
            {"ticker": "USDC", "quantity": 40_000,     "entry_price": 1.00,      "entry_date": "2025-06-30", "notes": "Operational liquidity"},
            {"ticker": "BTC",  "quantity": 7.20,       "entry_price": 108_500.00, "entry_date": "2025-06-30", "notes": "Concentrated core"},
            {"ticker": "ETH",  "quantity": 140.0,      "entry_price": 3_650.00,  "entry_date": "2025-06-30", "notes": ""},
            {"ticker": "SOL",  "quantity": 1_800,      "entry_price": 198.00,    "entry_date": "2025-06-30", "notes": ""},
            {"ticker": "BNB",  "quantity": 280.0,      "entry_price": 720.00,    "entry_date": "2025-06-30", "notes": ""},
            {"ticker": "HYPE", "quantity": 4_500,      "entry_price": 28.50,     "entry_date": "2025-08-12", "notes": "Perp DEX thesis"},
            {"ticker": "AAVE", "quantity": 220.0,      "entry_price": 295.00,    "entry_date": "2025-09-04", "notes": ""},
            {"ticker": "TAO",  "quantity": 95.0,       "entry_price": 340.00,    "entry_date": "2025-10-16", "notes": "AI compute tilt"},
            {"ticker": "AKT",  "quantity": 18_000,     "entry_price": 3.10,      "entry_date": "2025-10-16", "notes": "Decentralised compute"},
        ],
    },
}


def list_clients() -> list[dict]:
    """Lightweight list of clients for picker UI: id, name, profile, tagline."""
    return [
        {"id": c["id"], "name": c["name"], "profile": c["profile"], "tagline": c["tagline"], "domicile": c["domicile"]}
        for c in DEMO_CLIENTS.values()
    ]


def get_client(client_id: str) -> dict | None:
    return DEMO_CLIENTS.get(client_id)
