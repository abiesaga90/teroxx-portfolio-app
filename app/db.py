"""Database persistence for clients, lots, and the advisor audit trail.

Design notes:

- SQLAlchemy 2.0 ORM with declarative `Base`. Tables are created on first
  import (`init_db()`); schema changes will move to Alembic post-launch.
- Production: set DATABASE_URL to a Postgres connection string, e.g.
    postgresql://user:password@host:5432/teroxx
  Local dev fallback: SQLite at ./data/teroxx.db (no env var needed).
- Soft-deletes via `deleted_at`. Hard deletes only via direct SQL.
- All mutations should write a row to `advisor_actions`; the repo layer
  centralises this so endpoints don't forget.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
    func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session

logger = logging.getLogger(__name__)


def _build_db_url() -> tuple[str, dict]:
    """Return (url, connect_args) for the configured database.

    Priority:
      1. DATABASE_URL env var  → Postgres (or any SQLAlchemy-compatible URL)
      2. TEROXX_DB_PATH env var → SQLite at that path
      3. ./data/teroxx.db      → SQLite local dev default
      4. /tmp/teroxx.db        → SQLite last-resort fallback
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Heroku/Render sometimes emit postgres:// which SQLAlchemy 2.x rejects
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url, {}

    # SQLite fallback for local development
    env_path = os.getenv("TEROXX_DB_PATH")
    if env_path:
        db_path = Path(env_path)
    else:
        default = Path("data") / "teroxx.db"
        try:
            default.parent.mkdir(parents=True, exist_ok=True)
            probe = default.parent / ".write_probe"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            db_path = default
        except OSError:
            db_path = Path("/tmp/teroxx.db")

    return f"sqlite:///{db_path.as_posix()}", {"check_same_thread": False}


DB_URL, _connect_args = _build_db_url()
DB_PATH = Path(DB_URL.replace("sqlite:///", "")) if DB_URL.startswith("sqlite") else Path("postgres")

engine = create_engine(DB_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    profile: Mapped[str] = mapped_column(String(32), nullable=False, default="Balanced")
    domicile: Mapped[Optional[str]] = mapped_column(String(80))
    domicile_country: Mapped[Optional[str]] = mapped_column(String(8))  # ISO-3166-1 alpha-2
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    inception_date: Mapped[Optional[str]] = mapped_column(String(10))   # YYYY-MM-DD
    starting_capital_usd: Mapped[Optional[float]] = mapped_column(Float)
    tagline: Mapped[Optional[str]] = mapped_column(String(240))
    risk_notes: Mapped[Optional[str]] = mapped_column(Text)
    implementation_note: Mapped[Optional[str]] = mapped_column(Text)
    # Proposal-PDF/DOCX language preference. ISO-639-1 ("en", "de"); falls
    # back to a domicile_country mapping if NULL. See app/pdf/i18n.py.
    proposal_language: Mapped[Optional[str]] = mapped_column(String(8))
    # JSON blob of per-client overrides applied at proposal-render time:
    #   {
    #     "excluded_tickers": ["XRP", "ADA"],
    #     "wishes_md":        "...",  # client preferences / constraints
    #     "summary_md":       "...",  # custom advisor summary
    #     "execution_plan_md":"...",  # phased-build narrative
    #   }
    # Stored as text so we don't bind ourselves to a specific JSON-column
    # dialect; serialised/parsed at the repo boundary.
    proposal_overrides_json: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    lots: Mapped[list["ClientLot"]] = relationship(
        back_populates="client", cascade="all, delete-orphan",
        order_by="ClientLot.entry_date",
    )


class ClientLot(Base):
    __tablename__ = "client_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    entry_date: Mapped[Optional[str]] = mapped_column(String(10))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)

    client: Mapped[Client] = relationship(back_populates="lots")


class ApiToken(Base):
    """Long-lived bearer token for CRM / external integrations.

    Tokens are stored hashed (sha256 + per-token salt); the plaintext
    is only ever returned at creation time. `scopes` is a comma-
    separated list of capabilities ("clients:read", "clients:write",
    "webhooks:receive"), `provider` tags which external system the
    token is meant for ("hubspot", "salesforce", "internal").
    """

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(64))
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    salt: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[str] = mapped_column(String(240), default="clients:read")
    created_by: Mapped[Optional[str]] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Scenario(Base):
    """A saved what-if comparison input prepared by an advisor.

    Phase 8 lets the advisor stage "Conservative on Core" vs
    "Balanced on Expanded" for a specific client ahead of a meeting.
    Only the inputs are persisted; the allocation rollups are
    recomputed on each render so signal changes stay reflected.
    """

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    a_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    a_universe: Mapped[str] = mapped_column(String(64), nullable=False)
    b_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    b_universe: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False)


