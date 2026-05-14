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


def _money(ctx: dict, amount: float) -> str:
    """Currency-aware formatter. Reads client.currency and lang from ctx.

    USD → "$50,000"
    EUR + lang=de → "50.000 €" (German thousand-separator convention)
    EUR + lang=en → "€50,000"
    Other → "{X,XXX} {ccy}"
    """
    if amount is None:
        return "-"
    ccy = (ctx.get("client", {}).get("currency") or "USD").upper()
    lang = ctx.get("lang") or I18N_DEFAULT
    val = float(amount)
    if ccy == "USD":
        return f"${val:,.0f}"
    if ccy == "EUR":
        if lang == "de":
            s = f"{val:,.0f}".replace(",", ".")
            return f"{s} €"
        return f"€{val:,.0f}"
    return f"{val:,.0f} {ccy}"


def _country_label(client: dict, lang: str) -> str:
    """Best-effort country display string.

    Prefer the long ``domicile`` ("Berlin, DE") but fall back to the
    ISO ``domicile_country`` if the long form is missing.
    """
    return (client.get("domicile") or client.get("domicile_country") or "").strip()


def _md_or_placeholder(doc: Document, ctx: dict, md_value: str, placeholder_key: str) -> None:
    """Drop ``md_value`` as a paragraph block, or a muted placeholder
    instructing the advisor to fill the section in. The placeholder is
    italicised so it's visually obvious it needs editing before sending."""
    if md_value:
        _add_md_block(doc, md_value)
        return
    p = doc.add_paragraph()
    r = p.add_run(_T(ctx, placeholder_key).strip("_ ").strip())
    r.font.italic = True
    r.font.color.rgb = TEXT_MUTED
    r.font.size = Pt(10)


# ── Section builders ────────────────────────────────────────────────


def _cover(doc: Document, ctx: dict) -> None:
    """Minimal cover: brand mark, headline, confidentiality strip.

    Detailed client/advisor metadata moved into a dedicated Client
    Information section directly after the welcome paragraphs (matches
    Jannick's template flow)."""
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

    for _ in range(5):
        doc.add_paragraph()

    title_p = doc.add_paragraph()
    title_run = title_p.add_run(_T(ctx, "cover.title"))
    title_run.font.size = Pt(36)
    title_run.font.bold = True
    title_run.font.color.rgb = NIGHTBLUE
    title_run.font.name = "SometimesTimes"

    sub_p = doc.add_paragraph()
    sub_run = sub_p.add_run(ctx.get("cover_subtitle", ""))
    sub_run.font.size = Pt(12)
    sub_run.font.color.rgb = TEXT_BODY
    sub_run.font.italic = True

    for _ in range(8):
        doc.add_paragraph()

    foot = doc.add_paragraph()
    foot.alignment = WD_ALIGN_PARAGRAPH.LEFT
    foot_run = foot.add_run(_T(ctx, "cover.confidential"))
    foot_run.font.size = Pt(8.5)
    foot_run.font.color.rgb = TEXT_MUTED
    foot_run.font.italic = True

    doc.add_page_break()


def _welcome(doc: Document, ctx: dict) -> None:
    """Personal salutation + welcome paragraphs.

    Directional from Jannick's template: every IA proposal opens with
    "Sehr geehrter Herr {Lastname}," and a four-paragraph welcome.
    Advisor can fully override via the salutation / welcome_md fields
    on the client record; defaults are provided so the auto-generated
    DOCX still looks finished out of the box.
    """
    lang = ctx.get("lang", I18N_DEFAULT)
    ov = ctx.get("overrides") or {}
    client = ctx.get("client", {})

    # Salutation: explicit override > default with client name.
    salutation = ov.get("salutation") or _T(
        ctx, "welcome.salutation_default",
        name=client.get("name", "")
    )
    p = doc.add_paragraph()
    pr = p.add_run(salutation)
    pr.font.size = Pt(11)

    welcome_body = ov.get("welcome_md") or _T(ctx, "welcome.body_default")
    _add_md_block(doc, welcome_body)
    doc.add_page_break()


