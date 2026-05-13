"""Assembly point for the proposal PDF render context.

The route handler at `/api/clients/{id}/proposal.{html,pdf}` is thin: it
loads the client, gathers the inputs (live prices, allocation, macro
state) and asks `build_proposal_context()` to assemble the dict that
`proposal.html` consumes. This separation keeps the route easy to test
and keeps the template free of business logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from app.data import (
    ASSET_REGULATORY_FLAGS, DISCLAIMERS, RATIONALE_LIBRARY, RATIONALE_TAGS,
    ASSET_BY_TICKER, get_alloc_tier,
)
from app.engine import compute_allocations
from app.pdf.exhibits import (
    donut, donut_legend, tier_bar, regime_gauge,
)
from app.pdf.narrative import (
    cover_subtitle, exec_action_title, allocation_action_title, macro_action_title,
    exec_summary_bullets, macro_paragraph, implementation_default,
    rationale_paragraph, regime_bias,
)
from app.pdf.palette import PALETTE


TIER_LABELS = {
    "Fixed": "Defensive",
    "Store of Value": "Core",
    "Large Cap": "Large Cap",
    "Mid Cap": "Mid Cap",
    "Small Cap": "Small Cap",
}


@dataclass
class ProposalInputs:
    client: dict
    profile: str
    universe: str
    portfolio_value: float
    prepared_by: str
    prepared_date: str
    macro_state: dict
    spot_prices: dict[str, float]  # {ticker: live_price_or_None}


def _abs_static_path(rel: str) -> str:
    """Return a file:// URL pointing into app/static/.

    WeasyPrint resolves URLs against the document base, but cross-platform
    `file://` paths are easier when we render strings directly.
    """
    root = Path(__file__).resolve().parents[1] / "static"
    return (root / rel).as_uri()


def build_proposal_context(inp: ProposalInputs) -> dict[str, Any]:
    client = inp.client
    profile = inp.profile or client.get("profile", "Balanced")
    universe = inp.universe
    portfolio_value = float(inp.portfolio_value or 100_000)

    # 1. Target allocation from the engine. Drop zero-weighted rows.
    allocs_raw = compute_allocations(profile, universe, mode="Standard")
    allocs = [a for a in allocs_raw if (a.get("alloc_pct") or 0) > 0]
    allocs.sort(key=lambda a: -float(a.get("alloc_pct") or 0))

    # 2. Tier rollup (for the tier_bar exhibit).
    tier_totals: dict[str, float] = {}
    for a in allocs:
        tier = a.get("tier") or get_alloc_tier(a["ticker"])
        tier_totals[tier] = tier_totals.get(tier, 0.0) + float(a.get("alloc_pct") or 0)
    tier_pairs = sorted(tier_totals.items(), key=lambda kv: -kv[1])
    tier_pairs_labeled = [(TIER_LABELS.get(t, t), v) for t, v in tier_pairs]

    # 3. Donut + legend. Centre prints the position count so it's useful
    # to the reader rather than tautological.
    donut_slices = [(a["ticker"], float(a.get("alloc_pct") or 0) * 100) for a in allocs]
    donut_svg = donut(
        donut_slices,
        width=240, height=240,
        center_text=f"{len(allocs)}",
        center_sub="positions",
    )
    legend = donut_legend(donut_slices)

    tier_bar_svg = tier_bar(tier_pairs_labeled)

    # 4. Allocation table rows.
    alloc_rows = []
    for a in allocs:
        ticker = a["ticker"]
        target_pct = float(a.get("alloc_pct") or 0) * 100
        target_usd = (target_pct / 100) * portfolio_value
        flags = ASSET_REGULATORY_FLAGS.get(ticker, [])
        tier_label = TIER_LABELS.get(a.get("tier"), a.get("tier") or "—")
        alloc_rows.append({
            "ticker": ticker,
            "name": a.get("name") or ASSET_BY_TICKER.get(ticker, {}).get("name", ticker),
            "tier": a.get("tier"),
            "tier_label": tier_label,
            "target_pct": target_pct,
            "target_usd": target_usd,
            "flags": flags,
            "rationale_tag": RATIONALE_TAGS.get(ticker, ""),
        })

    # 5. Defensive / growth split for the executive summary.
    defensive_pct = sum(r["target_pct"] for r in alloc_rows if r["tier"] == "Fixed")
    growth_pct = sum(r["target_pct"] for r in alloc_rows if r["tier"] in ("Mid Cap", "Small Cap"))
    top_names = [r["ticker"] for r in alloc_rows[:3]]
    top_share = sum(r["target_pct"] for r in alloc_rows[:3])

    # 6. Macro framing.
    r = (inp.macro_state or {}).get("result") or {}
    regime_label = r.get("regime_label") or "Transition"
    score = float(r.get("composite_score") or 50)
    regime_color = r.get("regime_color") or PALETTE.electric_sky
    sources_available = r.get("sources_available") or 0
    sources_total = r.get("sources_total") or 22

    regime_gauge_svg = regime_gauge(score, label=regime_label, color=regime_color)
    macro_paragraph_text = macro_paragraph(
        regime_label=regime_label, score=score,
        sources_available=sources_available, sources_total=sources_total,
    )
    bias_word, _ = regime_bias(regime_label)

    # Pick the 6 most decisive indicators (highest absolute distance from 50).
    indicators = (inp.macro_state or {}).get("indicators") or []
    scores_map = r.get("scores") or {}
    decisive = []
    for ind in indicators:
        key = ind.get("key")
        s_val = scores_map.get(key) if key else None
        if s_val is None:
            continue
        decisive.append({
            "label": ind.get("label"),
            "category": ind.get("category"),
            "score": float(s_val),
            "abs_dev": abs(float(s_val) - 50),
        })
    decisive.sort(key=lambda x: -x["abs_dev"])
    top_indicators = decisive[:6]

    # 7. Per-asset rationale chunks (2 per page).
    rationale_pages: list[list[dict]] = []
    chunk: list[dict] = []
    for row in alloc_rows:
        ticker = row["ticker"]
        lib_entry = RATIONALE_LIBRARY.get(ticker)
        if not lib_entry:
            continue
        # Live signal placeholders: kept conservative so we never claim a
        # spec piece of data we don't have. Phase 3 ships with three
        # generic placeholders; later phases enrich with real signal feeds.
        signals = {
            "fees_30d_change": "n/a",
            "tvl": "n/a",
            "va_score": "n/a",
        }
        body = rationale_paragraph(lib_entry["body"], signals)
        chunk.append({
            "ticker": ticker,
            "name": row["name"],
            "tag": lib_entry.get("tag", row.get("rationale_tag", "")),
            "headline": lib_entry.get("headline", ""),
            "body": body,
            "target_pct": row["target_pct"],
            "current_price": (inp.spot_prices or {}).get(ticker),
        })
        if len(chunk) == 2:
            rationale_pages.append(chunk)
            chunk = []
    if chunk:
        rationale_pages.append(chunk)

    # 8. Narrative titles.
    exec_title = exec_action_title(
        profile=profile, n_assets=len(alloc_rows),
        defensive_pct=defensive_pct, regime_label=regime_label,
    )
    exec_bullets = exec_summary_bullets(
        regime_label=regime_label, notable_holdings=top_names,
    )
    allocation_title = allocation_action_title(
        top_names=top_names, top_share_pct=top_share,
        growth_tier_share_pct=growth_pct,
    )
    macro_title = macro_action_title(
        regime_label=regime_label, score=score, bias=bias_word,
    )

    cover_sub = cover_subtitle(
        client_name=client.get("name", ""),
        profile=profile, prepared_by=inp.prepared_by, date_str=inp.prepared_date,
    )
    implementation_text = client.get("implementation_note") or implementation_default(profile=profile)

    # 9. Disclaimer block based on domicile.
    domicile_key = (client.get("domicile_country") or "").upper()
    disclaimer = DISCLAIMERS.get(domicile_key) or DISCLAIMERS["default"]

    # Read the brand mark SVG into the template so WeasyPrint embeds it
    # alongside the rest of the document.
    try:
        mark_path = Path(__file__).resolve().parents[1] / "static" / "img" / "teroxx-mark.svg"
        teroxx_mark = mark_path.read_text(encoding="utf-8")
    except OSError:
        teroxx_mark = ""

    return {
        "client": client,
        "universe": universe,
        "portfolio_value": portfolio_value,
        "prepared_by": inp.prepared_by,
        "prepared_date": inp.prepared_date,
        "cover_subtitle": cover_sub,
        "exec_title": exec_title,
        "exec_bullets": exec_bullets,
        "allocation_count": len(alloc_rows),
        "defensive_pct": defensive_pct,
        "donut_svg": donut_svg,
        "donut_legend": legend,
        "allocation_title": allocation_title,
        "allocation_rows": alloc_rows,
        "tier_bar_svg": tier_bar_svg,
        "macro_title": macro_title,
        "regime_gauge_svg": regime_gauge_svg,
        "macro_paragraph_text": macro_paragraph_text,
        "top_indicators": top_indicators,
        "rationale_pages": rationale_pages,
        "implementation_text": implementation_text,
        "disclaimer": disclaimer,
        "teroxx_mark": teroxx_mark,
        # Helper for the template's <link rel="stylesheet" href="{{ static_url(...) }}">
        "static_url": lambda rel: _abs_static_path(rel),
    }


def render_pdf(ctx: dict[str, Any], html_only: bool = False) -> bytes | str:
    """Render the proposal template to PDF bytes (or HTML string for preview)."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("proposal.html")
    html = tpl.render(**ctx)
    if html_only:
        return html
    # Lazy import so the module is loadable without the system deps for
    # local dev / tests that only exercise the assembly path.
    from weasyprint import HTML
    base_url = str(Path(__file__).resolve().parents[1])  # app/
    return HTML(string=html, base_url=base_url).write_pdf()
