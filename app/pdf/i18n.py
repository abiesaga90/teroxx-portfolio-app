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
    # Brand claim from Short Brand Guideline VS1.0 — set in Sometimes
    # Times Medium; color depends on background (Sandstone on Nightblue,
    # white on color gradient). Same string in both languages: the brand
    # book keeps the claim in English even on German materials.
    "cover.brand_claim": {
        "en": "The Digital Asset Boutique.",
        "de": "The Digital Asset Boutique.",
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
    # Page footer (left side, next to the client name).
    "running.confidential": {"en": "Confidential", "de": "Vertraulich"},
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
    "kpi.weighting": {"en": "Weighting", "de": "Gewichtung"},
    "weighting.market_cap": {"en": "Market-cap, capped", "de": "Marktkapitalisierung, gedeckelt"},
    "weighting.fundamental": {"en": "Fundamental score", "de": "Fundamental-Score"},
    "kpi.risk_profile": {"en": "Risk profile", "de": "Risikoprofil"},
    "kpi.positions": {"en": "{n} positions", "de": "{n} Positionen"},
    # Plain noun for label/value KPI tables (the value column carries the count).
    "kpi.num_positions": {"en": "Positions", "de": "Positionen"},
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
    "exhibit.per_asset_weights_sub_basket": {
        "en": "Sorted by target weight. The basket is fully invested in-theme, with no defensive sleeve.",
        "de": "Sortiert nach Zielgewicht. Die Basket ist vollständig themenbezogen investiert, ohne defensive Komponente.",
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
    "methodology.body_basket": {
        "en": (
            "This is a thematic sector basket from the Teroxx Portfolio Allocation Model v4.1: "
            "a fully invested, single-theme allocation drawn only from assets in the Teroxx model "
            "universe. The basket carries no defensive sleeve. Constituents are weighted either by "
            "market capitalisation with a single-name cap (Market-cap mode) or by the model's "
            "fundamental factor score (Fundamental mode); the factor stack includes value-accrual "
            "signals, on-chain fundamentals and selective momentum overlays. Position the basket in "
            "line with the client's overall risk budget at the portfolio level."
        ),
        "de": (
            "Dies ist eine thematische Sektor-Basket aus dem Teroxx Portfolio Allocation Model v4.1: "
            "eine vollständig investierte, themenbezogene Allokation, die ausschließlich aus Anlagen "
            "des Teroxx-Modelluniversums besteht. Die Basket enthält keine defensive Komponente. Die "
            "Bestandteile werden entweder nach Marktkapitalisierung mit einer Einzeltitelobergrenze "
            "(Marktkapitalisierungsmodus) oder nach dem Fundamental-Faktor-Score des Modells "
            "(Fundamentalmodus) gewichtet. Der Faktorstapel umfasst Werterfassungssignale, "
            "On-Chain-Fundamentaldaten und selektive Momentum-Overlays. Die Basket sollte im Rahmen "
            "des Gesamtrisikobudgets des Kunden positioniert werden."
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

    # ── Welcome / salutation (directional from Jannick's template) ──
    "welcome.salutation_default": {
        "en": "Dear {name},",
        "de": "Sehr geehrte/r {name},",
    },
    # Four-paragraph default welcome. Tone: formal Sie-Form, advisor-
    # to-private-client, no superlatives. Advisors override per client
    # via the `welcome_md` field.
    "welcome.body_default": {
        "en": (
            "Welcome to Teroxx Investment Advisory. We are glad to count you among our clients "
            "and look forward to accompanying you on the path to durable capital preservation and "
            "considered wealth growth.\n\n"
            "At Teroxx, your financial goals stand at the centre of every decision. Our team "
            "combines deep market knowledge with disciplined, transparent execution so the strategy "
            "we agree on can be carried out precisely as defined.\n\n"
            "Transparency and trust are non-negotiable. We take the time to understand your needs "
            "and we work with you on a wealth strategy that fits your circumstances rather than a "
            "one-size-fits-all template.\n\n"
            "Below you will find an overview of your personal investment information and your "
            "individual investor profile."
        ),
        "de": (
            "Willkommen bei Teroxx Investment Advisory. Wir freuen uns, Sie als Kundin oder Kunden "
            "begrüßen zu dürfen, und begleiten Sie gerne auf Ihrem Weg zu langfristiger "
            "Vermögenssicherung und nachhaltigem Vermögensaufbau.\n\n"
            "Bei Teroxx Investment Advisory stehen Ihre finanziellen Ziele und Interessen stets im "
            "Mittelpunkt unseres Handelns. Unser Team verbindet fundiertes Marktwissen mit einer "
            "disziplinierten und transparenten Umsetzung, sodass die gemeinsam vereinbarte Strategie "
            "präzise und nachvollziehbar realisiert werden kann.\n\n"
            "Transparenz und Vertrauen stehen bei uns an erster Stelle. Wir nehmen uns die Zeit, "
            "Ihre Bedürfnisse zu verstehen, und arbeiten gemeinsam mit Ihnen an einer Strategie, "
            "die zu Ihrer persönlichen Situation passt – statt einer Standardlösung.\n\n"
            "Nachfolgend finden Sie eine Übersicht Ihrer persönlichen Anlageinformationen sowie "
            "Ihres individuellen Investorenprofils."
        ),
    },

    # ── Client information table ──
    "client_info.heading": {"en": "Client information", "de": "Kundeninformationen"},
    "client_info.prepared_by": {"en": "Prepared by", "de": "Erstellt von"},
    "client_info.prepared_by_team": {
        "en": "Teroxx Advisory & Research Department",
        "de": "Teroxx Advisory & Research Department",
    },
    "client_info.consultation_date": {
        "en": "Investment analysis date",
        "de": "Datum der Investitionsanalyse",
    },
    "client_info.client_name": {"en": "Client name", "de": "Name des Kunden"},
    "client_info.country": {"en": "Country", "de": "Land"},
    "client_info.status_level": {"en": "Teroxx status level", "de": "Teroxx Status Level"},

    # ── Risk profile table (Jannick's table 2) ──
    "risk_profile.heading": {"en": "Risk profile", "de": "Risikoprofil"},
    "risk_profile.tolerance": {"en": "Risk tolerance", "de": "Risiko-Toleranz"},
    "risk_profile.horizon": {"en": "Investment horizon", "de": "Anlagehorizont"},
    "risk_profile.objective": {"en": "Primary investment objective", "de": "Primäres Ziel der Investitionen"},
    "risk_profile.tolerance_default.Conservative": {
        "en": "Conservative · focus on long-term capital preservation",
        "de": "Konservativ · Fokus: langfristiger Kapitalerhalt",
    },
    "risk_profile.tolerance_default.Balanced": {
        "en": "Balanced · capital preservation with measured growth",
        "de": "Ausgewogen · Kapitalerhalt mit moderatem Wachstum",
    },
    "risk_profile.tolerance_default.Growth": {
        "en": "Growth · long-term capital appreciation",
        "de": "Wachstumsorientiert · langfristiger Kapitalzuwachs",
    },
    "risk_profile.tolerance_default.Aggressive": {
        "en": "Aggressive · maximum long-term growth, higher volatility tolerated",
        "de": "Aggressiv · maximaler langfristiger Zuwachs, höhere Volatilität toleriert",
    },
    "risk_profile.horizon_default": {
        "en": "Long-term · 5 years and beyond",
        "de": "Langfristig · 5 Jahre und mehr",
    },
    "risk_profile.objective_default": {
        "en": "High-quality digital assets with focus on market leaders.",
        "de": "Hochwertige digitale Anlagen mit Fokus auf Marktführern.",
    },

    # ── Section headers (Jannick's flow) ──
    "page.welcome": {"en": "Welcome", "de": "Willkommen"},
    "page.consultation": {
        "en": "Consultation summary",
        "de": "Zusammenfassung der Beratung",
    },
    "page.market_analysis": {"en": "Market analysis", "de": "Marktanalyse"},
    "page.portfolio_detail": {
        "en": "Your portfolio in detail",
        "de": "Ihr Portfolio im Detail",
    },
    "page.your_new_portfolio": {
        "en": "Your new portfolio",
        "de": "Ihr neues Portfolio",
    },
    "page.strategy": {
        "en": "Investment strategy",
        "de": "Anlagestrategie",
    },
    "page.fazit": {"en": "Conclusion", "de": "Fazit"},
    "page.fees": {"en": "Fee structure", "de": "Gebührenstruktur"},
    "page.contact": {"en": "Contact", "de": "Kontaktinformationen"},
    "page.legal": {"en": "Legal notice", "de": "Rechtlicher Hinweis"},
    "page.appendix_title": {
        "en": "Methodology, data sources and important information",
        "de": "Methodik, Datenquellen und wichtige Informationen",
    },

    # ── Market analysis defaults (left empty when no override; we
    #     don't fabricate market commentary). ──
    "market_analysis.subheading": {
        "en": "Tailored commentary for the current digital-asset market environment.",
        "de": "Individuelle Einordnung des aktuellen Marktumfelds digitaler Vermögenswerte.",
    },
    "page.current_allocation": {
        "en": "Current allocation",
        "de": "Aktuelle Allokation",
    },
    "current_allocation.subheading": {
        "en": "Your existing digital-asset holdings before this proposal.",
        "de": "Ihre aktuellen digitalen Vermögenswerte vor diesem Vorschlag.",
    },
    "current_allocation.placeholder": {
        "en": (
            "_Fill in the client's current digital-asset holdings below. "
            "Leave blank if the client is new to crypto._"
        ),
        "de": (
            "_Tragen Sie die aktuellen Krypto-Bestände des Kunden ein. "
            "Lassen Sie die Tabelle leer, wenn der Kunde neu in Krypto ist._"
        ),
    },
    "consultation.placeholder": {
        "en": (
            "_Describe what was discussed in the consultation: client goals, "
            "constraints, risk concerns, time horizon, and any agreed positioning._"
        ),
        "de": (
            "_Beschreiben Sie, was im Beratungsgespräch besprochen wurde: "
            "Ziele des Kunden, Rahmenbedingungen, Risikoaspekte, Anlagehorizont "
            "und vereinbarte Positionierung._"
        ),
    },
    "market_analysis.placeholder": {
        "en": (
            "_Market analysis to be added by the advisor before sending. "
            "Cover Bitcoin context, Ethereum positioning, institutional flows and stablecoin liquidity "
            "as relevant to this client's mandate._"
        ),
        "de": (
            "_Marktanalyse wird vor dem Versand vom Berater ergänzt. "
            "Behandeln Sie Bitcoin-Kontext, Ethereum-Positionierung, institutionelle Mittelflüsse "
            "und Stablecoin-Liquidität, soweit für das Mandat dieses Kunden relevant._"
        ),
    },

    # ── Conclusion (Fazit) ──
    "fazit.subheading": {
        "en": "Strategic summary and forward view.",
        "de": "Strategische Zusammenfassung und Ausblick.",
    },

    # ── Fees structure (directional from Jannick's table 6) ──
    "fees.subheading": {
        "en": "Fee components applicable to this engagement.",
        "de": "Im Rahmen dieses Mandats anwendbare Gebührenkomponenten.",
    },
    "fees.col_component": {"en": "Component", "de": "Komponente"},
    "fees.col_value": {"en": "Amount", "de": "Betrag"},
    "fees.default_initial": {
        "en": "Initial advisory fee",
        "de": "Initiale Beratungsgebühr",
    },
    "fees.default_trading": {
        "en": "Trading execution fee",
        "de": "Ausführungsgebühr",
    },
    "fees.default_aum": {
        "en": "New assets under management fee",
        "de": "Gebühr auf neu verwaltetes Vermögen",
    },

    # ── Advisor contact ──
    "contact.subheading": {
        "en": "For further information on this proposal, please contact:",
        "de": "Für weitere Informationen zu diesem Vorschlag wenden Sie sich bitte an:",
    },
    "contact.col_advisor": {"en": "Advisor", "de": "Berater"},
    "contact.col_email": {"en": "E-mail", "de": "E-Mail"},
    "contact.col_phone": {"en": "Mobile", "de": "Mobil"},

    # ── Asset-class aggregation table ──
    "assetclass.heading": {
        "en": "Allocation by asset class",
        "de": "Allokation nach Anlageklasse",
    },
    "assetclass.subheading": {
        "en": "Aggregated view across the recommended position list.",
        "de": "Aggregierte Sicht über die empfohlene Positionsliste.",
    },
    "assetclass.col_class": {"en": "Asset class", "de": "Anlageklasse"},
    "assetclass.col_share": {"en": "Allocation %", "de": "Anteil %"},
    "assetclass.total": {"en": "Total", "de": "Gesamt"},
    "assetclass.stablecoins": {"en": "Stablecoins (USDC / EURC)", "de": "Stablecoins (USDC / EURC)"},
    "assetclass.gold": {"en": "Gold hedge (PAXG)", "de": "Gold-Absicherung (PAXG)"},
    "assetclass.sov": {"en": "Store of value (BTC)", "de": "Wertspeicher (BTC)"},
    "assetclass.large_cap": {"en": "Large-cap crypto", "de": "Large-Cap-Crypto"},
    "assetclass.mid_cap": {"en": "Mid-cap crypto", "de": "Mid-Cap-Crypto"},
    "assetclass.small_cap": {"en": "Small-cap / thematic", "de": "Small-Cap / Thematisch"},

    # ── Review flow (existing-client proposals) ──
    "page.current_portfolio": {
        "en": "Current portfolio",
        "de": "Aktuelles Portfolio",
    },
    "page.target_allocation": {
        "en": "Target allocation",
        "de": "Ziel-Allokation",
    },
    "page.drift_analysis": {
        "en": "Drift vs target",
        "de": "Abweichung zum Ziel",
    },
    "page.rebalance": {
        "en": "Recommended rebalance trades",
        "de": "Empfohlene Rebalancing-Trades",
    },
    "current_portfolio.subheading": {
        "en": "Live mark-to-market view of the positions held with Teroxx today.",
        "de": "Live-Marktbewertung der aktuell bei Teroxx gehaltenen Positionen.",
    },
    "current_portfolio.title_with_total": {
        "en": "Total market value: {value}",
        "de": "Gesamtwert: {value}",
    },
    "drift_analysis.subheading": {
        "en": "Per-position deviation between current weight and {profile} target. Threshold for review: {threshold}pp.",
        "de": "Abweichung der aktuellen Gewichtung vom Ziel im Profil {profile}. Überprüfungsgrenze: {threshold} Prozentpunkte.",
    },
    "drift_analysis.max_drift_callout": {
        "en": "Largest deviation: {ticker} at {drift}pp from target. {status}",
        "de": "Größte Abweichung: {ticker} mit {drift} Prozentpunkten zum Ziel. {status}",
    },
    "drift_analysis.attention_yes": {
        "en": "Above the review threshold — rebalance proposal below.",
        "de": "Oberhalb der Überprüfungsgrenze — Rebalancing-Vorschlag siehe unten.",
    },
    "drift_analysis.attention_no": {
        "en": "Within the review threshold — no rebalance triggered.",
        "de": "Innerhalb der Überprüfungsgrenze — kein Rebalancing erforderlich.",
    },
    "rebalance.subheading": {
        "en": "Trades to bring the portfolio back to the {profile} target. Net movement: {net}.",
        "de": "Trades zur Rückführung auf das Profil-Ziel {profile}. Nettobewegung: {net}.",
    },
    "rebalance.no_action": {
        "en": "No material rebalancing trades required at current weights.",
        "de": "Keine wesentlichen Rebalancing-Trades bei den aktuellen Gewichten erforderlich.",
    },
    # Table headers / cells specific to the review flow
    "table.qty": {"en": "Quantity", "de": "Stückzahl"},
    "table.entry_price": {"en": "Avg entry price", "de": "Ø Einstiegspreis"},
    "table.live_price": {"en": "Live price", "de": "Live-Preis"},
    "table.market_value": {"en": "Market value", "de": "Marktwert"},
    "table.cost_basis": {"en": "Cost basis", "de": "Anschaffungskosten"},
    "table.pnl_unrealized": {"en": "Unrealized P&L", "de": "Unrealisiertes Ergebnis"},
    "table.pnl_pct": {"en": "P&L %", "de": "Ergebnis %"},
    "table.weight_now": {"en": "Current %", "de": "Aktuell %"},
    "table.weight_target": {"en": "Target %", "de": "Ziel %"},
    "table.drift_pp": {"en": "Drift pp", "de": "Drift PP"},
    "table.delta_usd": {"en": "Delta", "de": "Delta"},
    "table.action": {"en": "Action", "de": "Aktion"},
    "kpi.total_value": {"en": "Total market value", "de": "Gesamter Marktwert"},
    "kpi.total_cost": {"en": "Total cost basis", "de": "Anschaffungskosten gesamt"},
    "kpi.total_pnl": {"en": "Unrealized P&L", "de": "Unrealisiertes Ergebnis"},
    "kpi.days_held": {"en": "Days held since first entry", "de": "Tage seit erster Position"},
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


# Long-form month names per language. ``strftime("%B")`` follows the process
# locale (always English on our servers), so dates must be formatted from the
# day/month/year parts against this table instead.
_MONTH_NAMES = {
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni",
           "Juli", "August", "September", "Oktober", "November", "Dezember"],
}


def format_long_date(d, lang: str = DEFAULT) -> str:
    """Localise a date/datetime to a long form.

    en → "11 June 2026"   de → "11. Juni 2026"
    """
    months = _MONTH_NAMES.get(lang) or _MONTH_NAMES[DEFAULT]
    month = months[d.month - 1]
    if lang == "de":
        return f"{d.day}. {month} {d.year}"
    return f"{d.day} {month} {d.year}"


__all__ = [
    "DEFAULT",
    "SUPPORTED",
    "resolve_lang",
    "t",
    "profile_label",
    "tier_label",
    "regime_label",
    "format_long_date",
]
