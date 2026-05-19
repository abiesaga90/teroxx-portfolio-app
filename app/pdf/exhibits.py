"""Hand-rolled SVG exhibit builders.

Each function returns an SVG string ready to embed into a Jinja template
(`{{ exhibits.donut(...) | safe }}`). SVG is preferred over PNG so
exhibits stay crisp at any zoom and use embedded brand fonts. WeasyPrint
renders these as vector elements in the final PDF.

Design conventions:
- Output width is the viewBox width; the template wraps SVGs in a sized
  container so callers control layout independently.
- Brand palette comes from `BrandPalette`; functions accept an explicit
  palette for testing but default to `PALETTE`.
- Typography: SometimesTimes for headline numbers, Sohne for labels.
- All text uses `font-family="..."` strings that match the @font-face
  rules in `proposal.css`.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

from app.pdf.palette import PALETTE, BrandPalette


_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
_FOOT = "</svg>"


def _escape(text: str) -> str:
    """Minimal XML escape for label content embedded in SVG text nodes."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ── Donut (allocation share) ────────────────────────────────────────


def donut(
    slices: list[tuple[str, float]],
    *,
    width: int = 280,
    height: int = 280,
    center_text: Optional[str] = None,
    center_sub: Optional[str] = None,
    palette: BrandPalette = PALETTE,
    max_slices: int = 8,
) -> str:
    """Build a donut chart SVG.

    `slices` is a list of (label, value) pairs; values are normalised so
    they sum to 1. Slices beyond `max_slices` are merged into "Other" so
    the chart stays legible at the McKinsey-quality bar.
    """
    total = sum(max(0.0, v) for _, v in slices)
    if total <= 0:
        return _HEAD.format(w=width, h=height) + _FOOT
    rows = sorted(
        ((label, max(0.0, v) / total) for label, v in slices if v > 0),
        key=lambda r: -r[1],
    )
    if len(rows) > max_slices:
        head = rows[: max_slices - 1]
        tail_share = sum(r[1] for r in rows[max_slices - 1 :])
        rows = head + [("Other", tail_share)]

    cx, cy = width / 2, height / 2
    r_outer = min(cx, cy) - 16
    r_inner = r_outer - 36
    palette_colors = palette.primary_series + (palette.sandstone, palette.cream)

    paths: list[str] = []
    angle = -math.pi / 2  # start at 12 o'clock
    for i, (_, share) in enumerate(rows):
        if share <= 0:
            continue
        end = angle + share * 2 * math.pi
        large = 1 if (end - angle) > math.pi else 0
        # Outer arc
        x1o, y1o = cx + r_outer * math.cos(angle), cy + r_outer * math.sin(angle)
        x2o, y2o = cx + r_outer * math.cos(end), cy + r_outer * math.sin(end)
        # Inner arc
        x1i, y1i = cx + r_inner * math.cos(end), cy + r_inner * math.sin(end)
        x2i, y2i = cx + r_inner * math.cos(angle), cy + r_inner * math.sin(angle)
        color = palette_colors[i % len(palette_colors)]
        d = (
            f"M {x1o:.2f} {y1o:.2f} "
            f"A {r_outer:.2f} {r_outer:.2f} 0 {large} 1 {x2o:.2f} {y2o:.2f} "
            f"L {x1i:.2f} {y1i:.2f} "
            f"A {r_inner:.2f} {r_inner:.2f} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z"
        )
        paths.append(f'<path d="{d}" fill="{color}" />')
        angle = end

    center: list[str] = []
    if center_text:
        center.append(
            f'<text x="{cx:.2f}" y="{cy - 4:.2f}" text-anchor="middle" '
            f'font-family="SometimesTimes, Georgia, serif" font-size="22" '
            f'fill="{palette.nightblue}">{_escape(center_text)}</text>'
        )
    if center_sub:
        center.append(
            f'<text x="{cx:.2f}" y="{cy + 14:.2f}" text-anchor="middle" '
            f'font-family="Sohne, Arial, sans-serif" font-size="9" '
            f'letter-spacing="0.08em" fill="{palette.deep_indigo}" '
            f'opacity="0.65">{_escape(center_sub.upper())}</text>'
        )

    body = "".join(paths) + "".join(center)
    return _HEAD.format(w=width, h=height) + body + _FOOT


