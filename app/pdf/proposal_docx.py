"""Editable DOCX rendering of the Teroxx allocation proposal.

DOCX is the primary working format for the Investment Advisory team:
the auto-rendered file is a starting point that advisors layer with
client-specific wishes, summaries, execution analysis and comments
before sending. Per Jannick Bröring (2026-05-14): "with a PDF we can
not work, the outcome should be a docx".

The renderer takes the same ``ctx`` dict that ``proposal.render_pdf``
consumes (built by :func:`build_proposal_context`). Exhibits authored
as SVG (donut, regime gauge, tier bar) are rasterised to PNG via
cairosvg and embedded as inline images so the advisor opens a Word
document that already looks done.

Brand fonts (Söhne, Sometimes Times) are declared in the document
defaults. Word will pick them up if the advisor has the fonts
installed locally; otherwise it falls back to Calibri / Cambria
gracefully — the document remains editable either way.
"""
from __future__ import annotations

import io
import re
from typing import Any, Iterable, Optional

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Inches, Pt, RGBColor

from app.pdf.i18n import (
    DEFAULT as I18N_DEFAULT,
    t,
    profile_label,
    tier_label,
    regime_label,
)


# Brand palette as RGB triples.
NIGHTBLUE = RGBColor(0x01, 0x06, 0x26)
DEEP_INDIGO = RGBColor(0x06, 0x0D, 0x43)
ELECTRIC_SKY = RGBColor(0x0B, 0x68, 0x8C)
SANDSTONE = RGBColor(0xBF, 0xB3, 0xA8)
SUNSET_EMBER = RGBColor(0xD0, 0x66, 0x43)
TEXT_BODY = RGBColor(0x1A, 0x1A, 0x1A)
TEXT_MUTED = RGBColor(0x66, 0x66, 0x66)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


# ── Helpers ─────────────────────────────────────────────────────────


def _svg_to_png(svg: str, width_px: int = 720) -> Optional[bytes]:
    """Rasterise SVG to PNG bytes via cairosvg. Return None on failure
    so the renderer can drop the image silently rather than crash."""
    if not svg:
        return None
    try:
        import cairosvg  # type: ignore
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width_px)
    except Exception:
        return None


def _set_default_font(doc: Document) -> None:
    """Configure document defaults so Word picks brand fonts when
    available and Calibri / Cambria when not."""
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Sohne"
    font.size = Pt(10.5)
    font.color.rgb = TEXT_BODY
    # Set East-Asian + complex script font names so Word respects the
    # latin face for all runs even in mixed-script paragraphs.
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Sohne")
    rfonts.set(qn("w:hAnsi"), "Sohne")
    rfonts.set(qn("w:cs"), "Sohne")

    # Headings use the serif display face. Word falls back to Cambria
    # when SometimesTimes is unavailable.
    for level in range(1, 4):
        hs = doc.styles[f"Heading {level}"]
        hs.font.name = "SometimesTimes"
        hs.font.color.rgb = NIGHTBLUE
        hs.font.size = Pt({1: 22, 2: 16, 3: 12}[level])
        hs.font.bold = level <= 2


def _page_setup(doc: Document) -> None:
    """A4 with comfortable advisory-document margins."""
    for section in doc.sections:
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.left_margin = Cm(2.0)
        section.right_margin = Cm(2.0)
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.0)


