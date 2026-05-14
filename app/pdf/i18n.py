"""Internationalisation for the proposal PDF / DOCX.

Two languages: ``en`` (default) and ``de`` (German). DE is the primary
client language for Teroxx Advisory's existing book, so the wording is
held to investment-advisor register: formal Sie-Form, restrained, no
superlatives without numbers, no em dashes (per house style).

DE strings here are working drafts pending Jannick Bröring's review;
mark any change you make with care for the registered tone.
"""
from __future__ import annotations

from typing import Iterable, Optional


# ── Language resolution ─────────────────────────────────────────────


SUPPORTED = ("en", "de")
DEFAULT = "en"

# Map ISO-3166-1 alpha-2 country codes (Client.domicile_country) to a
# default proposal language. Anything not listed falls back to EN.
COUNTRY_TO_LANG = {
    "DE": "de",  # Germany
    "AT": "de",  # Austria
    "CH": "de",  # Switzerland (German-speaking — Romandie clients can flip via override)
    "LI": "de",  # Liechtenstein
}


def resolve_lang(*, requested: Optional[str], domicile_country: Optional[str]) -> str:
    """Pick the proposal language.

    Precedence: explicit query/override > domicile_country mapping > EN.
    """
    if requested:
        cand = requested.strip().lower()
        if cand in SUPPORTED:
            return cand
    if domicile_country:
        code = domicile_country.strip().upper()
        if code in COUNTRY_TO_LANG:
            return COUNTRY_TO_LANG[code]
    return DEFAULT


# ── Static string table ─────────────────────────────────────────────
#
# Flat namespace, dotted keys. Keep keys descriptive so a Jinja template
# {{ t('cover.confidential') }} reads on its own.