def donut_legend(slices: list[tuple[str, float]], *, palette: BrandPalette = PALETTE,
                 max_slices: int = 8) -> list[dict]:
    """Return the legend rows matching what donut() draws, with computed share %."""
    total = sum(max(0.0, v) for _, v in slices)
    rows = []
    if total <= 0:
        return rows
    rows_raw = sorted(((label, max(0.0, v) / total) for label, v in slices if v > 0),
                      key=lambda r: -r[1])
    if len(rows_raw) > max_slices:
        head = rows_raw[: max_slices - 1]
        tail_share = sum(r[1] for r in rows_raw[max_slices - 1 :])
        rows_raw = head + [("Other", tail_share)]
    colors = palette.primary_series + (palette.sandstone, palette.cream)
    for i, (label, share) in enumerate(rows_raw):
        rows.append({
            "label": label,
            "share_pct": share * 100,
            "color": colors[i % len(colors)],
        })
    return rows


# ── Horizontal tier bar ─────────────────────────────────────────────


def tier_bar(
    tiers: list[tuple[str, float]],
    *,
    width: int = 520,
    height: int = 180,
    palette: BrandPalette = PALETTE,
) -> str:
    """Stacked horizontal bar by tier (defensive/core/extended/...) summing to 100%.

    `tiers` is a list of (tier_label, share) pairs.
    """
    total = sum(max(0.0, v) for _, v in tiers) or 1.0
    bar_h = 36
    bar_y = height - bar_h - 36
    bar_w = width - 32
    bar_x = 16
    palette_colors = palette.primary_series

    parts: list[str] = []
    # Title
    parts.append(
        f'<text x="{bar_x}" y="22" font-family="SometimesTimes, Georgia, serif" '
        f'font-size="13" fill="{palette.nightblue}">Allocation by tier</text>'
    )
    parts.append(
        f'<text x="{bar_x}" y="40" font-family="Sohne, Arial, sans-serif" '
        f'font-size="9" letter-spacing="0.06em" fill="{palette.deep_indigo}" '
        f'opacity="0.55">SHARE OF PORTFOLIO</text>'
    )

    x = bar_x
    legend_y = bar_y + bar_h + 22
    legend_x = bar_x
    for i, (label, share) in enumerate(tiers):
        share = max(0.0, share)
        seg_w = (share / total) * bar_w
        color = palette_colors[i % len(palette_colors)]
        parts.append(
            f'<rect x="{x:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}" />'
        )
        # In-bar percent label if wide enough
        if seg_w > 38:
            parts.append(
                f'<text x="{x + seg_w / 2:.2f}" y="{bar_y + bar_h / 2 + 4:.2f}" '
                f'text-anchor="middle" font-family="Sohne, Arial, sans-serif" '
                f'font-size="11" font-weight="600" fill="{palette.white}">'
                f'{share * 100:.1f}%</text>'
            )
        # Legend row
        parts.append(
            f'<rect x="{legend_x}" y="{legend_y - 8}" width="10" height="10" fill="{color}" />'
            f'<text x="{legend_x + 16}" y="{legend_y + 1}" '
            f'font-family="Sohne, Arial, sans-serif" font-size="10" '
            f'fill="{palette.deep_indigo}">{_escape(label)} '
            f'<tspan fill="{palette.deep_indigo}" opacity="0.55">{share * 100:.1f}%</tspan>'
            f'</text>'
        )
        x += seg_w
        legend_x += 130

    return _HEAD.format(w=width, h=height) + "".join(parts) + _FOOT


# ── Regime gauge (0..100 composite score) ───────────────────────────