def _client_info(doc: Document, ctx: dict) -> None:
    """Two stacked tables: client information + risk profile.

    Mirrors Jannick's tables 1 + 2. Status level and consultation
    date come from per-client overrides; risk-tolerance defaults are
    derived from the configured profile when no override is set.
    """
    lang = ctx.get("lang", I18N_DEFAULT)
    client = ctx.get("client", {})
    ov = ctx.get("overrides") or {}

    _section_header(doc, ctx, "client_info.heading", _T(ctx, "client_info.heading"))

    # ── Client information table ──
    rows = [
        (_T(ctx, "client_info.prepared_by"), _T(ctx, "client_info.prepared_by_team")),
        (
            _T(ctx, "client_info.consultation_date"),
            ov.get("consultation_date") or ctx.get("prepared_date", ""),
        ),
        (_T(ctx, "client_info.client_name"), client.get("name", "")),
        (_T(ctx, "client_info.country"), _country_label(client, lang)),
    ]
    if ov.get("status_level"):
        rows.append((_T(ctx, "client_info.status_level"), ov["status_level"]))

    table = doc.add_table(rows=len(rows), cols=2)
    table.autofit = False
    table.columns[0].width = Cm(6.0)
    table.columns[1].width = Cm(10.5)
    for i, (lbl, val) in enumerate(rows):
        _set_cell_text(table.rows[i].cells[0], lbl, bold=True, color=TEXT_MUTED, size_pt=9)
        _set_cell_text(table.rows[i].cells[1], val, size_pt=10.5)
        if i % 2 == 0:
            _shade_cell(table.rows[i].cells[0], "F6F4F0")
            _shade_cell(table.rows[i].cells[1], "F6F4F0")

    doc.add_paragraph()

    # ── Risk profile mini-table ──
    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "risk_profile.heading"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE

    tolerance = t(
        f"risk_profile.tolerance_default.{client.get('profile', '')}",
        lang,
    ) or profile_label(client.get("profile", ""), lang)
    risk_rows = [
        (_T(ctx, "risk_profile.tolerance"), tolerance),
        (_T(ctx, "risk_profile.horizon"), _T(ctx, "risk_profile.horizon_default")),
        (_T(ctx, "risk_profile.objective"), _T(ctx, "risk_profile.objective_default")),
    ]
    rtable = doc.add_table(rows=len(risk_rows), cols=2)
    rtable.autofit = False
    rtable.columns[0].width = Cm(6.0)
    rtable.columns[1].width = Cm(10.5)
    for i, (lbl, val) in enumerate(risk_rows):
        _set_cell_text(rtable.rows[i].cells[0], lbl, bold=True, color=TEXT_MUTED, size_pt=9)
        _set_cell_text(rtable.rows[i].cells[1], val, size_pt=10.5)
        if i % 2 == 0:
            _shade_cell(rtable.rows[i].cells[0], "F6F4F0")
            _shade_cell(rtable.rows[i].cells[1], "F6F4F0")

    doc.add_page_break()


