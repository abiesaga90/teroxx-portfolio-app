"""Brand palette used by SVG exhibits and the PDF/HTML templates.

The same hex values live in `app/static/css/teroxx.css` as CSS variables;
this is the Python-side mirror for SVG generators that don't have CSS
custom properties available.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrandPalette:
    # Six brand colors from Short Brand Guideline VS1.0, section 3.2.
    nightblue: str = "#010626"
    deep_indigo: str = "#060D43"
    electric_sky: str = "#0B688C"
    sandstone: str = "#BFB3A8"
    sunset_ember: str = "#D06643"
    white: str = "#FFFFFF"
    black: str = "#000000"

    # Operational tints derived from the six brand colors — used for
    # backgrounds, zebra stripes, and disclaimer blocks. Not in the
    # brand book but stay inside the Sandstone family so the doc reads
    # as one palette.
    cream: str = "#ECE8E5"           # Sandstone tint @ ~12%
    sandstone_50: str = "#F4F1ED"    # Sandstone tint @ ~6% — zebra row

    # Semantic mappings for gain/loss. Brand palette deliberately has no
    # green, so gains map to Electric Sky and losses to Sunset Ember.
    # Anywhere we historically used #1A8A4A / #C0432A should call these.
    gain: str = "#0B688C"            # = electric_sky
    loss: str = "#D06643"            # = sunset_ember

    @property
    def primary_series(self) -> tuple[str, ...]:
        """Ordered palette for multi-series charts. Per brand guideline:
        Nightblue → Electric Sky → Sunset Ember → Sandstone → Deep Indigo."""
        return (
            self.nightblue,
            self.electric_sky,
            self.sunset_ember,
            self.sandstone,
            self.deep_indigo,
        )

    @property
    def chart_series(self) -> tuple[str, ...]:
        """Distinct, harmonious sequence for charts with many segments
        (donut, tier bar). The strict brand ``primary_series`` works for <=4
        slices but breaks down beyond that: Nightblue and Deep Indigo read as
        the same near-black, and the legacy overflow tints repeated Sandstone
        and ended on a near-white ``cream`` that vanished on the page.

        This leads with the four clearly-distinct brand colours, then extends
        with restrained tints from the same families (a muted indigo-slate, a
        softer ember, a cool slate grey, a light teal) so an eight-name
        allocation still reads as one precise, private-bank palette with no two
        segments confusable and nothing washing out.
        """
        return (
            self.nightblue,      # deep navy
            self.electric_sky,   # teal
            self.sunset_ember,   # terracotta accent
            self.sandstone,      # warm neutral
            "#3C4A6B",           # muted indigo-slate
            "#E2A98F",           # soft ember tint
            "#6E7B82",           # cool slate grey
            "#5E9DB5",           # light teal
        )


PALETTE = BrandPalette()
