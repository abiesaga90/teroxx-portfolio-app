"""Stable v1 API surface for CRM and external integrations.

Phase 9 ships the seam, not the integrations. The endpoints under
`/api/v1` are bearer-token-authenticated and intentionally narrow:
list / read / create / update clients and lots, plus an HMAC-validated
webhook receiver under `/webhooks/crm/{provider}`. We do not build the
actual HubSpot / Salesforce clients here.

Token format. Plaintext tokens look like `tax_<12-hex>_<32-hex>`. The
prefix `tax_<12-hex>` is stored for lookup; the remaining secret is
sha256-hashed with a per-token salt before persistence. The full token
is only returned once at creation time via the admin route.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import ApiToken, SessionLocal, log_action
from app.repos import clients as clients_repo

logger = logging.getLogger(__name__)


# ── Token helpers ────────────────────────────────────────────────────


def _new_token() -> tuple[str, str, str, str]:
    """Mint a new plaintext token. Returns (plaintext, prefix, salt, hash)."""
    prefix = "tax_" + secrets.token_hex(6)  # 12 hex chars after the prefix
    secret = secrets.token_hex(16)
    salt = secrets.token_hex(8)
    plaintext = f"{prefix}_{secret}"
    token_hash = hashlib.sha256(f"{salt}:{secret}".encode()).hexdigest()
    return plaintext, prefix, salt, token_hash


def _parse_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _split_token(plaintext: str) -> Optional[tuple[str, str]]:
    if not plaintext or not plaintext.startswith("tax_"):
        return None
    bits = plaintext.split("_", 2)
    if len(bits) != 3:
        return None
    prefix = f"{bits[0]}_{bits[1]}"
    secret = bits[2]
    return prefix, secret


def _verify_token(plaintext: Optional[str]) -> Optional[dict]:
    """Return a plain dict snapshot of the token row (detached from the ORM)
    so route handlers can read fields after the session closes.
    """
    parsed = _split_token(plaintext or "")
    if not parsed:
        return None
    prefix, secret = parsed
    with SessionLocal() as db:
        from sqlalchemy import select
        candidate = db.execute(
            select(ApiToken).where(ApiToken.token_prefix == prefix, ApiToken.revoked_at.is_(None))
        ).scalar_one_or_none()
        if not candidate:
            return None
        expected = hashlib.sha256(f"{candidate.salt}:{secret}".encode()).hexdigest()
        if not hmac.compare_digest(expected, candidate.token_hash):
            return None
        candidate.last_used_at = datetime.now(timezone.utc)
        snapshot = {
            "id": candidate.id,
            "name": candidate.name,
            "provider": candidate.provider,
            "scopes": candidate.scopes or "",
        }
        db.commit()
        return snapshot


def require_token(authorization: Optional[str] = Header(default=None), required_scope: str = "clients:read") -> dict:
    token = _verify_token(_parse_bearer(authorization))
    if not token:
        raise HTTPException(status_code=401, detail="invalid_token")
    scopes = {s.strip() for s in token["scopes"].split(",")}
    if required_scope not in scopes and "admin" not in scopes:
        raise HTTPException(status_code=403, detail=f"missing_scope:{required_scope}")
    return token


# ── Router ───────────────────────────────────────────────────────────


router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/clients")
def list_clients_v1(token: dict = Depends(require_token)):
    with SessionLocal() as db:
        return [clients_repo.to_legacy_dict(c) for c in clients_repo.list_active_clients(db)]


@router.get("/clients/{client_id}")
def get_client_v1(client_id: str, token: dict = Depends(require_token)):
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return clients_repo.to_legacy_dict(c)


@router.post("/clients")
async def create_client_v1(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    token = _verify_token(_parse_bearer(authorization))
    if not token:
        raise HTTPException(status_code=401, detail="invalid_token")
    scopes = {s.strip() for s in token["scopes"].split(",")}
    if "clients:write" not in scopes and "admin" not in scopes:
        raise HTTPException(status_code=403, detail="missing_scope:clients:write")
    payload = await request.json()
    if not isinstance(payload, dict) or not payload.get("name"):
        return JSONResponse({"error": "name_required"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.create_client(
            db,
            actor_email=f"token:{token['name']}",
            name=payload.get("name", ""),
            profile=payload.get("profile", "Balanced"),
            domicile=payload.get("domicile"),
            domicile_country=payload.get("domicile_country"),
            currency=payload.get("currency", "USD"),
            inception_date=payload.get("inception_date"),
            starting_capital_usd=payload.get("starting_capital_usd"),
            tagline=payload.get("tagline"),
        )
        db.commit()
        db.refresh(c)
        return clients_repo.to_legacy_dict(c)


@router.patch("/clients/{client_id}")
async def update_client_v1(
    client_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    token = _verify_token(_parse_bearer(authorization))
    if not token:
        raise HTTPException(status_code=401, detail="invalid_token")
    scopes = {s.strip() for s in token["scopes"].split(",")}
    if "clients:write" not in scopes and "admin" not in scopes:
        raise HTTPException(status_code=403, detail="missing_scope:clients:write")
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"error": "invalid_body"}, status_code=400)
    with SessionLocal() as db:
        c = clients_repo.get_client(db, client_id)
        if not c:
            return JSONResponse({"error": "not_found"}, status_code=404)
        clients_repo.update_client(db, actor_email=f"token:{token['name']}", client=c, fields=payload)
        db.commit()
        db.refresh(c)
        return clients_repo.to_legacy_dict(c)


# ── Webhook receiver scaffold ────────────────────────────────────────


WEBHOOK_SECRETS: dict[str, str] = {}  # provider -> shared secret; populate at deploy time.


def _verify_signature(provider: str, body: bytes, signature_header: Optional[str]) -> bool:
    secret = WEBHOOK_SECRETS.get(provider)
    if not secret or not signature_header:
        # No secret means we refuse the request. Caller must configure a secret per provider.
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    candidate = signature_header.strip().lower()
    if candidate.startswith("sha256="):
        candidate = candidate[len("sha256="):]
    return hmac.compare_digest(expected, candidate)


@router.post("/webhooks/{provider}")
async def receive_webhook(
    provider: str,
    request: Request,
    x_teroxx_signature: Optional[str] = Header(default=None, alias="X-Teroxx-Signature"),
):
    """Generic CRM webhook receiver.

    Validates an HMAC-SHA256 over the raw body using a per-provider
    shared secret from `WEBHOOK_SECRETS`. Currently logs the event to
    `advisor_actions` and returns 202; downstream processing
    (auto-create clients, sync field changes, etc.) lives behind the
    actual integration that will be built later.
    """
    body = await request.body()
    if not _verify_signature(provider, body, x_teroxx_signature):
        raise HTTPException(status_code=401, detail="invalid_signature")
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_json")
    with SessionLocal() as db:
        log_action(
            db, actor_email=f"webhook:{provider}", action_type="webhook_received",
            client_id=None,
            payload={"provider": provider, "event": payload.get("event"), "size": len(body)},
        )
        db.commit()
    return JSONResponse({"ok": True, "received_bytes": len(body)}, status_code=202)
