"""Auto-generated narrative copy for the proposal PDF (and reused by HTML).

Each function takes a snapshot of computed data and returns plain-English
strings the template can drop in directly. Tone is advisor-to-advisor:
specific, restrained, no em dashes, no superlatives without numbers.

The same generator feeds Workspace (HTML), Client View (HTML), and the
PDF so wording stays consistent across surfaces. Templates should never
build narrative strings themselves; they call functions from here.
"""
from __future__ import annotations

from typing import Iterable, Optional


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


def cover_subtitle(client_name: str, profile: str, prepared_by: str, date_str: str) -> str:
    """Cover page subtitle below the headline; one line, no punctuation drift."""
    return f"Prepared for {client_name}. {profile} profile. By {prepared_by}, {date_str}."


def exec_action_title(
    *, profile: str, n_assets: int, defensive_pct: float, regime_label: str
) -> str:
    """One-sentence finding for the Executive Summary page."""
    return (
        f"We recommend a {profile} allocation across {n_assets} assets, "
        f"anchored {defensive_pct:.0f}% in defensives, reflecting the current "
        f"{regime_label.lower()} regime."
    )


def allocation_action_title(
    *, top_names: list[str], top_share_pct: float, growth_tier_share_pct: float
) -> str:
    """One-sentence finding for the Recommended Allocation page."""
    top = ", ".join(top_names[:3]) if top_names else "core positions"
    return (
        f"The recommended allocation concentrates {top_share_pct:.0f}% in {top}, "
        f"while reserving {growth_tier_share_pct:.0f}% for selective growth exposure."
    )


def macro_action_title(*, regime_label: str, score: float, bias: str) -> str:
    """One-sentence finding for the Macro Framing page."""
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


def regime_bias(regime_label: str) -> tuple[str, str]:
    """(short_bias_word, explanatory_sentence)."""
    return _BIAS_BY_REGIME.get(regime_label, ("balanced", "Default to a balanced posture until signals confirm a clearer direction."))


def exec_summary_bullets(
    *,
    regime_label: str,
    next_review_weeks: int = 4,
    notable_holdings: Optional[list[str]] = None,
) -> list[str]:
    """The three "What this means" bullets on the Executive Summary page."""
    _, regime_sentence = regime_bias(regime_label)
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
) -> str:
    """Macro page body paragraph, one tight read of the data."""
    _, bias_sentence = regime_bias(regime_label)
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
) -> str:
    """Default implementation note. Editable per-client at the Workspace tab."""
    return (
        f"We suggest a phased build-out: dollar-cost-average new capital into the "
        f"recommended allocation over {dca_weeks} weeks, prioritising defensive "
        f"sleeves first and core L1 second. Once funded, monitor drift against "
        f"target; rebalance when any single position exceeds the target weight by "
        f"{rebalance_threshold_pp} percentage points or more, with a hard cap on "
        f"single-asset concentration aligned to the {profile.lower()} profile."
    )


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
]