def _consultation_summary(doc: Document, ctx: dict) -> None:
    """Advisor's account of the meeting + agreed positioning.

    Maps to Jannick's "Zusammenfassung der Beratung / des Gesprächs"
    heading. Sourced from overrides.summary_md; left out entirely when
    the advisor has not yet drafted the section (no placeholder, since
    inventing a summary would be misleading).
    """
    ov = ctx.get("overrides") or {}
    body = ov.get("summary_md")
    if not (body and body.strip()):
        return
    _section_header(doc, ctx, "page.consultation", _T(ctx, "page.consultation"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "overrides.summary_sub"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED
    _add_md_block(doc, body)
    doc.add_page_break()


def _market_analysis(doc: Document, ctx: dict) -> None:
    """Long-form market commentary slot — the section Jannick invests
    the most time in. Renders the advisor's market_analysis_md, or a
    visible italic placeholder if empty (advisor knows what to fill).
    """
    _section_header(doc, ctx, "page.market_analysis", _T(ctx, "page.market_analysis"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "market_analysis.subheading"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED
    ov = ctx.get("overrides") or {}
    _md_or_placeholder(doc, ctx, ov.get("market_analysis_md", ""), "market_analysis.placeholder")
    doc.add_page_break()


def _portfolio_detail(doc: Document, ctx: dict) -> None:
    """Combined portfolio section: parameters → asset-class summary →
    per-ticker target weights → tier-bar exhibit → donut exhibit.

    Folds the prior _exec_summary KPI strip into the parameters table
    here so the proposal reads as a single coherent "your portfolio"
    block rather than two thinly-separated pages."""
    _section_header(doc, ctx, "page.portfolio_detail", ctx.get("allocation_title", _T(ctx, "page.your_new_portfolio")))

    client = ctx.get("client", {})
    lang = ctx.get("lang", I18N_DEFAULT)

    # ── Parameters block (Jannick table 3) ──
    params = [
        (_T(ctx, "kpi.risk_profile"), profile_label(client.get("profile", ""), lang)),
        (_T(ctx, "table.asset"), ctx.get("universe", "")),
        (_T(ctx, "kpi.portfolio_value"), _money(ctx, ctx.get("portfolio_value", 0))),
        (_T(ctx, "kpi.defensive_sleeve"), f"{ctx.get('defensive_pct', 0):.0f}%"),
        (_T(ctx, "kpi.positions"), str(ctx.get("allocation_count", 0))),
    ]
    h = doc.add_paragraph()
    hr = h.add_run(_T(ctx, "exhibit.what_this_means"))
    hr.font.bold = True
    hr.font.size = Pt(12)
    hr.font.color.rgb = NIGHTBLUE
    ptable = doc.add_table(rows=len(params), cols=2)
    ptable.autofit = False
    ptable.columns[0].width = Cm(6.0)
    ptable.columns[1].width = Cm(10.5)
    for i, (lbl, val) in enumerate(params):
        _set_cell_text(ptable.rows[i].cells[0], lbl, bold=True, color=TEXT_MUTED, size_pt=9)
        _set_cell_text(ptable.rows[i].cells[1], val, size_pt=10.5)
        if i % 2 == 0:
            _shade_cell(ptable.rows[i].cells[0], "F6F4F0")
            _shade_cell(ptable.rows[i].cells[1], "F6F4F0")

    doc.add_paragraph()

    # ── "What this means" bullets ──
    bullets = ctx.get("exec_bullets") or []
    if bullets:
        for b in bullets:
            doc.add_paragraph(b, style="List Bullet")
        doc.add_paragraph()

    # ── Asset-class aggregation table (directional from Jannick) ──
    ac_rows = ctx.get("asset_class_rows") or []
    nonzero = [r for r in ac_rows if (r.get("share_pct") or 0) > 0]
    if nonzero:
        h2 = doc.add_paragraph()
        hr2 = h2.add_run(_T(ctx, "assetclass.heading"))
        hr2.font.bold = True
        hr2.font.size = Pt(12)
        hr2.font.color.rgb = NIGHTBLUE
        sub2 = doc.add_paragraph()
        sr2 = sub2.add_run(_T(ctx, "assetclass.subheading"))
        sr2.font.size = Pt(9)
        sr2.font.italic = True
        sr2.font.color.rgb = TEXT_MUTED
        ac_table = doc.add_table(rows=1 + len(nonzero) + 1, cols=2)
        headers = [_T(ctx, "assetclass.col_class"), _T(ctx, "assetclass.col_share")]
        for i, hd in enumerate(headers):
            _set_cell_text(ac_table.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
            _shade_cell(ac_table.rows[0].cells[i], "010626")
        total = 0.0
        for i, row in enumerate(nonzero, start=1):
            cells = ac_table.rows[i].cells
            _set_cell_text(cells[0], row["label"], size_pt=10)
            _set_cell_text(cells[1], f"{row['share_pct']:.1f}%",
                           align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=10)
            total += float(row.get("share_pct") or 0)
            if i % 2 == 0:
                for cell in cells:
                    _shade_cell(cell, "F6F4F0")
        tcells = ac_table.rows[-1].cells
        _set_cell_text(tcells[0], _T(ctx, "assetclass.total"), bold=True, size_pt=10)
        _set_cell_text(tcells[1], f"{total:.1f}%", bold=True,
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=10)
        _shade_cell(tcells[0], "BFB3A8")
        _shade_cell(tcells[1], "BFB3A8")

        doc.add_paragraph()

    # ── Donut exhibit ──
    png = _svg_to_png(ctx.get("donut_svg") or "", width_px=600)
    if png:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(io.BytesIO(png), width=Cm(10))
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cr = cap.add_run(_T(ctx, "exhibit.recommended_alloc"))
        cr.font.size = Pt(8.5)
        cr.font.italic = True
        cr.font.color.rgb = TEXT_MUTED

    doc.add_page_break()


def _wishes_section(doc: Document, ctx: dict) -> None:
    """Optional client-wishes section. Rendered only when the advisor
    has explicitly drafted it; no placeholder so the auto-PDF stays
    quiet for clients without specific requests."""
    ov = ctx.get("overrides") or {}
    body = ov.get("wishes_md", "")
    if not (body and body.strip()):
        return
    _section_header(doc, ctx, "page.wishes", _T(ctx, "page.wishes"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "overrides.wishes_sub"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED
    _add_md_block(doc, body)
    doc.add_page_break()


def _strategy_section(doc: Document, ctx: dict) -> None:
    """Strategy / phased build. Falls back to PAM's default implementation
    paragraph when no execution plan is drafted, keeping the section
    informative for fresh clients."""
    ov = ctx.get("overrides") or {}
    plan_md = ov.get("execution_plan_md", "")
    rows = ctx.get("dca_rows") or []
    if not (plan_md or rows):
        # Use the auto-generated implementation paragraph + review cadence
        # to ensure the strategy page is never blank.
        _implementation_section(doc, ctx)
        return

    _section_header(doc, ctx, "page.strategy", _T(ctx, "exhibit.phased_build"))

    if plan_md:
        sub = doc.add_paragraph()
        sr = sub.add_run(_T(ctx, "overrides.execution_sub"))
        sr.font.size = Pt(9.5)
        sr.font.italic = True
        sr.font.color.rgb = TEXT_MUTED
        _add_md_block(doc, plan_md)
        doc.add_paragraph()

    if rows:
        meta = ctx.get("dca_meta") or {}
        h = doc.add_paragraph()
        hr = h.add_run(_T(ctx, "exhibit.phased_build"))
        hr.font.bold = True
        hr.font.size = Pt(12)
        hr.font.color.rgb = NIGHTBLUE
        sub2 = doc.add_paragraph()
        sr2 = sub2.add_run(_T(ctx, "exhibit.phased_build_sub",
                              horizon_months=meta.get("horizon_months", 0)))
        sr2.font.size = Pt(9.5)
        sr2.font.italic = True
        sr2.font.color.rgb = TEXT_MUTED

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
            _set_cell_text(cells[2], _money(ctx, r.get("monthly_buy", 0)),
                           align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
            _set_cell_text(cells[3], _money(ctx, r.get("horizon_total", 0)),
                           align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
            if i % 2 == 0:
                for cell in cells:
                    _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


def _fazit_section(doc: Document, ctx: dict) -> None:
    """Conclusion / Fazit. Optional; placeholder absent so empty
    proposals don't carry a stub heading."""
    ov = ctx.get("overrides") or {}
    body = ov.get("conclusion_md", "")
    if not (body and body.strip()):
        return
    _section_header(doc, ctx, "page.fazit", _T(ctx, "page.fazit"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "fazit.subheading"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED
    _add_md_block(doc, body)
    doc.add_page_break()


def _fees_section(doc: Document, ctx: dict) -> None:
    """Fee structure table (directional from Jannick template table 6).

    Renders only when the advisor supplied at least one fee row; the
    table headers/cells are translated, but the values come verbatim
    from the override so the advisor can phrase exemptions, %s, or
    explanatory notes however the engagement requires.
    """
    ov = ctx.get("overrides") or {}
    fees = ov.get("fees") or []
    if not isinstance(fees, list) or not fees:
        return
    cleaned = [
        f for f in fees
        if isinstance(f, dict) and (f.get("name") or f.get("value"))
    ]
    if not cleaned:
        return

    _section_header(doc, ctx, "page.fees", _T(ctx, "page.fees"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "fees.subheading"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    table = doc.add_table(rows=1 + len(cleaned), cols=2)
    headers = [_T(ctx, "fees.col_component"), _T(ctx, "fees.col_value")]
    for i, hd in enumerate(headers):
        _set_cell_text(table.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(table.rows[0].cells[i], "010626")
    for i, f in enumerate(cleaned, start=1):
        cells = table.rows[i].cells
        _set_cell_text(cells[0], f.get("name", ""), size_pt=10)
        _set_cell_text(cells[1], f.get("value", ""), size_pt=10)
        if i % 2 == 0:
            for cell in cells:
                _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


# ── Review-flow sections (existing-client proposals) ───────────────


def _current_holdings(doc: Document, ctx: dict) -> None:
    """Current portfolio: KPI strip (cost basis / market value / P&L /
    days held) + per-ticker holdings table with live mark-to-market."""
    review = ctx.get("review") or {}
    pnl = review.get("pnl") or {}
    rows = pnl.get("ticker_summary") or pnl.get("by_ticker") or []
    if not rows:
        # Fall back to lot-level rows if the ticker rollup is missing.
        rows = pnl.get("rows") or []
    summary = pnl.get("summary") or {}
    if not rows and not summary:
        # Nothing to render — likely client has no lots; the renderer
        # will switch the audience back to the new-client flow upstream
        # but we still guard here.
        return

    _section_header(
        doc, ctx, "page.current_portfolio",
        _T(ctx, "current_portfolio.title_with_total",
           value=_money(ctx, summary.get("total_value", 0))),
    )
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "current_portfolio.subheading"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    # KPI strip — uses the same shape as portfolio_detail's params block.
    kpis = [
        (_T(ctx, "kpi.total_value"), _money(ctx, summary.get("total_value", 0))),
        (_T(ctx, "kpi.total_cost"), _money(ctx, summary.get("total_cost", 0))),
        (_T(ctx, "kpi.total_pnl"),
         f"{_money(ctx, summary.get('total_pnl', 0))} ({summary.get('total_pnl_pct', 0):.1f}%)"),
        (_T(ctx, "kpi.days_held"), str(summary.get("days_since_entry", 0))),
    ]
    ktable = doc.add_table(rows=len(kpis), cols=2)
    ktable.autofit = False
    ktable.columns[0].width = Cm(7.0)
    ktable.columns[1].width = Cm(9.5)
    for i, (lbl, val) in enumerate(kpis):
        _set_cell_text(ktable.rows[i].cells[0], lbl, bold=True, color=TEXT_MUTED, size_pt=9)
        _set_cell_text(ktable.rows[i].cells[1], val, size_pt=10.5)
        if i % 2 == 0:
            _shade_cell(ktable.rows[i].cells[0], "F6F4F0")
            _shade_cell(ktable.rows[i].cells[1], "F6F4F0")

    doc.add_paragraph()

    # Per-ticker holdings table.
    headers = [
        _T(ctx, "table.asset"),
        _T(ctx, "table.qty"),
        _T(ctx, "table.entry_price"),
        _T(ctx, "table.live_price"),
        _T(ctx, "table.market_value"),
        _T(ctx, "table.pnl_unrealized"),
        _T(ctx, "table.weight_now"),
    ]
    htable = doc.add_table(rows=1 + len(rows), cols=len(headers))
    for i, hd in enumerate(headers):
        _set_cell_text(htable.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(htable.rows[0].cells[i], "010626")
    for i, r in enumerate(rows, start=1):
        cells = htable.rows[i].cells
        c = cells[0]
        c.text = ""
        p = c.paragraphs[0]
        rt = p.add_run(r.get("ticker", ""))
        rt.font.bold = True
        rt.font.size = Pt(10)
        rn = p.add_run(f"  {r.get('name', '')}")
        rn.font.size = Pt(9)
        rn.font.color.rgb = TEXT_MUTED
        _set_cell_text(cells[1], f"{r.get('quantity', 0):,.4f}".rstrip("0").rstrip("."),
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[2], _money(ctx, r.get("avg_entry_price", r.get("entry_price", 0))),
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[3], _money(ctx, r.get("current_price", 0)),
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[4], _money(ctx, r.get("current_value", 0)),
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        pnl_val = r.get("pnl", 0)
        pnl_text = f"{_money(ctx, pnl_val)} ({r.get('pnl_pct', 0):.1f}%)"
        # Colour the P&L cell green / red so the advisor can scan the
        # row at a glance even before reading the value.
        pnl_cell = cells[5]
        pnl_cell.text = ""
        pp = pnl_cell.paragraphs[0]
        pp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        pr = pp.add_run(pnl_text)
        pr.font.size = Pt(9.5)
        if pnl_val > 0:
            pr.font.color.rgb = RGBColor(0x14, 0x6C, 0x43)
        elif pnl_val < 0:
            pr.font.color.rgb = RGBColor(0xB4, 0x3A, 0x3A)
        _set_cell_text(cells[6], f"{r.get('weight', 0):.1f}%",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        if i % 2 == 0:
            for cell in cells:
                _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


def _drift_analysis(doc: Document, ctx: dict) -> None:
    """Per-position drift vs the configured profile target."""
    review = ctx.get("review") or {}
    drift = review.get("drift") or {}
    rows = drift.get("rows") or []
    if not rows:
        return

    lang = ctx.get("lang", I18N_DEFAULT)
    profile = ctx.get("client", {}).get("profile", "")
    threshold = drift.get("threshold_pp", 0)

    _section_header(doc, ctx, "page.drift_analysis", _T(ctx, "page.drift_analysis"))

    sub = doc.add_paragraph()
    sr = sub.add_run(_T(
        ctx, "drift_analysis.subheading",
        profile=profile_label(profile, lang),
        threshold=f"{threshold:.0f}",
    ))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    # Callout for the largest drift.
    max_ticker = drift.get("max_drift_ticker")
    max_pp = drift.get("max_drift_pp", 0)
    if max_ticker:
        status_key = "drift_analysis.attention_yes" if drift.get("attention") else "drift_analysis.attention_no"
        callout = doc.add_paragraph()
        cr = callout.add_run(_T(
            ctx, "drift_analysis.max_drift_callout",
            ticker=max_ticker, drift=f"{max_pp:.1f}",
            status=_T(ctx, status_key),
        ))
        cr.font.size = Pt(10)
        cr.font.bold = True
        cr.font.color.rgb = SUNSET_EMBER if drift.get("attention") else TEXT_BODY

    headers = [
        _T(ctx, "table.asset"),
        _T(ctx, "table.weight_now"),
        _T(ctx, "table.weight_target"),
        _T(ctx, "table.drift_pp"),
    ]
    dtable = doc.add_table(rows=1 + len(rows), cols=len(headers))
    for i, hd in enumerate(headers):
        _set_cell_text(dtable.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(dtable.rows[0].cells[i], "010626")
    for i, r in enumerate(rows, start=1):
        cells = dtable.rows[i].cells
        _set_cell_text(cells[0], r.get("ticker", ""), bold=True, size_pt=10)
        _set_cell_text(cells[1], f"{r.get('current_pct', 0):.2f}%",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[2], f"{r.get('target_pct', 0):.2f}%",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        drift_pp = float(r.get("drift_pp", 0) or 0)
        sign = "+" if drift_pp > 0 else ""
        drift_cell = cells[3]
        drift_cell.text = ""
        dp = drift_cell.paragraphs[0]
        dp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        dr = dp.add_run(f"{sign}{drift_pp:.2f}pp")
        dr.font.size = Pt(9.5)
        dr.font.bold = abs(drift_pp) >= float(threshold or 0)
        if abs(drift_pp) >= float(threshold or 0):
            dr.font.color.rgb = SUNSET_EMBER
        if i % 2 == 0:
            for cell in cells:
                _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


def _rebalance_actions(doc: Document, ctx: dict) -> None:
    """Recommended BUY/SELL trades to bring the portfolio to target."""
    review = ctx.get("review") or {}
    rebal = review.get("rebalance") or {}
    rows = rebal.get("rows") or []
    actionable = [r for r in rows if (r.get("action") or "") and abs(float(r.get("difference") or 0)) > 1]
    lang = ctx.get("lang", I18N_DEFAULT)
    profile = ctx.get("client", {}).get("profile", "")
    net = rebal.get("net_rebalance", 0)

    _section_header(doc, ctx, "page.rebalance", _T(ctx, "page.rebalance"))

    sub = doc.add_paragraph()
    sr = sub.add_run(_T(
        ctx, "rebalance.subheading",
        profile=profile_label(profile, lang),
        net=_money(ctx, net),
    ))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    if not actionable:
        p = doc.add_paragraph()
        pr = p.add_run(_T(ctx, "rebalance.no_action"))
        pr.font.italic = True
        pr.font.color.rgb = TEXT_MUTED
        pr.font.size = Pt(10.5)
        doc.add_page_break()
        return

    headers = [
        _T(ctx, "table.asset"),
        _T(ctx, "table.weight_target"),
        _T(ctx, "table.market_value"),
        _T(ctx, "table.delta_usd"),
        _T(ctx, "table.action"),
    ]
    rtable = doc.add_table(rows=1 + len(actionable), cols=len(headers))
    for i, hd in enumerate(headers):
        _set_cell_text(rtable.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(rtable.rows[0].cells[i], "010626")
    for i, r in enumerate(actionable, start=1):
        cells = rtable.rows[i].cells
        c = cells[0]
        c.text = ""
        p = c.paragraphs[0]
        rt = p.add_run(r.get("ticker", ""))
        rt.font.bold = True
        rt.font.size = Pt(10)
        rn = p.add_run(f"  {r.get('name', '')}")
        rn.font.size = Pt(9)
        rn.font.color.rgb = TEXT_MUTED
        _set_cell_text(cells[1], f"{(r.get('target_pct') or 0) * 100:.2f}%",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        _set_cell_text(cells[2], _money(ctx, r.get("current_usd", 0)),
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        delta = float(r.get("difference") or 0)
        sign = "+" if delta > 0 else ""
        _set_cell_text(cells[3], f"{sign}{_money(ctx, delta)}",
                       align=WD_ALIGN_PARAGRAPH.RIGHT, size_pt=9.5)
        action_cell = cells[4]
        action_cell.text = ""
        ap = action_cell.paragraphs[0]
        ap.alignment = WD_ALIGN_PARAGRAPH.LEFT
        ar = ap.add_run(r.get("action", ""))
        ar.font.bold = True
        ar.font.size = Pt(9.5)
        if r.get("action") == "BUY":
            ar.font.color.rgb = RGBColor(0x14, 0x6C, 0x43)
        elif r.get("action") == "SELL":
            ar.font.color.rgb = RGBColor(0xB4, 0x3A, 0x3A)
        if i % 2 == 0:
            for cell in cells:
                _shade_cell(cell, "F6F4F0")

    doc.add_page_break()


def _contact_section(doc: Document, ctx: dict) -> None:
    """Advisor contact table. Always rendered (every IA proposal needs
    one); falls back to the document author when override fields are
    empty."""
    ov = ctx.get("overrides") or {}
    advisor_name = (ctx.get("prepared_by") or "").strip()
    advisor_email = ov.get("advisor_email") or ""
    advisor_phone = ov.get("advisor_phone") or ""
    if not (advisor_name or advisor_email or advisor_phone):
        return

    _section_header(doc, ctx, "page.contact", _T(ctx, "page.contact"))
    sub = doc.add_paragraph()
    sr = sub.add_run(_T(ctx, "contact.subheading"))
    sr.font.size = Pt(9.5)
    sr.font.italic = True
    sr.font.color.rgb = TEXT_MUTED

    table = doc.add_table(rows=2, cols=3)
    headers = [
        _T(ctx, "contact.col_advisor"),
        _T(ctx, "contact.col_email"),
        _T(ctx, "contact.col_phone"),
    ]
    for i, hd in enumerate(headers):
        _set_cell_text(table.rows[0].cells[i], hd, bold=True, color=WHITE, size_pt=9.5)
        _shade_cell(table.rows[0].cells[i], "010626")
    row_vals = [advisor_name, advisor_email, advisor_phone]
    for i, v in enumerate(row_vals):
        _set_cell_text(table.rows[1].cells[i], v, size_pt=10.5)

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
    # In review mode the same per-ticker target table reads as "what we
    # rebalance toward", so swap the kicker label to "Target allocation".
    kicker_key = (
        "page.target_allocation"
        if (ctx.get("proposal_type") or "").lower() == "review"
        else "page.allocation"
    )
    _section_header(doc, ctx, kicker_key, ctx.get("allocation_title", ""))

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

    Two flavours, switched on ``ctx['proposal_type']``:

    * ``"new"`` (default) — onboarding allocation proposal. Section
      order mirrors Jannick Bröring's WIP IA template: cover → welcome
      → client info → consultation summary → market analysis →
      portfolio detail → recommended allocation → strategy → macro
      framing → fazit → wishes → fees → contact → appendix.

    * ``"review"`` — existing-client portfolio review. Inserts three
      review-specific sections after market analysis: current
      holdings + P&L, drift vs target, recommended rebalance trades.
      The target-allocation section is still rendered but reads as
      "what we are rebalancing toward", not "what we propose buying".

    The returned bytes are a complete .docx archive suitable for the
    response body of a FastAPI handler.
    """
    doc = Document()
    _set_default_font(doc)
    _page_setup(doc)

    proposal_type = (ctx.get("proposal_type") or "new").strip().lower()
    is_review = proposal_type == "review"

    _cover(doc, ctx)
    _welcome(doc, ctx)
    _client_info(doc, ctx)
    _consultation_summary(doc, ctx)
    _market_analysis(doc, ctx)
    if is_review:
        _current_holdings(doc, ctx)
        _drift_analysis(doc, ctx)
    _portfolio_detail(doc, ctx)
    _allocation_table(doc, ctx)
    if is_review:
        _rebalance_actions(doc, ctx)
    _strategy_section(doc, ctx)
    _macro_section(doc, ctx)
    _fazit_section(doc, ctx)
    _wishes_section(doc, ctx)
    _fees_section(doc, ctx)
    _contact_section(doc, ctx)
    _appendix(doc, ctx)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


__all__ = ["render_docx"]
