"""Auto-generated narrative copy for the proposal PDF / DOCX / HTML.

Each function takes a snapshot of computed data and returns plain
strings the template can drop in directly. Tone is advisor-to-advisor:
specific, restrained, no em dashes, no superlatives without numbers.

The same generator feeds Workspace (HTML), Client View (HTML), the PDF
and the DOCX so wording stays consistent across surfaces. Templates
should never build narrative strings themselves; they call functions
from here.

Most functions accept an optional ``lang`` ("en"|"de"). DE strings are
working drafts pending Jannick Bröring's review; keep the investment-
advisor register (Sie-Form, formal, restrained).
"""
from __future__ import annotations

from typing import Iterable, Optional

from app.pdf.i18n import profile_label, regime_label, tier_label  # re-export friendly


# ── Helpers ──────────────────────────────────────────────────────────


def _pct(v: Optional[float], digits: int = 1) -> str:
    if v is None:
        return "n/a"
    return f"{v:.{digits}f}%"


def _money(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"${v:,.0f}"


# ── Action titles (top of each page) ────────────────────────────────


def cover_subtitle(client_name: str, profile: str, prepared_by: str, date_str: str, lang: str = "en") -> str:
    """Cover page subtitle below the headline; one line, no punctuation drift."""
    if lang == "de":
        return f"Erstellt für {client_name}. Profil {profile_label(profile, 'de')}. Von {prepared_by}, {date_str}."
    return f"Prepared for {client_name}. {profile} profile. By {prepared_by}, {date_str}."


def exec_action_title(
    *, profile: str, n_assets: int, defensive_pct: float, regime_label: str, lang: str = "en"
) -> str:
    """One-sentence finding for the Executive Summary page."""
    if lang == "de":
        from app.pdf.i18n import regime_label as _regime
        return (
            f"Wir empfehlen eine {profile_label(profile, 'de').lower()}-Allokation über "
            f"{n_assets} Positionen, defensiv verankert zu {defensive_pct:.0f}%, "
            f"im aktuellen Marktregime {_regime(regime_label, 'de')}."
        )
    return (
        f"We recommend a {profile} allocation across {n_assets} assets, "
        f"anchored {defensive_pct:.0f}% in defensives, reflecting the current "
        f"{regime_label.lower()} regime."
    )


def allocation_action_title(
    *, top_names: list[str], top_share_pct: float, growth_tier_share_pct: float, lang: str = "en"
) -> str:
    """One-sentence finding for the Recommended Allocation page."""
    if lang == "de":
        top = ", ".join(top_names[:3]) if top_names else "Kernpositionen"
        return (
            f"Die empfohlene Allokation konzentriert {top_share_pct:.0f}% auf {top} "
            f"und reserviert {growth_tier_share_pct:.0f}% für selektives Wachstumsengagement."
        )
    top = ", ".join(top_names[:3]) if top_names else "core positions"
    return (
        f"The recommended allocation concentrates {top_share_pct:.0f}% in {top}, "
        f"while reserving {growth_tier_share_pct:.0f}% for selective growth exposure."
    )


def basket_exec_action_title(
    *, theme: str, n_assets: int, weighting_label: str, lang: str = "en"
) -> str:
    """Executive-summary finding for a thematic basket (no defensive sleeve)."""
    if lang == "de":
        wl = "nach Marktkapitalisierung" if weighting_label == "market-cap" else "nach Fundamental-Score"
        return (
            f"Wir empfehlen eine vollständig investierte {theme}-Basket über "
            f"{n_assets} Titel, {wl} gewichtet, ohne defensiven Anteil."
        )
    wl = "market-cap" if weighting_label == "market-cap" else "fundamental-score"
    return (
        f"We recommend a fully invested {theme} basket across {n_assets} names, "
        f"{wl} weighted, with no defensive sleeve."
    )


def basket_allocation_action_title(
    *, theme: str, top_names: list[str], top_share_pct: float,
    weighting_label: str, lang: str = "en"
) -> str:
    """Recommended-allocation finding for a thematic basket."""
    top = ", ".join(top_names[:3]) if top_names else (theme + " leaders")
    if lang == "de":
        wl = "nach Marktkapitalisierung" if weighting_label == "market-cap" else "nach Fundamental-Score"
        return (
            f"Die {theme}-Basket gewichtet {wl} und konzentriert {top_share_pct:.0f}% "
            f"auf die drei größten Titel ({top})."
        )
    wl = "market-cap" if weighting_label == "market-cap" else "fundamental-score"
    return (
        f"The {theme} basket is {wl} weighted, with {top_share_pct:.0f}% in its "
        f"three largest names ({top})."
    )


def macro_action_title(*, regime_label: str, score: float, bias: str, lang: str = "en") -> str:
    """One-sentence finding for the Macro Framing page."""
    if lang == "de":
        from app.pdf.i18n import regime_label as _regime
        return (
            f"Das Marktregime liegt bei {_regime(regime_label, 'de')} mit "
            f"{score:.0f}/100 und stützt eine {bias}e Ausrichtung."
        )
    return (
        f"The market regime reads {regime_label.lower()} at {score:.0f}/100, "
        f"supporting a {bias} bias."
    )


# ── Bullets and short paragraphs ────────────────────────────────────


_BIAS_BY_REGIME = {
    "Deep Bear": ("defensive", "Capital preservation comes first; we hold cash-equivalents and gold while waiting for the trend to base."),
    "Late Bear": ("cautious accumulation", "We add to core conviction names at measured pace; the worst is likely behind, but recovery is uneven."),
    "Transition": ("balanced", "Mixed signals warrant a balanced posture: keep defensives intact, accumulate core names on weakness."),
    "Early Bull": ("constructive", "We lean into core L1 and quality DeFi while keeping enough defensive cushion to ride the volatility."),
    "Full Bull": ("growth", "We tilt toward growth tiers and trim defensives at the margin; risk-managed, not risk-on."),
}


_BIAS_BY_REGIME_DE = {
    "Deep Bear": ("defensiv", "Kapitalerhalt steht im Vordergrund; wir halten geldnahe Instrumente und Gold und warten auf eine Bodenbildung des Trends."),
    "Late Bear": ("vorsichtig akkumulierend", "Wir bauen Kernpositionen in geordneten Schritten auf; das Schlimmste liegt vermutlich hinter uns, die Erholung verläuft jedoch uneinheitlich."),
    "Transition": ("ausgewogen", "Gemischte Signale erfordern eine ausgewogene Haltung: defensive Komponenten unverändert halten, Kernpositionen auf Schwäche akkumulieren."),
    "Early Bull": ("konstruktiv", "Wir gewichten Kern-L1 und qualitativ hochwertige DeFi-Positionen stärker, halten aber ausreichend defensive Reserve, um die Volatilität zu tragen."),
    "Full Bull": ("wachstumsorientiert", "Wir gewichten Wachstumsstufen stärker und reduzieren defensive Anteile am Rand; risikobewusst, nicht risiko-aggressiv."),
}


def regime_bias(regime_label: str, lang: str = "en") -> tuple[str, str]:
    """(short_bias_word, explanatory_sentence)."""
    table = _BIAS_BY_REGIME_DE if lang == "de" else _BIAS_BY_REGIME
    default = (
        ("ausgewogen", "Standardmäßig eine ausgewogene Haltung, bis die Signale eine klarere Richtung bestätigen.")
        if lang == "de" else
        ("balanced", "Default to a balanced posture until signals confirm a clearer direction.")
    )
    return table.get(regime_label, default)


def exec_summary_bullets(
    *,
    regime_label: str,
    next_review_weeks: int = 4,
    notable_holdings: Optional[list[str]] = None,
    lang: str = "en",
) -> list[str]:
    """The three "What this means" bullets on the Executive Summary page."""
    # The market-regime read was removed from the proposal (advisor feedback,
    # 2026-06), so the exec summary no longer surfaces a regime-context bullet
    # or a regime-triggered review window — it leads with the allocation
    # rationale and a plain review cadence instead.
    if lang == "de":
        holdings_clause = ""
        if notable_holdings:
            names = ", ".join(notable_holdings[:3])
            holdings_clause = f" Die Kernpositionierung stützt sich auf {names}."
        return [
            f"Die Allokation spiegelt die genannte Risikotoleranz des Kunden und die Hausmeinung der Firma wider." + holdings_clause,
            f"Die Gewichtung folgt dem disziplinierten, mehrstufigen Allokationsmodell von Teroxx.",
            f"Vorgeschlagener nächster Überprüfungszeitpunkt: in {next_review_weeks} Wochen "
            f"oder früher bei wesentlichen Marktbewegungen.",
        ]
    holdings_clause = ""
    if notable_holdings:
        names = ", ".join(notable_holdings[:3])
        holdings_clause = f" Core positioning anchors on {names}."
    return [
        f"The allocation reflects the client's stated risk tolerance and the firm's house view." + holdings_clause,
        f"Weightings follow Teroxx's disciplined, multi-tier allocation model.",
        f"Suggested next portfolio review window: in {next_review_weeks} weeks, "
        f"or sooner on material market moves.",
    ]


def macro_paragraph(
    *,
    regime_label: str,
    score: float,
    sources_available: int,
    sources_total: int,
    lang: str = "en",
) -> str:
    """Macro page body paragraph, one tight read of the data."""
    _, bias_sentence = regime_bias(regime_label, lang=lang)
    if lang == "de":
        from app.pdf.i18n import regime_label as _regime
        return (
            f"Das Komposit liegt bei {score:.0f}/100 ({_regime(regime_label, 'de')}) und aggregiert "
            f"{sources_available} von {sources_total} Indikatoren über Sentiment, "
            f"traditionelle Märkte, On-Chain-Aktivität und Technik. {bias_sentence}"
        )
    return (
        f"The composite reads {score:.0f}/100 ({regime_label}), aggregating "
        f"{sources_available} of {sources_total} indicators across sentiment, "
        f"traditional markets, on-chain activity and technicals. {bias_sentence}"
    )


def market_analysis_draft(
    *,
    regime_label: str,
    score: float,
    sources_available: int,
    sources_total: int,
    profile: str,
    btc_pct: float = 0.0,
    defensive_pct: float = 0.0,
    anchor_names: Optional[Iterable[str]] = None,
    top_indicators: Optional[list[dict]] = None,
    next_review_weeks: int = 4,
    lang: str = "en",
) -> str:
    """A ready-to-edit DRAFT of the long-form market analysis.

    The market-analysis slot is the section the advisor invests the most
    time in; leaving it blank reads as unfinished. This generates a
    sober, general digital-asset market read grounded in the current
    macro composite and this client's allocation, covering the four
    themes the advisor is expected to address (Bitcoin context, Ethereum /
    higher-beta positioning, institutional flows and stablecoin
    liquidity). It is explicitly a starting point: the advisor edits it
    before sending. Returns markdown (blank-line-separated paragraphs).
    No hard price calls — those age badly between generation and send.
    """
    _, bias_sentence = regime_bias(regime_label, lang=lang)
    names = [n for n in (anchor_names or []) if n]
    names_clause = ", ".join(names[:4])
    inds = top_indicators or []
    lead = inds[0] if inds else None

    if lang == "de":
        from app.pdf.i18n import regime_label as _regime
        regime_de = _regime(regime_label, "de")
        lead_sentence = (
            f" Das deutlichste Einzelsignal ist aktuell {lead.get('label')} "
            f"({float(lead.get('score', 50)):.0f}/100)." if lead else ""
        )
        names_sentence = (
            f" Diese Beta-Schicht umfasst Positionen wie {names_clause}." if names_clause else ""
        )
        return "\n\n".join([
            (
                f"**Marktregime.** Das Teroxx-Makrokomposit liegt bei {score:.0f}/100 "
                f"({regime_de}) und aggregiert {sources_available} von {sources_total} "
                f"Indikatoren über Sentiment, traditionelle Märkte, On-Chain-Aktivität "
                f"und Technik.{lead_sentence} {bias_sentence}"
            ),
            (
                f"**Bitcoin.** Bitcoin bleibt der strategische Anker des Marktes für "
                f"digitale Vermögenswerte und dieser Allokation mit {btc_pct:.0f}%. Als "
                f"liquidestes und qualitativ hochwertigstes Krypto-Asset trägt es das "
                f"geringste idiosynkratische Risiko im Portfolio; die zunehmende "
                f"institutionelle Adoption über Spot-ETFs und Unternehmensbestände "
                f"vertieft die Liquidität weiter. Wir behandeln Bitcoin als Kern-"
                f"Wertaufbewahrungsposition, um die herum das übrige Portfolio "
                f"dimensioniert wird."
            ),
            (
                f"**Ethereum und höheres Beta.** Ethereum und die breitere Smart-Contract-"
                f"Ebene liefern die produktive, höher gehebelte Exponierung des "
                f"Portfolios. Aktivität auf Ethereum und konkurrierenden Layer-1-/Layer-2-"
                f"Netzwerken — Staking, Stablecoin-Settlement und tokenisierte Real-World-"
                f"Assets — untermauert die mittleren Positionen.{names_sentence} Diese "
                f"Werte verstärken Auf- und Abwärtsbewegungen gegenüber Bitcoin und sind "
                f"daher unterhalb des Kerns und gemäß dem Risikobudget "
                f"({profile_label(profile, 'de')}) gewichtet."
            ),
            (
                f"**Stablecoin-Liquidität und defensive Haltung.** Die defensive Schicht "
                f"von {defensive_pct:.0f}% (USDC, EURC, PAXG) sichert Kaufkraft und hält "
                f"Pulver trocken, um bei Volatilität zu investieren. Das Stablecoin-"
                f"Angebot ist ein nützlicher Indikator für wartendes Kapital; ein "
                f"wachsendes Angebot ging historisch Risk-on-Rotationen voraus. Wir "
                f"überprüfen diese Markteinschätzung beim nächsten Review in rund "
                f"{next_review_weeks} Wochen oder früher bei einer wesentlichen "
                f"Veränderung des Komposits."
            ),
        ])

    lead_sentence = (
        f" The single strongest read is {lead.get('label')} "
        f"({float(lead.get('score', 50)):.0f}/100)." if lead else ""
    )
    names_sentence = (
        f" This beta sleeve includes positions such as {names_clause}." if names_clause else ""
    )
    return "\n\n".join([
        (
            f"**Market regime.** The Teroxx macro composite currently reads "
            f"{score:.0f}/100 ({regime_label}), aggregating {sources_available} of "
            f"{sources_total} indicators across sentiment, traditional markets, "
            f"on-chain activity and technicals.{lead_sentence} {bias_sentence}"
        ),
        (
            f"**Bitcoin.** Bitcoin remains the strategic anchor of the digital-asset "
            f"market and of this allocation at {btc_pct:.0f}%. As the most liquid, "
            f"highest-quality crypto asset it carries the lowest idiosyncratic risk in "
            f"the book; deepening institutional adoption through spot ETFs and corporate "
            f"treasuries continues to broaden its liquidity and shorten drawdown "
            f"recoveries. We treat Bitcoin as the core store-of-value position around "
            f"which the rest of the portfolio is sized."
        ),
        (
            f"**Ethereum and higher beta.** Ethereum and the broader smart-contract "
            f"layer provide the portfolio's productive, higher-beta exposure. Activity "
            f"across Ethereum and competing Layer 1 / Layer 2 networks — staking, "
            f"stablecoin settlement and tokenised real-world assets — underpins the "
            f"mid-tier positions.{names_sentence} These names amplify both upside and "
            f"drawdown relative to Bitcoin, which is why they sit below the core and are "
            f"scaled to the {profile.lower()} risk budget."
        ),
        (
            f"**Stablecoin liquidity and defensive posture.** On the defensive side, the "
            f"{defensive_pct:.0f}% stablecoin and gold-hedge sleeve (USDC, EURC, PAXG) "
            f"preserves purchasing power and keeps dry powder ready to deploy into "
            f"volatility. Stablecoin supply is a useful proxy for capital waiting on the "
            f"sidelines; expanding supply has historically preceded risk-on rotations. "
            f"We will revisit this read at the next review in roughly "
            f"{next_review_weeks} weeks, or sooner on a material change in the composite."
        ),
    ])


def implementation_default(
    *,
    profile: str,
    dca_weeks: int = 6,
    rebalance_threshold_pp: int = 5,
    lang: str = "en",
    basket_theme: str = "",
) -> str:
    """Default implementation note. Editable per-client at the Workspace tab.

    When `basket_theme` is set the note describes a single-theme index basket
    (no defensive sleeve, weight-drift rebalancing) instead of the profiled
    sleeve-first build-out."""
    if basket_theme:
        if lang == "de":
            return (
                f"Wir empfehlen einen gestaffelten Aufbau: Neues Kapital wird über "
                f"{dca_weeks} Wochen im Cost-Average-Verfahren vollständig in die "
                f"{basket_theme}-Basket investiert, gewichtet gemäß der gewählten "
                f"Methodik. Nach vollständiger Investition wird die Abweichung "
                f"gegenüber den Zielgewichten überwacht; ein Rebalancing wird "
                f"vorgeschlagen, sobald eine Einzelposition ihr Zielgewicht um "
                f"{rebalance_threshold_pp} Prozentpunkte oder mehr überschreitet."
            )
        return (
            f"We suggest a phased build-out: dollar-cost-average new capital fully "
            f"into the {basket_theme} basket over {dca_weeks} weeks, weighted per the "
            f"chosen methodology. Once funded, monitor drift against the target "
            f"weights; rebalance when any single position exceeds its target weight "
            f"by {rebalance_threshold_pp} percentage points or more. The basket holds "
            f"no defensive sleeve, so position in line with the client's overall "
            f"risk budget at the portfolio level."
        )
    if lang == "de":
        return (
            f"Wir empfehlen einen gestaffelten Aufbau: Neues Kapital wird über "
            f"{dca_weeks} Wochen im Cost-Average-Verfahren in die empfohlene Allokation "
            f"investiert, wobei zuerst die defensiven Komponenten und anschließend die "
            f"Kern-Layer-1-Positionen aufgebaut werden. Nach vollständiger Investition "
            f"wird die Abweichung gegenüber dem Ziel überwacht; ein Rebalancing wird "
            f"vorgeschlagen, sobald eine Einzelposition das Zielgewicht um "
            f"{rebalance_threshold_pp} Prozentpunkte oder mehr überschreitet, mit einer "
            f"festen Obergrenze für Einzelpositionskonzentration entsprechend dem "
            f"Profil {profile_label(profile, 'de')}."
        )
    return (
        f"We suggest a phased build-out: dollar-cost-average new capital into the "
        f"recommended allocation over {dca_weeks} weeks, prioritising defensive "
        f"sleeves first and core L1 second. Once funded, monitor drift against "
        f"target; rebalance when any single position exceeds the target weight by "
        f"{rebalance_threshold_pp} percentage points or more, with a hard cap on "
        f"single-asset concentration aligned to the {profile.lower()} profile."
    )


def client_review_narrative(
    *,
    client_name: str,
    profile: str,
    is_up: bool,
    total_pnl_pct: float,
    days_held: int,
    n_unique_tickers: int,
    regime_label: str,
    score: Optional[float],
    next_review_weeks: int = 4,
) -> dict:
    """Three paragraphs for the client-facing Review page.

    Tone: read out loud to a non-specialist. Reads from the same regime
    state but lands the point in plain English, not jargon.
    """
    bias_word, regime_sentence = regime_bias(regime_label)
    direction = "up" if is_up else "down"
    magnitude = abs(total_pnl_pct)
    portfolio = (
        f"Your portfolio is {direction} {magnitude:.1f}% over {days_held} days, "
        f"spread across {n_unique_tickers} positions consistent with the "
        f"{profile.lower()} mandate. We mark to live market prices once per minute; "
        f"the allocation shown below reflects today's values."
    )
    score_clause = f" The composite score reads {int(score)} out of 100." if score is not None else ""
    macro = (
        f"The broader market is in a {regime_label.lower()} regime.{score_clause} "
        f"{regime_sentence}"
    )
    next_focus = (
        f"At the next review window in roughly {next_review_weeks} weeks, we will "
        f"check whether the allocation has drifted beyond the {profile.lower()} "
        f"profile thresholds and confirm the macro read still supports a "
        f"{bias_word} posture. Anything material in between is flagged here."
    )
    return {"portfolio": portfolio, "macro": macro, "next": next_focus}


def rationale_paragraph(template: str, signals: dict) -> str:
    """Fill a per-asset rationale template with live signal placeholders.

    Missing keys collapse to "n/a"; unrecognised placeholders leave the
    template text untouched so we never display "{foo}" raw.
    """
    class _SafeDict(dict):
        def __missing__(self, key):
            return "n/a"
    try:
        return template.format_map(_SafeDict(signals))
    except Exception:
        return template


__all__ = [
    "cover_subtitle",
    "exec_action_title",
    "allocation_action_title",
    "macro_action_title",
    "exec_summary_bullets",
    "macro_paragraph",
    "market_analysis_draft",
    "regime_bias",
    "implementation_default",
    "rationale_paragraph",
    "client_review_narrative",
]
