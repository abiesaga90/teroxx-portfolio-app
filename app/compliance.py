"""Compliance helpers — surface only, no gating.

Per the project decision in the holistic improvement plan, this layer
*shows* the right regulatory context without blocking any user action.
- Domicile-aware disclaimer text for footers on Workspace and Client
  Review.
- Inline badges for MiCA-classified assets (USDC, EURC = EMT;
  PAXG = ART) so advisors do not stray into yield messaging.
- A top-of-page MiCA reminder banner when an active client portfolio
  contains an e-money token under MiCA Art. 40 / 50.

This module imports from `app.data` only (no DB / network) so it stays
trivially testable.
"""
from __future__ import annotations

from typing import Iterable, Optional

from app.data import ASSET_REGULATORY_FLAGS, DISCLAIMERS


# Tickers classified as e-money tokens (Art. 40) for MiCA purposes.
_EMT_TICKERS = {t for t, flags in ASSET_REGULATORY_FLAGS.items() if "EMT" in flags}
# Tickers classified as asset-referenced tokens (Art. 50).
_ART_TICKERS = {t for t, flags in ASSET_REGULATORY_FLAGS.items() if "ART" in flags}

# EU+EEA domicile codes that fall under MiCA scope.
_MICA_DOMICILES = {"DE", "AT", "FR", "ES", "IT", "NL", "BE", "IE", "LU", "PT", "PL", "FI", "SE", "DK", "GR", "CZ", "HU", "HR", "RO", "SK", "SI", "BG", "EE", "LT", "LV", "CY", "MT"}


def is_mica_domicile(country_code: Optional[str]) -> bool:
    return bool(country_code) and country_code.upper() in _MICA_DOMICILES


def regulatory_flags(ticker: str) -> list[str]:
    """Return the inline badges to render next to a ticker, in display order."""
    return list(ASSET_REGULATORY_FLAGS.get((ticker or "").upper(), []))


def flag_meaning(flag: str) -> str:
    """One-line explanation behind each badge, for tooltips."""
    return {
        "EMT": "E-money token under MiCA Art. 40. Held flat against reference currency; no yield is paid or implied.",
        "ART": "Asset-referenced token under MiCA Art. 50. Backed by a basket; not a deposit.",
    }.get(flag, flag)


def disclaimer_for(client: Optional[dict]) -> dict:
    """Return the disclaimer block matching the client's domicile country."""
    country = ((client or {}).get("domicile_country") or "").upper()
    return DISCLAIMERS.get(country) or DISCLAIMERS["default"]


def tax_disclaimer() -> str:
    """Shorthand for the tax-only paragraph (Steuerberater-only rule)."""
    return DISCLAIMERS["default"]["tax"]


def portfolio_contains_emt(tickers: Iterable[str]) -> bool:
    """True if any of the given tickers are MiCA EMTs."""
    return any((t or "").upper() in _EMT_TICKERS for t in tickers)


def portfolio_contains_art(tickers: Iterable[str]) -> bool:
    return any((t or "").upper() in _ART_TICKERS for t in tickers)


def mica_banner(client: Optional[dict], active_tickers: Iterable[str]) -> Optional[str]:
    """Return a one-line banner string when MiCA-relevant context applies.

    Triggers when:
      - The client is domiciled in a MiCA jurisdiction AND holds EMTs/ARTs, OR
      - Any active ticker is EMT/ART regardless of domicile (defensive surface).
    Returns None if no banner is needed.
    """
    tickers = [t for t in active_tickers if t]
    has_emt = portfolio_contains_emt(tickers)
    has_art = portfolio_contains_art(tickers)
    if not (has_emt or has_art):
        return None
    country = (client or {}).get("domicile_country", "")
    if is_mica_domicile(country) or has_emt or has_art:
        parts = []
        if has_emt:
            parts.append("EMTs (USDC, EURC) are held flat per MiCA Art. 40 / 50")
        if has_art:
            parts.append("ART positions (PAXG) follow MiCA Art. 50 messaging")
        return "Reminder: " + "; ".join(parts) + ". Do not message yield on these holdings."
    return None


__all__ = [
    "is_mica_domicile",
    "regulatory_flags",
    "flag_meaning",
    "disclaimer_for",
    "tax_disclaimer",
    "portfolio_contains_emt",
    "portfolio_contains_art",
    "mica_banner",
]
