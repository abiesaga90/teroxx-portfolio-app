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
    _, regime_sentence = regime_bias(regime_label, lang=lang)
    if lang == "de":
        holdings_clause = ""
        if notable_holdings:
            names = ", ".join(notable_holdings[:3])
            holdings_clause = f" Die Kernpositionierung stützt sich auf {names}."
        return [
            f"Die Allokation spiegelt die genannte Risikotoleranz des Kunden und die Hausmeinung der Firma wider." + holdings_clause,
            f"Regime-Kontext: {regime_sentence}",
            f"Vorgeschlagener nächster Überprüfungszeitpunkt: in {next_review_weeks} Wochen "
            f"oder früher, sobald sich das Regime-Komposit um mehr als 10 Punkte verschiebt.",
        ]
    holdings_clause = ""
    if notable_holdings:
        names = ", ".join(notable_holdings[:3])
        holdings_clause = f" Core positioning anchors on {names}."
    return [
        f"The allocation reflects the client's stated risk tolerance and the firm's house view." + holdings_clause,
        f"Regime context: {regime_sentence}",
        f"Suggested next portfolio review window: in {next_review_weeks} weeks, "
        f"or sooner if the regime composite shifts by more than 10 points.",
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


def implementation_default(
    *,
    profile: str,
    dca_weeks: int = 6,
    rebalance_threshold_pp: int = 5,
    lang: str = "en",
) -> str:
    """Default implementation note. Editable per-client at the Workspace tab."""
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
    "regime_bias",
    "implementation_default",
    "rationale_paragraph",
    "client_review_narrative",
]
