"""Assembly point for the proposal render context.

`build_proposal_context()` gathers the inputs (live prices, allocation,
macro state) and assembles the dict that `render_docx()` consumes.

The DOCX is the single source of truth for the proposal: the PDF and
Google Docs outputs are conversions of it (docx_to_pdf.py, google_docs.py),
so the three outputs cannot drift apart. Do not add a separate PDF or
HTML renderer here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from app.data import (
    ASSET_REGULATORY_FLAGS, DISCLAIMERS, RATIONALE_LIBRARY, RATIONALE_TAGS,
    ASSET_BY_TICKER, get_alloc_tier, THEMATIC_BASKETS,
)
from app.engine import (
    compute_allocations, compute_dca,
    compute_client_portfolio_pnl, compute_client_drift, compute_rebalance_pnl,
)
from app.pdf.exhibits import (
    donut, donut_legend, tier_bar, regime_gauge,
)
from app.pdf.i18n import (
    resolve_lang, t, profile_label, tier_label as _i18n_tier_label,
    regime_label as _i18n_regime_label,
)
from app.pdf.narrative import (
    cover_subtitle, exec_action_title, allocation_action_title, macro_action_title,
    exec_summary_bullets, macro_paragraph, implementation_default,
    rationale_paragraph, regime_bias,
    basket_exec_action_title, basket_allocation_action_title,
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
    # Proposal language ("en"|"de"). When None, resolved from
    # client.proposal_language → client.domicile_country → "en".
    lang: Optional[str] = None
    # Optional per-render overrides (also stored on the client record).
    # Per-render values take precedence; missing fields fall through to
    # whatever is on client["proposal_overrides"].
    overrides: Optional[dict] = None
    # Optional phased-build / DCA parameters. When set, the proposal
    # renders a "Phased build" section using compute_dca() output.
    #   {"monthly_amount": 10000, "scope": "all", "horizon_months": 6, "min_order": 100}
    dca: Optional[dict] = None
    # Proposal flavour:
    #   "new"    → onboarding allocation proposal (default, current
    #               behaviour). Client.lots is ignored.
    #   "review" → existing-client review. Pulls client.lots, computes
    #               live mark-to-market P&L, drift vs target and a
    #               rebalance trade list. Heading wording shifts from
    #               "Recommended allocation" to "Target allocation".
    proposal_type: str = "new"
    # Allocation mode passed to the engine: "Standard" (equal-weight
    # within tier) or "Fundamental"/"VA Model"/"Enhanced Model"
    # (factor-weighted). Must mirror whatever the advisor selected on the
    # Portfolio tab, otherwise the proposal weights drift from the screen.
    mode: str = "Standard"


# Asset-class buckets for the directional summary table. The mapping
# is deliberately coarse to match what an HNW client sees in a paper
# proposal (Jannick's template table 4): six buckets, not the full
# per-ticker list. Any ticker not mapped lands in "Small-cap / thematic".
_ASSET_CLASS_BUCKETS = (
    ("stablecoins", "assetclass.stablecoins",
     ("USDC", "USDT", "EURC", "DAI", "FDUSD", "PYUSD")),
    ("gold", "assetclass.gold", ("PAXG", "XAUT")),
    ("sov", "assetclass.sov", ("BTC",)),
    ("large_cap", "assetclass.large_cap",
     ("ETH", "BNB", "XRP", "ADA", "SOL", "DOGE", "TRX", "LINK", "TON")),
    ("mid_cap", "assetclass.mid_cap",
     ("POL", "AVAX", "DOT", "LTC", "SUI", "ATOM", "NEAR", "APT", "HBAR",
      "ICP", "ARB", "OP", "FIL", "AAVE", "UNI", "MKR", "RENDER", "FET",
      "TAO", "PENDLE", "ENA", "ONDO", "QNT", "MNT", "HYPE")),
)


def _aggregate_asset_classes(rows: list[dict], *, lang: str) -> list[dict]:
    """Bucket per-ticker rows into the six asset-class summary rows."""
    from app.pdf.i18n import t as _t
    totals: dict[str, float] = {key: 0.0 for key, _, _ in _ASSET_CLASS_BUCKETS}
    totals["small_cap"] = 0.0
    ticker_to_bucket: dict[str, str] = {}
    for key, _, tickers in _ASSET_CLASS_BUCKETS:
        for tk in tickers:
            ticker_to_bucket[tk] = key
    for r in rows:
        tk = (r.get("ticker") or "").upper()
        bucket = ticker_to_bucket.get(tk, "small_cap")
        totals[bucket] += float(r.get("target_pct") or 0)
    labels = {
        "stablecoins": "assetclass.stablecoins",
        "gold": "assetclass.gold",
        "sov": "assetclass.sov",
        "large_cap": "assetclass.large_cap",
        "mid_cap": "assetclass.mid_cap",
        "small_cap": "assetclass.small_cap",
    }
    out = []
    for key in ("stablecoins", "gold", "sov", "large_cap", "mid_cap", "small_cap"):
        share = totals.get(key, 0.0)
        out.append({
            "key": key,
            "label": _t(labels[key], lang),
            "share_pct": share,
        })
    return out


def _aggregate_basket_categories(rows: list[dict]) -> list[dict]:
    """For thematic baskets, group the 'by asset class' table by each
    token's own category (e.g. DeFi / DEX) rather than the profile macro
    buckets, which would collapse a whole sector basket into one row."""
    totals: dict[str, float] = {}
    for r in rows:
        asset = ASSET_BY_TICKER.get((r.get("ticker") or "").upper(), {})
        cat = (r.get("category") or asset.get("category") or "Other").strip() or "Other"
        totals[cat] = totals.get(cat, 0.0) + float(r.get("target_pct") or 0)
    return [
        {"key": cat, "label": cat, "share_pct": share}
        for cat, share in sorted(totals.items(), key=lambda kv: -kv[1])
    ]


def build_proposal_context(inp: ProposalInputs) -> dict[str, Any]:
    client = inp.client
    profile = inp.profile or client.get("profile", "Balanced")
    universe = inp.universe
    portfolio_value = float(inp.portfolio_value or 100_000)
    mode_use = inp.mode or "Standard"

    # 0a. Resolve language: explicit input > client record > domicile > EN.
    lang = resolve_lang(
        requested=inp.lang or client.get("proposal_language"),
        domicile_country=client.get("domicile_country"),
    )

    # 0b. Per-client overrides. Per-render dict beats stored record.
    stored_overrides = client.get("proposal_overrides") or {}
    if isinstance(stored_overrides, str):
        try:
            import json as _json
            stored_overrides = _json.loads(stored_overrides) or {}
        except Exception:
            stored_overrides = {}
    overrides = {**stored_overrides, **(inp.overrides or {})}
    excluded_tickers = {
        (s or "").strip().upper()
        for s in (overrides.get("excluded_tickers") or [])
        if s
    }

    # 1. Target allocation from the engine. Drop zero-weighted rows and
    #    any tickers excluded by the client.
    allocs_raw = compute_allocations(profile, universe, mode=mode_use)
    allocs = [
        a for a in allocs_raw
        if (a.get("alloc_pct") or 0) > 0
        and a.get("ticker", "").upper() not in excluded_tickers
    ]
    allocs.sort(key=lambda a: -float(a.get("alloc_pct") or 0))

    # If excluding any tickers materially shrinks the universe, renormalise
    # so the remaining weights sum back to 100%. Otherwise the displayed
    # alloc_pct values would not sum to 100% and the donut/exhibits would
    # look broken.
    if excluded_tickers and allocs:
        total = sum(float(a.get("alloc_pct") or 0) for a in allocs)
        if 0 < total < 1.0:
            for a in allocs:
                a["alloc_pct"] = float(a.get("alloc_pct") or 0) / total

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
        lang=lang,
    )
    bias_word, _ = regime_bias(regime_label, lang=lang)

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
        if len(chunk) == 4:
            rationale_pages.append(chunk)
            chunk = []
    if chunk:
        rationale_pages.append(chunk)

    # 8. Narrative titles (lang-aware). Thematic baskets are pure in-theme
    #    index products (no defensive sleeve), so they use index-product
    #    wording instead of the profile/sleeve framing.
    is_basket = universe in THEMATIC_BASKETS
    theme_label = universe.replace(" Basket", "") if is_basket else ""
    weighting_label = "market-cap" if mode_use == "Standard" else "fundamental-score"
    if is_basket:
        exec_title = basket_exec_action_title(
            theme=theme_label, n_assets=len(alloc_rows),
            weighting_label=weighting_label, lang=lang,
        )
        allocation_title = basket_allocation_action_title(
            theme=theme_label, top_names=top_names, top_share_pct=top_share,
            weighting_label=weighting_label, lang=lang,
        )
    else:
        exec_title = exec_action_title(
            profile=profile, n_assets=len(alloc_rows),
            defensive_pct=defensive_pct, regime_label=regime_label, lang=lang,
        )
        allocation_title = allocation_action_title(
            top_names=top_names, top_share_pct=top_share,
            growth_tier_share_pct=growth_pct, lang=lang,
        )
    exec_bullets = exec_summary_bullets(
        regime_label=regime_label, notable_holdings=top_names, lang=lang,
    )
    macro_title = macro_action_title(
        regime_label=regime_label, score=score, bias=bias_word, lang=lang,
    )

    cover_sub = cover_subtitle(
        client_name=client.get("name", ""),
        profile=profile, prepared_by=inp.prepared_by, date_str=inp.prepared_date,
        lang=lang,
    )
    implementation_text = client.get("implementation_note") or implementation_default(
        profile=profile, lang=lang, basket_theme=(theme_label if is_basket else ""),
    )

    # 9. Disclaimer block based on domicile + language. DISCLAIMERS may
    # be keyed by either "DE" or ("DE", "de") depending on what's in
    # data.py; we try the lang-aware key first, then the legacy key.
    domicile_key = (client.get("domicile_country") or "").upper()
    disclaimer = (
        DISCLAIMERS.get((domicile_key, lang))
        or DISCLAIMERS.get(f"{domicile_key}.{lang}")
        or DISCLAIMERS.get(domicile_key)
        or DISCLAIMERS.get(("default", lang))
        or DISCLAIMERS.get(f"default.{lang}")
        or DISCLAIMERS["default"]
    )

    # 9b. Review-flow payload: current holdings + P&L + drift +
    #     recommended rebalance trades. Only computed when the proposal
    #     is being rendered for an existing client (proposal_type=review)
    #     so the new-client onboarding path stays lightweight.
    proposal_type = (inp.proposal_type or "new").strip().lower()
    if proposal_type not in ("new", "review"):
        proposal_type = "new"
    review_payload: dict = {}
    if proposal_type == "review":
        try:
            pnl = compute_client_portfolio_pnl(client)
        except Exception:
            pnl = {"summary": {}, "rows": [], "by_ticker": []}
        try:
            drift = compute_client_drift(client, profile=profile, universe=universe)
        except Exception:
            drift = {"rows": [], "max_drift_pp": 0, "max_drift_ticker": None,
                     "threshold_pp": 0, "attention": False}
        # Build the {ticker → {current_usd, entry_price}} dict that
        # compute_rebalance_pnl() expects. Aggregate across lots.
        positions_agg: dict[str, dict] = {}
        for r in (pnl.get("rows") or []):
            tk = (r.get("ticker") or "").upper()
            bucket = positions_agg.setdefault(tk, {"current_usd": 0.0, "cost": 0.0, "qty": 0.0})
            bucket["current_usd"] += float(r.get("current_value") or 0)
            bucket["cost"] += float(r.get("cost_basis") or 0)
            bucket["qty"] += float(r.get("quantity") or 0)
        for tk, bucket in positions_agg.items():
            qty = bucket["qty"] or 0
            bucket["entry_price"] = (bucket["cost"] / qty) if qty else 0
        # The denominator the renderer should use for the review:
        # whichever is bigger between the prospective portfolio_value
        # and the client's live MTM. This way a partially-funded
        # client still shows the full target.
        live_value = float(pnl.get("summary", {}).get("total_value") or 0)
        review_pv = max(portfolio_value, live_value) if live_value > 0 else portfolio_value
        try:
            rebal = compute_rebalance_pnl(
                profile=profile, universe=universe, mode=mode_use,
                portfolio_value=review_pv, positions=positions_agg,
            )
        except Exception:
            rebal = {"rows": [], "total_target": 0, "total_current": 0,
                     "total_pnl": 0, "total_pnl_pct": 0, "net_rebalance": 0}
        review_payload = {
            "pnl": pnl,
            "drift": drift,
            "rebalance": rebal,
            "live_value": live_value,
        }

    # 10. Phased-build / DCA section (optional).
    dca_rows: list[dict] = []
    dca_meta: dict = {}
    if inp.dca and (inp.dca.get("monthly_amount") or 0) > 0:
        try:
            dca_rows = compute_dca(
                profile=profile,
                universe=universe,
                mode=mode_use,
                monthly_amount=float(inp.dca.get("monthly_amount") or 0),
                dca_scope=str(inp.dca.get("scope") or "all"),
                horizon_months=int(inp.dca.get("horizon_months") or 6),
                min_order=float(inp.dca.get("min_order") or 0),
            )
            # Drop excluded tickers from the DCA plan too — keep it
            # consistent with the displayed allocation.
            if excluded_tickers:
                dca_rows = [r for r in dca_rows if r["ticker"].upper() not in excluded_tickers]
            dca_meta = {
                "monthly_amount": float(inp.dca.get("monthly_amount") or 0),
                "horizon_months": int(inp.dca.get("horizon_months") or 6),
                "scope": str(inp.dca.get("scope") or "all"),
                "min_order": float(inp.dca.get("min_order") or 0),
            }
        except Exception:
            dca_rows = []

    # Brand SVGs embedded inline so the renderer needs no URL resolution.
    static_img = Path(__file__).resolve().parents[1] / "static" / "img"
    try:
        teroxx_mark = (static_img / "teroxx-mark.svg").read_text(encoding="utf-8")
    except OSError:
        teroxx_mark = ""
    try:
        teroxx_logo_svg = (static_img / "logo.svg").read_text(encoding="utf-8")
    except OSError:
        teroxx_logo_svg = ""

    return {
        "client": client,
        "lang": lang,
        "universe": universe,
        "portfolio_value": portfolio_value,
        "prepared_by": inp.prepared_by,
        "prepared_date": inp.prepared_date,
        "cover_subtitle": cover_sub,
        "exec_title": exec_title,
        "exec_bullets": exec_bullets,
        "allocation_count": len(alloc_rows),
        "defensive_pct": defensive_pct,
        "is_basket": is_basket,
        "basket_theme": theme_label,
        "weighting_label": weighting_label,
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
        "teroxx_logo_svg": teroxx_logo_svg,
        # Overrides: cleaned-up versions ready for the renderer.
        # All free-form *_md blocks are markdown strings; empty when
        # the advisor has not yet drafted that section.
        "overrides": {
            "excluded_tickers": sorted(excluded_tickers),
            # Personal welcome (Jannick template: 4-paragraph welcome
            # block opening with "Sehr geehrter Herr X,").
            "salutation": (overrides.get("salutation") or "").strip(),
            "welcome_md": (overrides.get("welcome_md") or "").strip(),
            # Advisor-narrative slots arranged in Jannick's flow.
            "summary_md": (overrides.get("summary_md") or "").strip(),
            "market_analysis_md": (overrides.get("market_analysis_md") or "").strip(),
            "execution_plan_md": (overrides.get("execution_plan_md") or "").strip(),
            "conclusion_md": (overrides.get("conclusion_md") or "").strip(),
            # Wishes is the "what the client asked for" block.
            "wishes_md": (overrides.get("wishes_md") or "").strip(),
            # Client-info metadata.
            "status_level": (overrides.get("status_level") or "").strip(),
            "consultation_date": (overrides.get("consultation_date") or "").strip(),
            # Structured fee components: [{name, value}]. Stored as a
            # list so the advisor can add/remove rows. Defaults are
            # injected by the renderer if the list is empty.
            "fees": overrides.get("fees") or [],
            # Advisor contact card.
            "advisor_email": (overrides.get("advisor_email") or "").strip(),
            "advisor_phone": (overrides.get("advisor_phone") or "").strip(),
        },
        # Asset-class aggregation for the directional summary table
        # (Jannick's template table 4). Each entry: {key, label, share_pct}.
        "asset_class_rows": (
            _aggregate_basket_categories(alloc_rows) if is_basket
            else _aggregate_asset_classes(alloc_rows, lang=lang)
        ),
        # DCA section payload (empty when no DCA params supplied).
        "dca_rows": dca_rows,
        "dca_meta": dca_meta,
        # Proposal flavour + the review payload. Empty dict when
        # proposal_type=new so the renderer can branch on truthiness.
        "proposal_type": proposal_type,
        "review": review_payload,
        # i18n helpers for the template.
        "t": lambda key, **fmt: t(key, lang, **fmt),
        "tier_label_i18n": lambda label: _i18n_tier_label(label, lang),
        "profile_label_i18n": lambda label: profile_label(label, lang),
        "regime_label_i18n": lambda label: _i18n_regime_label(label, lang),
    }