def _shade_cell(cell, hex_color: str) -> None:
    """Apply a background fill to a table cell via raw OOXML.

    python-docx exposes no first-class cell-shading API, so we attach
    a ``<w:shd>`` element to the cell's tcPr. Hex without leading '#'.
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _set_cell_text(cell, text: str, *, bold: bool = False, color: Optional[RGBColor] = None,
                   align: int = WD_ALIGN_PARAGRAPH.LEFT, size_pt: float = 10.0) -> None:
    cell.text = ""  # clear default empty paragraph contents
    p = cell.paragraphs[0]
    p.alignment = align
    run = p.add_run(str(text))
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _add_horizontal_rule(doc: Document, color: RGBColor = NIGHTBLUE) -> None:
    """Insert a thin horizontal rule paragraph."""
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), f"{color}")  # RGBColor str = 'RRGGBB'
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_md_block(doc: Document, md: str) -> None:
    """Render a small subset of markdown into Word paragraphs.

    Supports bullet lists, numbered lists, paragraphs separated by
    blank lines, and inline **bold** / *italic*. Not a full markdown
    renderer — keeps the artifact editable in Word with simple
    structure. Anything fancier should be drafted directly in Word
    after generation.
    """
    if not md:
        return
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in md.replace("\r\n", "\n").split("\n"):
        if raw.strip() == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(raw)
    if current:
        blocks.append(current)

    bullet_re = re.compile(r"^\s*[-*]\s+(.*)$")
    numbered_re = re.compile(r"^\s*\d+\.\s+(.*)$")

    for block in blocks:
        if all(bullet_re.match(line) for line in block):
            for line in block:
                doc.add_paragraph(bullet_re.match(line).group(1), style="List Bullet")
            continue
        if all(numbered_re.match(line) for line in block):
            for line in block:
                doc.add_paragraph(numbered_re.match(line).group(1), style="List Number")
            continue
        text = " ".join(line.strip() for line in block)
        p = doc.add_paragraph()
        _add_inline_formatted_runs(p, text)


_INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")


def _add_inline_formatted_runs(paragraph, text: str) -> None:
    for chunk in _INLINE_RE.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**"):
            r = paragraph.add_run(chunk[2:-2])
            r.font.bold = True
        elif chunk.startswith("*") and chunk.endswith("*"):
            r = paragraph.add_run(chunk[1:-1])
            r.font.italic = True
        else:
            paragraph.add_run(chunk)


def _T(ctx: dict, key: str, **fmt) -> str:
    """Shorthand: pull the bound translator off the ctx dict."""
    lang = ctx.get("lang") or I18N_DEFAULT
    return t(key, lang, **fmt)


# ── Section builders ────────────────────────────────────────────────


def _cover(doc: Document, ctx: dict) -> None:
    client = ctx["client"]
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(_T(ctx, "cover.brand"))
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = ELECTRIC_SKY

    p = doc.add_paragraph()
    run = p.add_run(_T(ctx, "cover.brand_sub"))
    run.font.size = Pt(9.5)
    run.font.color.rgb = TEXT_MUTED

    # Add some vertical room before the title.
    for _ in range(4):
        doc.add_paragraph()

    title_p = doc.add_paragraph()
    title_run = title_p.add_run(_T(ctx, "cover.title"))
    title_run.font.size = Pt(34)
    title_run.font.bold = True
    title_run.font.color.rgb = NIGHTBLUE
    title_run.font.name = "SometimesTimes"

    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run(ctx.get("cover_subtitle", ""))
    sub_run.font.size = Pt(12)
    sub_run.font.color.rgb = TEXT_BODY
    sub_run.font.italic = True

    for _ in range(2):
        doc.add_paragraph()

    # Client meta block as a 2x4 table for tidy alignment.
    rows = [
        (_T(ctx, "cover.lbl_client"), client.get("name", "")),
        (
            _T(ctx, "cover.lbl_profile"),
            (profile_label(ctx.get("client", {}).get("profile", ""), ctx.get("lang", I18N_DEFAULT))
             + (f" · {client.get('domicile')}" if client.get("domicile") else "")),
        ),
        (_T(ctx, "cover.lbl_prepared_by"), ctx.get("prepared_by", "")),
        (_T(ctx, "cover.lbl_date"), ctx.get("prepared_date", "")),
    ]
    table = doc.add_table(rows=len(rows), cols=2)
    table.autofit = False
    table.columns[0].width = Cm(4.5)
    table.columns[1].width = Cm(12)
    for i, (lbl, val) in enumerate(rows):
        _set_cell_text(table.rows[i].cells[0], lbl, bold=True, color=TEXT_MUTED, size_pt=8.5)
        _set_cell_text(table.rows[i].cells[1], val, size_pt=11)

    for _ in range(2):
        doc.add_paragraph()

    foot = doc.add_paragraph()
    foot_run = foot.add_run(_T(ctx, "cover.confidential"))
    foot_run.font.size = Pt(8.5)
    foot_run.font.color.rgb = TEXT_MUTED
    foot_run.font.italic = True

    doc.add_page_break()


def _section_header(doc: Document, ctx: dict, page_tag_key: str, action_title: str) -> None:
    """Per-section title block: small kicker line + one-sentence action title + rule."""
    kicker = doc.add_paragraph()
    krun = kicker.add_run(_T(ctx, page_tag_key).upper())
    krun.font.size = Pt(8.5)
    krun.font.bold = True
    krun.font.color.rgb = SUNSET_EMBER

    h = doc.add_paragraph()
    h.paragraph_format.space_before = Pt(2)
    hrun = h.add_run(action_title)
    hrun.font.size = Pt(18)
    hrun.font.bold = True
    hrun.font.color.rgb = NIGHTBLUE
    hrun.font.name = "SometimesTimes"

    _add_horizontal_rule(doc, NIGHTBLUE)


def _exec_summary(doc: Document, ctx: dict) -> None:
    _section_header(doc, ctx, "page.exec_summary", ctx.get("exec_title", ""))

    # KPI strip
    kpi_table = doc.add_table(rows=2, cols=3)
    kpi_table.autofit = True
    headers = [
        _T(ctx, "kpi.portfolio_value"),
        _T(ctx, "kpi.defensive_sleeve"),
        _T(ctx, "kpi.risk_profile"),
    ]
    values = [
        f"${ctx.get('portfolio_value', 0):,.0f}",
        f"{ctx.get('defensive_pct', 0):.0f}%",
        profile_label(ctx.get("client", {}).get("profile", ""), ctx.get("lang", I18N_DEFAULT)),
    ]
    subs = [
        _T(ctx, "kpi.reporting_ccy", ccy=ctx.get("client", {}).get("currency", "USD")),
        "USDC · EURC · PAXG",
        _T(ctx, "kpi.positions", n=ctx.get("allocation_count", 0)),
    ]
    for i, (hd, vl, sub) in enumerate(zip(headers, values, subs)):
        _set_cell_text(kpi_table.rows[0].cells[i], hd, bold=True, color=TEXT_MUTED, size_pt=8.5)
        c = kpi_table.rows[1].cells[i]
        c.text = ""
        p1 = c.paragraphs[0]
        r1 = p1.add_run(vl)
        r1.font.size = Pt(20)
        r1.font.bold = True
        r1.font.color.rgb = NIGHTBLUE
        p2 = c.add_paragraph()
        r2 = p2.add_run(sub)
        r2.font.size = Pt(8.5)
        r2.font.color.rgb = TEXT_MUTED
        _shade_cell(c, "F6F4F0")
        _shade_cell(kpi_table.rows[0].cells[i], "F6F4F0")

    doc.add_paragraph()

    # "What this means" bullets
    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "exhibit.what_this_means"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE

    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "exhibit.what_this_means_sub"))
    sr.font.size = Pt(9)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    for b in ctx.get("exec_bullets", []):
        doc.add_paragraph(b, style="List Bullet")

    # Embed the donut exhibit if rasterisation succeeds.
    png = _svg_to_png(ctx.get("donut_svg") or "", width_px=600)
    if png:
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(io.BytesIO(png), width=Cm(10))
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cr = cap.add_run(_T(ctx, "exhibit.recommended_alloc_sub"))
        cr.font.size = Pt(8.5)
        cr.font.italic = True
        cr.font.color.rgb = TEXT_MUTED

    doc.add_page_break()


def _allocation_table(doc: Document, ctx: dict) -> None:
    _section_header(doc, ctx, "page.allocation", ctx.get("allocation_title", ""))

    rows = ctx.get("allocation_rows", [])
    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "exhibit.per_asset_weights"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE

    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "exhibit.per_asset_weights_sub"))
    sr.font.size = Pt(9)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    table = doc.add_table(rows=1 + len(rows), cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    headers = [
        _T(ctx, "table.asset"),
        _T(ctx, "table.tier"),
        _T(ctx, "table.weight_pct"),
        _T(ctx, "table.alloc_usd"),
        _T(ctx, "table.role"),
    ]
    for i, hd in enumerate(headers):
        _set_cell_text(table.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(table.rows[0].cells[i], "010626")

    lang = ctx.get("lang", I18N_DEFAULT)
    for i, row in enumerate(rows, start=1):
        cells = table.rows[i].cells
        # Asset cell: ticker bold + name
        c = cells[0]
        c.text = ""
        p = c.paragraphs[0]
        r1 = p.add_run(row.get("ticker", ""))
        r1.font.bold = True
        r1.font.size = Pt(10)
        r2 = p.add_run(f"  {row.get('name', '')}")
        r2.font.size = Pt(9)
        r2.font.color.rgb = TEXT_MUTED
        _set_cell_text(cells[1], tier_label(row.get("tier", ""), lang), size_pt=9.5)
        _set_cell_text(cells[2], f"{row.get('target_pct', 0):.2f}%", align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[3], f"${row.get('target_usd', 0):,.0f}", align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[4], row.get("rationale_tag", ""), size_pt=9.5, color=TEXT_MUTED)
        # Zebra stripe
        if i % 2 == 0:
            for cell in cells:
                _shade_cell(cell, "F6F4F0")

    # Disclosed-omission note when overrides excluded any tickers.
    excluded = (ctx.get("overrides") or {}).get("excluded_tickers") or []
    if excluded:
        note = doc.add_paragraph()
        nr = note.add_run(_T(ctx, "overrides.omitted_note", tickers=", ".join(excluded)))
        nr.font.size = Pt(8.5)
        nr.font.italic = True
        nr.font.color.rgb = TEXT_MUTED

    # Tier-bar exhibit underneath.
    png = _svg_to_png(ctx.get("tier_bar_svg") or "", width_px=720)
    if png:
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(io.BytesIO(png), width=Cm(15))
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cr = cap.add_run(_T(ctx, "exhibit.alloc_by_tier"))
        cr.font.size = Pt(8.5)
        cr.font.italic = True
        cr.font.color.rgb = TEXT_MUTED

    doc.add_page_break()


def _overrides_sections(doc: Document, ctx: dict) -> None:
    ov = ctx.get("overrides") or {}
    blocks = [
        ("page.wishes", "overrides.wishes_sub", ov.get("wishes_md")),
        ("page.summary", "overrides.summary_sub", ov.get("summary_md")),
        ("page.execution_plan", "overrides.execution_sub", ov.get("execution_plan_md")),
    ]
    rendered = False
    for tag_key, sub_key, body in blocks:
        if not (body and body.strip()):
            continue
        rendered = True
        _section_header(doc, ctx, tag_key, _T(ctx, tag_key))
        sub = doc.add_paragraph()
        sr = sub.add_run(_T(ctx, sub_key))
        sr.font.size = Pt(9.5)
        sr.font.italic = True
        sr.font.color.rgb = TEXT_MUTED
        _add_md_block(doc, body)
        doc.add_page_break()


def _dca_section(doc: Document, ctx: dict) -> None:
    rows = ctx.get("dca_rows") or []
    if not rows:
        return
    meta = ctx.get("dca_meta") or {}
    _section_header(doc, ctx, "page.phased_build", _T(ctx, "exhibit.phased_build"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "exhibit.phased_build_sub",
                       horizon_months=meta.get("horizon_months", 0)))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    table = doc.add_table(rows=1 + len(rows), cols=4)
    headers = [
        _T(ctx, "table.asset"),
        _T(ctx, "table.weight_pct"),
        _T(ctx, "table.monthly_buy"),
        _T(ctx, "table.horizon_total"),
    ]
    for i, hd in enumerate(headers):
        _set_cell_text(table.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(table.rows[0].cells[i], "010626")

    for i, r in enumerate(rows, start=1):
        cells = table.rows[i].cells
        c = cells[0]
        c.text = ""
        p = c.paragraphs[0]
        rt = p.add_run(r.get("ticker", ""))
        rt.font.bold = True
        rt.font.size = Pt(10)
        rn = p.add_run(f"  {r.get('name', '')}")
        rn.font.size = Pt(9)
        rn.font.color.rgb = TEXT_MUTED
        _set_cell_text(cells[1], f"{(r.get('portfolio_pct', 0) * 100):.2f}%",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[2], f"${r.get('monthly_buy', 0):,.0f}",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[3], f"${r.get('horizon_total', 0):,.0f}",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        if i % 2 == 0:
            for cell in cells:
                _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


def _macro_section(doc: Document, ctx: dict) -> None:
    _section_header(doc, ctx, "page.macro", ctx.get("macro_title", ""))

    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "exhibit.regime_read"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE

    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "exhibit.regime_read_sub"))
    sr.font.size = Pt(9)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    png = _svg_to_png(ctx.get("regime_gauge_svg") or "", width_px=480)
    if png:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(io.BytesIO(png), width=Cm(8.5))

    body_p = doc.add_paragraph()
    body_p.add_run(ctx.get("macro_paragraph_text", ""))

    inds = ctx.get("top_indicators") or []
    if inds:
        doc.add_paragraph()
        table = doc.add_table(rows=1 + len(inds), cols=3)
        headers = [
            _T(ctx, "table.indicator"),
            _T(ctx, "table.category"),
            _T(ctx, "table.score"),
        ]
        for i, hd in enumerate(headers):
            _set_cell_text(table.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
            _shade_cell(table.rows[0].cells[i], "010626")
        for i, ind in enumerate(inds, start=1):
            cells = table.rows[i].cells
            _set_cell_text(cells[0], ind.get("label", ""), size_pt=9.5)
            _set_cell_text(cells[1], ind.get("category", ""), size_pt=9.5)
            score = ind.get("score")
            _set_cell_text(cells[2],
                           "—" if score is None else f"{score:.0f}",
                           align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
            if i % 2 == 0:
                for cell in cells:
                    _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


def _implementation_section(doc: Document, ctx: dict) -> None:
    lang = ctx.get("lang", I18N_DEFAULT)
    profile = ctx.get("client", {}).get("profile", "")
    heading = t("implementation.heading_tpl", lang,
                profile=profile_label(profile, lang))
    _section_header(doc, ctx, "page.implementation", heading)

    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "exhibit.execution_path"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE

    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "exhibit.execution_path_sub"))
    sr.font.size = Pt(9)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    body = doc.add_paragraph()
    body.add_run(ctx.get("implementation_text", ""))

    doc.add_paragraph()

    h2 = doc.add_paragraph()
    hr2 = h2.add_run(_T(ctx, "exhibit.review_cadence"))
    hr2.font.bold = True
    hr2.font.size = Pt(12)
    hr2.font.color.rgb = NIGHTBLUE
    for key in ("review.drift_window", "review.single_drift", "review.rescore_cadence"):
        doc.add_paragraph(_T(ctx, key), style="List Bullet")

    doc.add_page_break()


def _appendix(doc: Document, ctx: dict) -> None:
    lang = ctx.get("lang", I18N_DEFAULT)
    title_en = "Methodology, data sources and important information"
    title_de = "Methodik, Datenquellen und wichtige Hinweise"
    _section_header(doc, ctx, "page.appendix", title_de if lang == "de" else title_en)

    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "exhibit.methodology"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE
    doc.add_paragraph(_T(ctx, "methodology.body"))

    h2 = doc.add_paragraph()
    hr2 = h2.add_run(_T(ctx, "exhibit.data_sources"))
    hr2.font.bold = True
    hr2.font.size = Pt(12)
    hr2.font.color.rgb = NIGHTBLUE
    for key in ("datasources.spot", "datasources.macro", "datasources.onchain", "datasources.history"):
        doc.add_paragraph(_T(ctx, key), style="List Bullet")

    doc.add_paragraph()
    disclaimer = ctx.get("disclaimer") or {}
    h3 = doc.add_paragraph()
    hr3 = h3.add_run(disclaimer.get("title") or "")
    hr3.font.bold = True
    hr3.font.size = Pt(11)
    hr3.font.color.rgb = NIGHTBLUE
    for key in ("body", "tax", "estate"):
        body = disclaimer.get(key)
        if body:
            p = doc.add_paragraph()
            r = p.add_run(body)
            r.font.size = Pt(9.5)

    doc.add_paragraph()
    sign = doc.add_paragraph()
    sr = sign.add_run(_T(ctx, "signoff.prepared_by"))
    sr.font.bold = True
    sr.font.size = Pt(10)
    foot = doc.add_paragraph()
    fr = foot.add_run(f"{ctx.get('prepared_by', '')} · {ctx.get('prepared_date', '')}")
    fr.font.size = Pt(9.5)
    fr.font.color.rgb = TEXT_MUTED


# ── Public entry point ──────────────────────────────────────────────


def render_docx(ctx: dict[str, Any]) -> bytes:
    """Build the proposal as a Word document from a proposal context dict.

    The returned bytes are a complete .docx archive suitable for the
    response body of a FastAPI handler.
    """
    doc = Document()
    _set_default_font(doc)
    _page_setup(doc)

    _cover(doc, ctx)
    _exec_summary(doc, ctx)
    _allocation_table(doc, ctx)
    _overrides_sections(doc, ctx)
    _dca_section(doc, ctx)
    _macro_section(doc, ctx)
    _implementation_section(doc, ctx)
    _appendix(doc, ctx)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


__all__ = ["render_docx"]