_STRINGS: dict[str, dict[str, str]] = {
    # Cover
    "cover.brand": {
        "en": "Teroxx Advisory",
        "de": "Teroxx Advisory",
    },
    "cover.brand_sub": {
        "en": "Investment Advisory · MiCA-regulated",
        "de": "Anlageberatung · MiCA-reguliert",
    },
    "cover.title": {
        "en": "Allocation Proposal",
        "de": "Allokationsvorschlag",
    },
    "cover.lbl_client": {"en": "CLIENT", "de": "KUNDE"},
    "cover.lbl_profile": {"en": "PROFILE", "de": "PROFIL"},
    "cover.lbl_prepared_by": {"en": "PREPARED BY", "de": "ERSTELLT VON"},
    "cover.lbl_date": {"en": "DATE", "de": "DATUM"},
    "cover.confidential": {
        "en": "Strictly confidential. Prepared for client use only.",
        "de": "Streng vertraulich. Ausschließlich für den Gebrauch des Kunden bestimmt.",
    },
    # Running header / footer
    "running.header_title": {
        "en": "Allocation Proposal",
        "de": "Allokationsvorschlag",
    },
    "running.footer_prefix": {
        "en": "Strictly confidential. Prepared by",
        "de": "Streng vertraulich. Erstellt von",
    },
    "running.footer_for": {"en": "for", "de": "für"},
    # Page tags
    "page.exec_summary": {"en": "Executive summary", "de": "Zusammenfassung"},
    "page.allocation": {"en": "Recommended allocation", "de": "Empfohlene Allokation"},
    "page.macro": {"en": "Macro framing", "de": "Makro-Einordnung"},
    "page.rationale": {"en": "Per-asset rationale", "de": "Begründung je Position"},
    "page.rationale_cont": {
        "en": "Per-asset rationale (continued)",
        "de": "Begründung je Position (Fortsetzung)",
    },
    "page.implementation": {"en": "Implementation", "de": "Umsetzung"},
    "page.appendix": {"en": "Appendix", "de": "Anhang"},
    "page.wishes": {"en": "Client wishes", "de": "Kundenwünsche"},
    "page.summary": {"en": "Advisor summary", "de": "Zusammenfassung des Beraters"},
    "page.execution_plan": {"en": "Execution plan", "de": "Umsetzungsplan"},
    "page.phased_build": {"en": "Phased build", "de": "Gestaffelter Aufbau"},
    # KPI labels
    "kpi.portfolio_value": {"en": "Portfolio value", "de": "Portfoliowert"},
    "kpi.reporting_ccy": {
        "en": "{ccy} reporting",
        "de": "Berichtswährung {ccy}",
    },
    "kpi.defensive_sleeve": {"en": "Defensive sleeve", "de": "Defensive Komponente"},
    "kpi.risk_profile": {"en": "Risk profile", "de": "Risikoprofil"},
    "kpi.positions": {"en": "{n} positions", "de": "{n} Positionen"},
    # Exhibit titles / subtitles
    "exhibit.what_this_means": {
        "en": "What this means",
        "de": "Was das bedeutet",
    },
    "exhibit.what_this_means_sub": {
        "en": "Three implications for the client.",
        "de": "Drei Schlussfolgerungen für den Kunden.",
    },
    "exhibit.recommended_alloc": {
        "en": "Recommended allocation",
        "de": "Empfohlene Allokation",
    },
    "exhibit.recommended_alloc_sub": {
        "en": "Top-down weights, target.",
        "de": "Top-down-Gewichtungen, Zielwerte.",
    },
    "exhibit.per_asset_weights": {
        "en": "Per-asset target weights",
        "de": "Zielgewichte je Position",
    },
    "exhibit.per_asset_weights_sub": {
        "en": "Sorted by target weight. The defensive sleeve is profile-driven and always included.",
        "de": "Sortiert nach Zielgewicht. Die defensive Komponente ist profilgesteuert und stets enthalten.",
    },
    "exhibit.alloc_by_tier": {
        "en": "Allocation by tier",
        "de": "Allokation nach Stufe",
    },
    "exhibit.alloc_by_tier_sub": {
        "en": "Share of portfolio across defensive, core and extended sleeves.",
        "de": "Portfolioanteil über defensive, Kern- und erweiterte Komponenten.",
    },
    "exhibit.regime_read": {
        "en": "Composite regime read",
        "de": "Marktregime-Komposit",
    },
    "exhibit.regime_read_sub": {
        "en": "22 indicators aggregated across sentiment, traditional markets, on-chain activity and technicals.",
        "de": "22 Indikatoren aggregiert über Sentiment, traditionelle Märkte, On-Chain-Aktivität und Technik.",
    },
    "exhibit.rationale_title": {
        "en": "Why each position earns its weight",
        "de": "Warum jede Position ihr Gewicht verdient",
    },
    "exhibit.execution_path": {
        "en": "Suggested execution path",
        "de": "Vorgeschlagener Umsetzungspfad",
    },
    "exhibit.execution_path_sub": {
        "en": "Editable per client; defaults below.",
        "de": "Pro Kunde anpassbar; Standardwerte unten.",
    },
    "exhibit.review_cadence": {
        "en": "Review cadence",
        "de": "Überprüfungsrhythmus",
    },
    "exhibit.methodology": {
        "en": "Methodology in one paragraph",
        "de": "Methodik in einem Absatz",
    },
    "exhibit.data_sources": {
        "en": "Data sources",
        "de": "Datenquellen",
    },
    "exhibit.phased_build": {
        "en": "Phased build schedule",
        "de": "Gestaffelter Aufbauplan",
    },
    "exhibit.phased_build_sub": {
        "en": "Monthly tranches over {horizon_months} months; the defensive sleeve is funded first, growth positions later.",
        "de": "Monatliche Tranchen über {horizon_months} Monate; die defensive Komponente wird zuerst aufgebaut, Wachstumspositionen folgen.",
    },
    # Table headers
    "table.asset": {"en": "Asset", "de": "Anlage"},
    "table.tier": {"en": "Tier", "de": "Stufe"},
    "table.weight_pct": {"en": "Weight %", "de": "Gewicht %"},
    "table.alloc_usd": {"en": "$ allocation", "de": "Zuteilung $"},
    "table.role": {"en": "Role", "de": "Rolle"},
    "table.indicator": {"en": "Indicator", "de": "Indikator"},
    "table.category": {"en": "Category", "de": "Kategorie"},
    "table.score": {"en": "Score", "de": "Wert"},
    "table.monthly_buy": {"en": "Monthly buy", "de": "Monatlicher Kauf"},
    "table.horizon_total": {"en": "Total over horizon", "de": "Summe über Zeitraum"},
    # Source attributions
    "source.pam": {
        "en": "Source: Teroxx Portfolio Allocation Model v4.1.",
        "de": "Quelle: Teroxx Portfolio Allocation Model v4.1.",
    },
    "source.as_of": {
        "en": "Data as of {date}.",
        "de": "Stand: {date}.",
    },
    "source.renormalised": {
        "en": "Renormalised across {n} positions.",
        "de": "Über {n} Positionen renormiert.",
    },
    "source.pam_universe": {
        "en": "Source: Teroxx PAM v4.1, profile {profile}, universe {universe}.",
        "de": "Quelle: Teroxx PAM v4.1, Profil {profile}, Universum {universe}.",
    },
    "source.mica_emt_art": {
        "en": "EMT = e-money token under MiCA Art. 40. ART = asset-referenced token.",
        "de": "EMT = E-Geld-Token gemäß MiCA Art. 40. ART = wertreferenzierter Token.",
    },
    "source.tier_framework": {
        "en": "Source: Teroxx PAM v4.1 tier framework.",
        "de": "Quelle: Teroxx PAM v4.1 Stufenkonzept.",
    },
    "source.macro_composite": {
        "en": "Source: alternative.me, Yahoo Finance, Binance, blockchain.info, CoinMetrics, CryptoCompare. Composite renormalises when sources are unavailable.",
        "de": "Quellen: alternative.me, Yahoo Finance, Binance, blockchain.info, CoinMetrics, CryptoCompare. Das Komposit renormiert sich, wenn einzelne Quellen nicht verfügbar sind.",
    },
    "source.house_view": {
        "en": "Source: Teroxx Advisory house view, calibrated to {profile} risk profile.",
        "de": "Quelle: Teroxx Advisory Hausmeinung, kalibriert auf das Risikoprofil {profile}.",
    },
    # Review cadence bullets
    "review.drift_window": {
        "en": "Portfolio drift checked at each review window or on regime shifts greater than 10 composite points.",
        "de": "Die Portfolio-Abweichung wird bei jedem Überprüfungstermin oder bei Regimewechseln von mehr als 10 Kompositpunkten geprüft.",
    },
    "review.single_drift": {
        "en": "Single-position drift over 5 percentage points triggers a rebalance proposal.",
        "de": "Eine Einzelpositions-Abweichung von mehr als 5 Prozentpunkten löst einen Rebalancing-Vorschlag aus.",
    },
    "review.rescore_cadence": {
        "en": "Macro regime is re-scored every 30 minutes by the Teroxx allocation model.",
        "de": "Das Makroregime wird vom Teroxx-Allokationsmodell alle 30 Minuten neu bewertet.",
    },
    # Methodology + data sources
    "methodology.body": {
        "en": (
            "The Teroxx Portfolio Allocation Model v4.1 assigns each asset to a strategic tier "
            "(defensive, core, large cap, mid cap, small cap) and distributes a profile-specific "
            "budget across the universe using either equal-weight (Standard mode) or factor-weighted "
            "(Fundamental mode) allocation. The factor stack includes value-accrual signals, on-chain "
            "fundamentals and selective momentum overlays. Defensive sleeves (USDC, EURC, PAXG) are "
            "held flat against their reference currencies; no yield is implied or paid."
        ),
        "de": (
            "Das Teroxx Portfolio Allocation Model v4.1 ordnet jede Anlage einer strategischen Stufe zu "
            "(defensiv, Kern, Large Cap, Mid Cap, Small Cap) und verteilt ein profilabhängiges Budget "
            "über das Universum, entweder gleichgewichtet (Standardmodus) oder faktorgewichtet "
            "(Fundamentalmodus). Der Faktorstapel umfasst Werterfassungssignale, On-Chain-Fundamentaldaten "
            "und selektive Momentum-Overlays. Defensive Komponenten (USDC, EURC, PAXG) werden flach gegen "
            "ihre Referenzwährungen gehalten; eine Verzinsung wird weder impliziert noch gezahlt."
        ),
    },
    "datasources.spot": {
        "en": "Spot prices and market data: CoinMarketCap (primary), CoinGecko (fallback). Five-minute cache.",
        "de": "Spotpreise und Marktdaten: CoinMarketCap (primär), CoinGecko (Reserve). Fünf-Minuten-Cache.",
    },
    "datasources.macro": {
        "en": "Macro composite: alternative.me, Yahoo Finance, Binance public fapi, blockchain.info, CoinGecko global, CoinMetrics community API.",
        "de": "Makro-Komposit: alternative.me, Yahoo Finance, Binance Public fapi, blockchain.info, CoinGecko Global, CoinMetrics Community API.",
    },
    "datasources.onchain": {
        "en": "On-chain protocol metrics: DeFiLlama, Messari, native protocol RPCs.",
        "de": "On-Chain-Protokollkennzahlen: DeFiLlama, Messari, native Protokoll-RPCs.",
    },
    "datasources.history": {
        "en": "Historical daily closes: CryptoCompare.",
        "de": "Historische Tagesschlusskurse: CryptoCompare.",
    },
    # Signoff
    "signoff.prepared_by": {
        "en": "Prepared by Teroxx Advisory.",
        "de": "Erstellt von Teroxx Advisory.",
    },
    # Override section subtitles
    "overrides.wishes_sub": {
        "en": "Specific client preferences and constraints noted in this proposal.",
        "de": "Spezifische Präferenzen und Vorgaben des Kunden, die in diesem Vorschlag berücksichtigt wurden.",
    },
    "overrides.summary_sub": {
        "en": "Tailored advisor commentary for this client.",
        "de": "Individuelle Einordnung des Beraters für diesen Kunden.",
    },
    "overrides.execution_sub": {
        "en": "Custom execution path drafted by the advisor.",
        "de": "Individueller Umsetzungsweg, abgestimmt durch den Berater.",
    },
    "overrides.omitted_note": {
        "en": "The following positions were excluded at the client's request: {tickers}.",
        "de": "Die folgenden Positionen wurden auf Wunsch des Kunden ausgeschlossen: {tickers}.",
    },
    # Implementation page heading template (lower-cased profile substituted in)
    "implementation.heading_tpl": {
        "en": "Phased build-out tailored to the {profile} profile",
        "de": "Gestaffelter Aufbau, abgestimmt auf das {profile}-Profil",
    },
    # Misc
    "misc.spot_label": {"en": "Spot", "de": "Spot"},
    "misc.weight_target": {"en": "Weight target", "de": "Zielgewicht"},
    "misc.diagram_in_pdf": {
        "en": "Diagrams and exhibits are available in the PDF version of this proposal.",
        "de": "Diagramme und Grafiken finden Sie in der PDF-Fassung dieses Vorschlags.",
    },
}


