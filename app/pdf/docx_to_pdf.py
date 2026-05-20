"""DOCX to PDF conversion via headless LibreOffice.

The proposal pipeline has a SINGLE source of truth: ``render_docx`` in
``proposal_docx.py``. The PDF download and the Google Docs export are
both *derived* from that one DOCX:

    render_docx(ctx)  ->  .docx           (the canonical artifact)
                      ->  this module     ->  .pdf
                      ->  google_docs.py  ->  Google Doc

Because PDF and Google Docs are conversions, not independent renders,
the three outputs cannot drift apart. Do NOT reintroduce a separate
PDF template/renderer — that divergence is exactly what this design
removes (the old WeasyPrint ``proposal.html`` had fallen ~10 sections
behind the DOCX).

This module shells out to LibreOffice (installed in the Docker image),
with the Teroxx brand fonts available system-wide so the PDF stays
on-brand.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

logger = logging.getLogger("teroxx.docx_to_pdf")

# LibreOffice binary. Overridable for local dev (e.g. macOS installs it
# at /Applications/LibreOffice.app/Contents/MacOS/soffice).
_SOFFICE = os.getenv("SOFFICE_BIN", "soffice")


class DocxToPdfError(RuntimeError):
    """Raised when the LibreOffice conversion fails."""


def docx_bytes_to_pdf(docx_bytes: bytes, *, timeout: int = 120) -> bytes:
    """Convert a ``.docx`` (bytes) to PDF (bytes) via headless LibreOffice.

    Blocking — call via a threadpool from async request handlers.
    """
    workdir = tempfile.mkdtemp(prefix="teroxx_pdf_")
    # Per-conversion LibreOffice user profile: lets concurrent requests
    # convert without contending over a shared profile lock.
    profile = os.path.join(workdir, "louser")
    src = os.path.join(workdir, "proposal.docx")
    out = os.path.join(workdir, "proposal.pdf")
    try:
        with open(src, "wb") as f:
            f.write(docx_bytes)
        cmd = [
            _SOFFICE,
            "--headless",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "pdf",
            "--outdir", workdir,
            src,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=timeout, check=False,
            )
        except FileNotFoundError as e:
            raise DocxToPdfError(
                f"LibreOffice ({_SOFFICE}) is not installed."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise DocxToPdfError("LibreOffice conversion timed out.") from e

        if proc.returncode != 0 or not os.path.exists(out):
            raise DocxToPdfError(
                f"LibreOffice conversion failed (rc={proc.returncode}): "
                f"{proc.stderr.decode('utf-8', 'replace')[:400]}"
            )
        with open(out, "rb") as f:
            pdf = f.read()
        if not pdf:
            raise DocxToPdfError("LibreOffice produced an empty PDF.")
        return pdf
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