class AdvisorAction(Base):
    """Every state-changing action made by an advisor is logged here.

    Used by Phase 2 (Workspace activity card), Phase 6 (Activity tab), and
    will back compliance exports. Payload is JSON-encoded for forward-
    compatibility; we don't need to query into it for now.
    """

    __tablename__ = "advisor_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(160), index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, nullable=False, index=True)


def init_db() -> None:
    """Create tables and seed demo clients if the store is empty."""
    Base.metadata.create_all(engine)
    if DB_URL.startswith("sqlite"):
        _ensure_client_columns_sqlite()
    with SessionLocal() as db:
        has_any = db.execute(select(func.count(Client.id))).scalar_one() > 0
        if not has_any:
            _seed_demo(db)
            db.commit()
            logger.info("Seeded demo clients into fresh database")
        else:
            logger.info("Clients table already populated; skipping seed")


def _ensure_client_columns_sqlite() -> None:
    """Forward-only column migration for existing SQLite databases.

    SQLAlchemy's create_all does not ALTER existing tables. On Postgres this
    is handled by running migrations; on SQLite (local dev / legacy) we patch
    in missing columns manually. Not needed on fresh databases since create_all
    produces the full schema from the model definitions.
    """
    required = {
        "proposal_language": "VARCHAR(8)",
        "proposal_overrides_json": "TEXT",
    }
    try:
        with engine.begin() as conn:
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(clients)")}
            for col_name, col_type in required.items():
                if col_name in existing:
                    continue
                conn.exec_driver_sql(f"ALTER TABLE clients ADD COLUMN {col_name} {col_type}")
                logger.info("Added missing column clients.%s", col_name)
    except Exception as e:
        logger.warning("Client-column migration failed (non-fatal): %s", e)


def _seed_demo(db: Session) -> None:
    """Bootstrap the four demo clients from app/demo_clients.py."""
    try:
        from app.demo_clients import DEMO_CLIENTS
    except Exception as e:  # pragma: no cover
        logger.warning("Could not import demo clients for seeding: %s", e)
        return
    for cid, c in DEMO_CLIENTS.items():
        domicile = c.get("domicile") or ""
        country = None
        if "," in domicile:
            country = domicile.rsplit(",", 1)[-1].strip()
            if len(country) > 2:
                # heuristic mapping for the demo set; production uses ISO-2.
                country = {"DE": "DE", "AE": "AE"}.get(country, country[:2].upper())
        client = Client(
            id=cid,
            name=c["name"],
            profile=c.get("profile", "Balanced"),
            domicile=c.get("domicile"),
            domicile_country=country,
            currency=c.get("currency", "USD"),
            inception_date=c.get("inception_date"),
            starting_capital_usd=c.get("starting_capital_usd"),
            tagline=c.get("tagline"),
            created_by="seed",
        )
        for pos in c.get("positions", []) or []:
            client.lots.append(ClientLot(
                ticker=pos.get("ticker", ""),
                quantity=float(pos.get("quantity", 0) or 0),
                entry_price=float(pos.get("entry_price", 0) or 0),
                entry_date=pos.get("entry_date"),
                notes=pos.get("notes"),
                created_by="seed",
            ))
        db.add(client)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a Session, ensuring close on teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_action(
    db: Session,
    *,
    actor_email: Optional[str],
    action_type: str,
    client_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> AdvisorAction:
    row = AdvisorAction(
        client_id=client_id,
        actor_email=actor_email,
        action_type=action_type,
        payload_json=json.dumps(payload, default=str) if payload else None,
    )
    db.add(row)
    return row
