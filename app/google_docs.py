"""Google Docs export for proposals.

Takes the bytes of a generated proposal ``.docx`` and uploads them to
Google Drive, converting the file to a native Google Docs document so
an advisor can open and edit it in the browser. The proposal endpoints
use this to offer an "Open in Google Docs" option next to the existing
``.docx`` download.

Auth is a Google service account. Two deployment shapes are supported,
selected purely by which env vars are set:

  * **Shared Drive** (no Workspace admin needed) — create a Shared Drive
    in Google Drive, add the service account's email as a Content
    Manager, and point ``GOOGLE_DRIVE_FOLDER_ID`` at a folder inside it.
    Docs are owned by the Shared Drive, so the whole team sees them.

  * **Domain-wide delegation** (needs a Workspace admin one-time grant)
    — authorise the service account for the Drive scope in the Google
    Admin console, then set ``GOOGLE_IMPERSONATE_SUBJECT`` to a
    teroxx.com user. Docs are then created as (and owned by) that user
    and appear in their My Drive. ``GOOGLE_DRIVE_FOLDER_ID`` is optional
    here; if unset the doc lands in the impersonated user's Drive root.

Env vars
--------
GOOGLE_SERVICE_ACCOUNT_JSON   Required. The service account key, either
                              as raw JSON or base64-encoded JSON.
GOOGLE_DRIVE_FOLDER_ID        Optional. Target folder (Shared Drive
                              folder or a My Drive folder).
GOOGLE_IMPERSONATE_SUBJECT    Optional. User to impersonate via
                              domain-wide delegation, e.g.
                              aleksander.biesaga@teroxx.com.
GOOGLE_DOCS_SHARE             Optional. One of none | domain | anyone.
                              How the created doc is shared. Default
                              "none" (rely on Shared Drive membership /
                              the impersonated owner).
GOOGLE_DOCS_SHARE_DOMAIN      Optional. Domain for share=domain.
                              Default "teroxx.com".
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import threading

logger = logging.getLogger("teroxx.google_docs")

# Full Drive scope: needed to create files and to set sharing
# permissions on them.
_SCOPES = ["https://www.googleapis.com/auth/drive"]

_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_GDOC_MIME = "application/vnd.google-apps.document"

# Lazily-built Drive client, reused across requests. Service account
# credentials refresh their own access tokens, so a single client is
# safe for the lifetime of the process.
_service_lock = threading.Lock()
_service = None


class GoogleDocsError(RuntimeError):
    """Raised when the Google Docs export cannot be completed."""


def is_configured() -> bool:
    """True when a service account key is present in the environment."""
    return bool(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip())


def _load_key_info() -> dict:
    """Parse GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON or base64 JSON)."""
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise GoogleDocsError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is not set — Google Docs export "
            "is not configured."
        )
    # Try raw JSON first, then fall back to base64 (handy for setting a
    # single-line value in the Render dashboard).
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise GoogleDocsError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is neither valid JSON nor "
            "base64-encoded JSON."
        ) from e


def service_account_email() -> str | None:
    """The service account's client_email, for setup/diagnostics."""
    try:
        return _load_key_info().get("client_email")
    except GoogleDocsError:
        return None


def _build_service():
    """Build (and cache) an authenticated Drive v3 client."""
    global _service
    if _service is not None:
        return _service
    with _service_lock:
        if _service is not None:
            return _service
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as e:  # noqa: BLE001
            raise GoogleDocsError(
                "Google client libraries are not installed "
                "(google-api-python-client / google-auth)."
            ) from e

        info = _load_key_info()
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=_SCOPES
        )
        subject = os.getenv("GOOGLE_IMPERSONATE_SUBJECT", "").strip()
        if subject:
            # Domain-wide delegation: act as a real Workspace user.
            creds = creds.with_subject(subject)

        _service = build(
            "drive",
            "v3",
            credentials=creds,
            cache_discovery=False,
            static_discovery=True,
        )
        return _service


def _apply_sharing(service, file_id: str) -> None:
    """Set link-sharing on the created doc per GOOGLE_DOCS_SHARE.

    Failures here are logged but not fatal — the doc already exists and
    the caller still gets a working link (visible to Shared Drive
    members / the owning user even without an explicit permission).
    """
    mode = os.getenv("GOOGLE_DOCS_SHARE", "none").strip().lower()
    if mode in ("", "none"):
        return
    if mode == "domain":
        body = {
            "type": "domain",
            "role": "writer",
            "domain": os.getenv("GOOGLE_DOCS_SHARE_DOMAIN", "teroxx.com").strip(),
        }
    elif mode == "anyone":
        body = {"type": "anyone", "role": "writer"}
    else:
        logger.warning("Unknown GOOGLE_DOCS_SHARE value %r — skipping.", mode)
        return
    try:
        service.permissions().create(
            fileId=file_id,
            body=body,
            supportsAllDrives=True,
            sendNotificationEmail=False,
        ).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not set sharing on %s: %s", file_id, e)


def upload_docx_as_gdoc(docx_bytes: bytes, title: str) -> str:
    """Upload ``docx_bytes`` to Drive as a native Google Doc.

    Returns the ``webViewLink`` of the created document. Blocking — call
    via a threadpool from async request handlers.
    """
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as e:  # noqa: BLE001
        raise GoogleDocsError(
            "Google client libraries are not installed "
            "(google-api-python-client / google-auth)."
        ) from e

    service = _build_service()

    metadata = {"name": title, "mimeType": _GDOC_MIME}
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder_id:
        metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(
        io.BytesIO(docx_bytes), mimetype=_DOCX_MIME, resumable=False
    )

    try:
        created = (
            service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception as e:  # noqa: BLE001
        raise GoogleDocsError(f"Drive upload failed: {e}") from e

    file_id = created.get("id")
    link = created.get("webViewLink")
    if not file_id or not link:
        raise GoogleDocsError("Drive upload returned no file id / link.")

    _apply_sharing(service, file_id)
    return link


def status() -> dict:
    """Configuration snapshot, for the /api/google-docs/status endpoint."""
    return {
        "configured": is_configured(),
        "service_account_email": service_account_email(),
        "folder_id": os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None,
        "impersonate": os.getenv("GOOGLE_IMPERSONATE_SUBJECT", "").strip() or None,
        "share": os.getenv("GOOGLE_DOCS_SHARE", "none").strip().lower() or "none",
    }
