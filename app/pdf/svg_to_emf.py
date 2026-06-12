"""SVG to EMF conversion via headless LibreOffice.

The proposal embeds charts as hand-authored SVG. Historically those SVGs were
rasterised to PNG (cairosvg) before being placed in the DOCX, which looked soft
in print. This module converts them to **EMF** instead — Word's native vector
metafile — so the charts stay crisp at any zoom in Word, the LibreOffice PDF,
and Google Docs, with tiny file sizes.

It reuses the same LibreOffice binary already required for the DOCX->PDF step
(see ``docx_to_pdf.py``), so no new dependency is introduced. ``add_picture``
accepts EMF (embedded as ``image/x-emf``), and LibreOffice preserves EMF picture
parts as vector through its own DOCX->PDF conversion.

Design contract, mirrored from ``docx_to_pdf.py``:
  * per-conversion temp dir + isolated LibreOffice user profile, so concurrent
    requests don't contend on the shared profile lock;
  * a hard timeout;
  * **never raises** — any failure returns ``None`` (single) or omits the chart
    (batch), so the caller silently falls back to a high-DPI PNG and a chart
    problem can never break a whole proposal.

``svgs_to_emf`` converts several charts in ONE soffice invocation (soffice
accepts multiple input files), which matters because process cold-start
dominates: 3 charts in one spawn instead of three.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger("teroxx.svg_to_emf")

# Same binary as docx_to_pdf.py. Overridable for local dev (macOS installs it
# at /Applications/LibreOffice.app/Contents/MacOS/soffice).
_SOFFICE = os.getenv("SOFFICE_BIN", "soffice")


def vector_charts_enabled() -> bool:
    """Whether to attempt EMF (vector) charts. Default on; set
    ``TEROXX_VECTOR_CHARTS=0`` to force the high-DPI PNG path (e.g. local dev
    without LibreOffice)."""
    return os.getenv("TEROXX_VECTOR_CHARTS", "1").strip().lower() not in ("0", "false", "no")


def svgs_to_emf(svgs: dict[str, str], *, timeout: int = 30) -> dict[str, bytes]:
    """Convert ``{name: svg_string}`` to ``{name: emf_bytes}`` in one soffice
    spawn. Names missing from the result simply failed to convert and the
    caller falls back per chart. Returns ``{}`` on total failure.
    """
    if not svgs or not vector_charts_enabled():
        return {}
    workdir = tempfile.mkdtemp(prefix="teroxx_emf_")
    profile = os.path.join(workdir, "louser")
    try:
        src_paths = []
        for name, svg in svgs.items():
            if not svg:
                continue
            p = os.path.join(workdir, f"{name}.svg")
            with open(p, "w", encoding="utf-8") as f:
                f.write(svg)
            src_paths.append((name, p))
        if not src_paths:
            return {}
        cmd = [
            _SOFFICE,
            "--headless",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "emf",
            "--outdir", workdir,
            *[p for _, p in src_paths],
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
        except FileNotFoundError:
            logger.warning("LibreOffice (%s) not found; charts fall back to PNG.", _SOFFICE)
            return {}
        except subprocess.TimeoutExpired:
            logger.warning("SVG->EMF batch timed out; charts fall back to PNG.")
            return {}
        if proc.returncode != 0:
            logger.warning(
                "SVG->EMF batch rc=%s: %s", proc.returncode,
                proc.stderr.decode("utf-8", "replace")[:300],
            )
        out: dict[str, bytes] = {}
        for name, _ in src_paths:
            emf_path = os.path.join(workdir, f"{name}.emf")
            if os.path.exists(emf_path):
                with open(emf_path, "rb") as f:
                    data = f.read()
                if data:
                    out[name] = data
        return out
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def svg_bytes_to_emf(svg: str, *, timeout: int = 60) -> bytes | None:
    """Convert a single SVG string to EMF bytes, or ``None`` on any failure.

    Blocking — call via a threadpool from async request handlers. Prefer
    ``svgs_to_emf`` when converting several charts (one process spawn).
    """
    result = svgs_to_emf({"chart": svg}, timeout=timeout)
    return result.get("chart")