# Profile name translations (Conservative / Balanced / Growth / Aggressive)
PROFILE_LABELS: dict[str, dict[str, str]] = {
    "Conservative": {"en": "Conservative", "de": "Konservativ"},
    "Balanced": {"en": "Balanced", "de": "Ausgewogen"},
    "Growth": {"en": "Growth", "de": "Wachstum"},
    "Aggressive": {"en": "Aggressive", "de": "Aggressiv"},
}


# Tier label translations (TIER_LABELS in proposal.py)
TIER_LABELS_I18N: dict[str, dict[str, str]] = {
    "Defensive": {"en": "Defensive", "de": "Defensiv"},
    "Core": {"en": "Core", "de": "Kern"},
    "Large Cap": {"en": "Large Cap", "de": "Large Cap"},
    "Mid Cap": {"en": "Mid Cap", "de": "Mid Cap"},
    "Small Cap": {"en": "Small Cap", "de": "Small Cap"},
}


# Regime label translations
REGIME_LABELS: dict[str, dict[str, str]] = {
    "Deep Bear": {"en": "Deep Bear", "de": "Tiefer Bärenmarkt"},
    "Late Bear": {"en": "Late Bear", "de": "Später Bärenmarkt"},
    "Transition": {"en": "Transition", "de": "Übergang"},
    "Early Bull": {"en": "Early Bull", "de": "Früher Bullenmarkt"},
    "Full Bull": {"en": "Full Bull", "de": "Voller Bullenmarkt"},
}


def t(key: str, lang: str = DEFAULT, **fmt) -> str:
    """Translate ``key`` to ``lang``, with optional .format kwargs.

    Missing keys fall back to EN, then to the raw key so a missing
    string is visible in the rendered output rather than silently empty.
    """
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    val = entry.get(lang) or entry.get(DEFAULT) or key
    if fmt:
        try:
            return val.format(**fmt)
        except (KeyError, IndexError):
            return val
    return val


def profile_label(profile: str, lang: str = DEFAULT) -> str:
    entry = PROFILE_LABELS.get(profile)
    if not entry:
        return profile
    return entry.get(lang) or entry.get(DEFAULT) or profile


def tier_label(tier: str, lang: str = DEFAULT) -> str:
    entry = TIER_LABELS_I18N.get(tier)
    if not entry:
        return tier
    return entry.get(lang) or entry.get(DEFAULT) or tier


def regime_label(label: str, lang: str = DEFAULT) -> str:
    entry = REGIME_LABELS.get(label)
    if not entry:
        return label
    return entry.get(lang) or entry.get(DEFAULT) or label


__all__ = [
    "DEFAULT",
    "SUPPORTED",
    "resolve_lang",
    "t",
    "profile_label",
    "tier_label",
    "regime_label",
]
