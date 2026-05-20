"""Proposal rendering: DOCX builder, SVG exhibits, narrative, brand palette.

The proposal has a single source of truth — `proposal_docx.render_docx`
builds the canonical .docx. The PDF (`docx_to_pdf`) and the Google Docs
export (`app.google_docs`) are conversions of that .docx, so the three
outputs always match. This package also owns the pure-Python helpers
(exhibits, narrative) the builder depends on.
"""