def regime_gauge(
    score: float,
    *,
    label: str,
    color: str,
    width: int = 320,
    height: int = 200,
    palette: BrandPalette = PALETTE,
) -> str:
    """Semi-circular gauge for the macro composite score.

    Track is sandstone, fill is the regime colour, needle points at the
    score, the centre prints the value in SometimesTimes.
    """
    cx, cy = width / 2, height - 36
    r = min(width / 2 - 18, height - 60)
    score = max(0.0, min(100.0, score or 0.0))
    # Map score 0..100 to angle 180..360 degrees (left to right).
    angle = math.radians(180 + (score / 100) * 180)
    end_x = cx + r * math.cos(angle)
    end_y = cy + r * math.sin(angle)
    needle_x = cx + (r - 18) * math.cos(angle)
    needle_y = cy + (r - 18) * math.sin(angle)

    # Background half-track (left to right)
    bg = (
        f'<path d="M {cx - r:.2f} {cy:.2f} A {r:.2f} {r:.2f} 0 0 1 {cx + r:.2f} {cy:.2f}" '
        f'stroke="{palette.sandstone}" stroke-width="14" fill="none" '
        f'stroke-linecap="round" />'
    )
    # Filled arc up to the score
    large = 1 if score > 50 else 0
    fill = (
        f'<path d="M {cx - r:.2f} {cy:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {end_x:.2f} {end_y:.2f}" '
        f'stroke="{color}" stroke-width="14" fill="none" stroke-linecap="round" />'
    )
    # Tick marks at 0/25/50/75/100
    ticks: list[str] = []
    for v in (0, 25, 50, 75, 100):
        a = math.radians(180 + (v / 100) * 180)
        x1 = cx + (r + 4) * math.cos(a)
        y1 = cy + (r + 4) * math.sin(a)
        x2 = cx + (r + 14) * math.cos(a)
        y2 = cy + (r + 14) * math.sin(a)
        ticks.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{palette.deep_indigo}" stroke-opacity="0.45" stroke-width="1" />'
        )
        lx = cx + (r + 24) * math.cos(a)
        ly = cy + (r + 24) * math.sin(a) + 4
        ticks.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="middle" '
            f'font-family="Sohne, Arial, sans-serif" font-size="9" '
            f'fill="{palette.deep_indigo}" opacity="0.55">{v}</text>'
        )
    # Needle
    needle = (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="4" fill="{palette.nightblue}" />'
        f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{needle_x:.2f}" y2="{needle_y:.2f}" '
        f'stroke="{palette.nightblue}" stroke-width="2.5" stroke-linecap="round" />'
    )
    # Centre text
    centre = (
        f'<text x="{cx:.2f}" y="{cy - 18:.2f}" text-anchor="middle" '
        f'font-family="SometimesTimes, Georgia, serif" font-size="34" '
        f'fill="{color}">{int(score)}</text>'
        f'<text x="{cx:.2f}" y="{cy - 2:.2f}" text-anchor="middle" '
        f'font-family="Sohne, Arial, sans-serif" font-size="10" '
        f'letter-spacing="0.10em" fill="{palette.deep_indigo}" '
        f'opacity="0.7">{_escape(label.upper())}</text>'
    )
    return (
        _HEAD.format(w=width, h=height)
        + bg + fill + "".join(ticks) + needle + centre
        + _FOOT
    )


# ── Sparkline (per-asset price last N points) ───────────────────────


def sparkline(
    values: Iterable[float],
    *,
    width: int = 140,
    height: int = 36,
    palette: BrandPalette = PALETTE,
    color: Optional[str] = None,
) -> str:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return _HEAD.format(w=width, h=height) + _FOOT
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    color = color or palette.electric_sky
    pad = 2
    step = (width - pad * 2) / (len(vals) - 1)
    points = []
    for i, v in enumerate(vals):
        x = pad + i * step
        y = height - pad - ((v - lo) / (hi - lo)) * (height - pad * 2)
        points.append(f"{x:.2f},{y:.2f}")
    pl = " ".join(points)
    last_v = vals[-1]
    color_end = palette.gain if last_v >= vals[0] else palette.loss
    body = (
        f'<polyline points="{pl}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" />'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="2.4" fill="{color_end}" />'
    )
    return _HEAD.format(w=width, h=height) + body + _FOOT


__all__ = ["donut", "donut_legend", "tier_bar", "regime_gauge", "sparkline"]
