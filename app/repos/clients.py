"""Repository layer for clients and their lots.

Centralises every CRUD operation + the matching `advisor_actions` log
write, so endpoints can call thin helpers and we don't drift on the audit
trail. Also exposes `to_legacy_dict()` which converts an ORM `Client` into
the dict shape that the existing `compute_client_portfolio_pnl()` and
`compute_client_portfolio_history()` functions in `app/engine.py` expect.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from app.db import AdvisorAction, Client, ClientLot, log_action


# ── Conversion helpers ───────────────────────────────────────────────


def to_legacy_dict(client: Client) -> dict:
    """Mirror the shape of `DEMO_CLIENTS[*]` so engine code stays unchanged."""
    return {
        "id": client.id,
        "name": client.name,
        "profile": client.profile,
        "domicile": client.domicile or "",
        "domicile_country": client.domicile_country,
        "tagline": client.tagline or "",
        "inception_date": client.inception_date or "",
        "currency": client.currency or "USD",
        "starting_capital_usd": client.starting_capital_usd or 0,
        "risk_notes": client.risk_notes or "",
        "implementation_note": client.implementation_note or "",
        "positions": [
            {
                "ticker": lot.ticker,
                "quantity": float(lot.quantity or 0),
                "entry_price": float(lot.entry_price or 0),
                "entry_date": lot.entry_date or "",
                "notes": lot.notes or "",
            }
            for lot in client.lots
        ],
    }


def to_summary_dict(client: Client) -> dict:
    """Lightweight payload for client pickers."""
    return {
        "id": client.id,
        "name": client.name,
        "profile": client.profile,
        "tagline": client.tagline or "",
        "domicile": client.domicile or "",
    }


# ── Queries ──────────────────────────────────────────────────────────


def list_active_clients(db: Session) -> list[Client]:
    stmt = (
        select(Client)
        .where(Client.deleted_at.is_(None))
        .options(selectinload(Client.lots))
        .order_by(Client.name)
    )
    return list(db.execute(stmt).scalars().all())


def get_client(db: Session, client_id: str) -> Optional[Client]:
    stmt = (
        select(Client)
        .where(Client.id == client_id, Client.deleted_at.is_(None))
        .options(selectinload(Client.lots))
    )
    return db.execute(stmt).scalar_one_or_none()


# ── Mutations (each writes an advisor_action row) ────────────────────


def _slugify(name: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
    return base or "client"


def create_client(
    db: Session,
    *,
    actor_email: Optional[str],
    name: str,
    profile: str = "Balanced",
    domicile: Optional[str] = None,
    domicile_country: Optional[str] = None,
    currency: str = "USD",
    inception_date: Optional[str] = None,
    starting_capital_usd: Optional[float] = None,
    tagline: Optional[str] = None,
    risk_notes: Optional[str] = None,
) -> Client:
    # Generate a stable-ish id from the name + count suffix to avoid collisions.
    base = _slugify(name)
    suffix = 0
    candidate = base
    while db.get(Client, candidate) is not None:
        suffix += 1
        candidate = f"{base}_{suffix}"
    client = Client(
        id=candidate,
        name=name.strip(),
        profile=profile,
        domicile=domicile,
        domicile_country=domicile_country,
        currency=currency,
        inception_date=inception_date,
        starting_capital_usd=starting_capital_usd,
        tagline=tagline,
        risk_notes=risk_notes,
        created_by=actor_email,
    )
    db.add(client)
    log_action(db, actor_email=actor_email, action_type="client_created",
               client_id=client.id, payload={"name": name, "profile": profile})
    db.flush()  # populate id without committing
    return client


def update_client(
    db: Session,
    *,
    actor_email: Optional[str],
    client: Client,
    fields: dict,
) -> Client:
    allowed = {
        "name", "profile", "domicile", "domicile_country", "currency",
        "inception_date", "starting_capital_usd", "tagline", "risk_notes",
        "implementation_note",
    }
    changed: dict[str, object] = {}
    for k, v in fields.items():
        if k in allowed and getattr(client, k) != v:
            setattr(client, k, v)
            changed[k] = v
    if changed:
        log_action(db, actor_email=actor_email, action_type="client_updated",
                   client_id=client.id, payload=changed)
    return client


def soft_delete_client(db: Session, *, actor_email: Optional[str], client: Client) -> None:
    client.deleted_at = datetime.now(timezone.utc)
    log_action(db, actor_email=actor_email, action_type="client_deleted",
               client_id=client.id, payload=None)


def add_lot(
    db: Session,
    *,
    actor_email: Optional[str],
    client: Client,
    ticker: str,
    quantity: float,
    entry_price: float,
    entry_date: Optional[str] = None,
    notes: Optional[str] = None,
) -> ClientLot:
    lot = ClientLot(
        client_id=client.id,
        ticker=ticker.upper().strip(),
        quantity=float(quantity),
        entry_price=float(entry_price),
        entry_date=entry_date,
        notes=notes,
        created_by=actor_email,
    )
    db.add(lot)
    log_action(db, actor_email=actor_email, action_type="lot_added",
               client_id=client.id,
               payload={"ticker": lot.ticker, "quantity": lot.quantity, "entry_price": lot.entry_price})
    db.flush()
    return lot


def update_lot(
    db: Session,
    *,
    actor_email: Optional[str],
    lot: ClientLot,
    fields: dict,
) -> ClientLot:
    allowed = {"ticker", "quantity", "entry_price", "entry_date", "notes"}
    changed: dict[str, object] = {}
    for k, v in fields.items():
        if k in allowed and getattr(lot, k) != v:
            if k == "ticker" and isinstance(v, str):
                v = v.upper().strip()
            setattr(lot, k, v)
            changed[k] = v
    if changed:
        log_action(db, actor_email=actor_email, action_type="lot_edited",
                   client_id=lot.client_id, payload={"lot_id": lot.id, **changed})
    return lot


def delete_lot(db: Session, *, actor_email: Optional[str], lot: ClientLot) -> None:
    log_action(db, actor_email=actor_email, action_type="lot_deleted",
               client_id=lot.client_id,
               payload={"lot_id": lot.id, "ticker": lot.ticker})
    db.delete(lot)


def recent_actions(db: Session, *, client_id: Optional[str] = None, limit: int = 10) -> list[AdvisorAction]:
    stmt = select(AdvisorAction).order_by(AdvisorAction.created_at.desc()).limit(limit)
    if client_id:
        stmt = (
            select(AdvisorAction)
            .where(AdvisorAction.client_id == client_id)
            .order_by(AdvisorAction.created_at.desc())
            .limit(limit)
        )
    return list(db.execute(stmt).scalars().all())
