"""Brand palette used by SVG exhibits and the PDF/HTML templates.

The same hex values live in `app/static/css/teroxx.css` as CSS variables;
this is the Python-side mirror for SVG generators that don't have CSS
custom properties available.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrandPalette:
    nightblue: str = "#010626"
    deep_indigo: str = "#060D43"
    electric_sky: str = "#0B688C"
    sandstone: str = "#BFB3A8"
    cream: str = "#ECE8E5"
    sunset_ember: str = "#D06643"
    white: str = "#FFFFFF"
    success: str = "#1A8A4A"
    danger: str = "#C0432A"

    @property
    def primary_series(self) -> tuple[str, ...]:
        """Ordered palette for multi-series charts: structure, primary, accent, neutral, support."""
        return (
            self.nightblue,
            self.electric_sky,
            self.sunset_ember,
            self.sandstone,
            self.deep_indigo,
            self.success,
            self.danger,
        )


PALETTE = BrandPalette()
