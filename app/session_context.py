"""Session-scoped context shared across every request.

One object carries the advisor's working context (which mode, which client,
which universe/profile/portfolio_value, which "as-of" moment) so any tab can
read or update it without re-deriving from a patchwork of localStorage /
sessionStorage / URL params.

Persistence: serialised into the existing Starlette session under the key
``ctx`` so it survives across requests within a 7-day session window.

Phase 0 keeps the surface tiny: the model itself, a FastAPI dependency to
load it, and a helper to persist mutations. Subsequent phases (1, 2) add
client_id wiring, the workspace landing, and audit logging on context
changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Request
from pydantic import BaseModel, Field


Mode = Literal["advisor", "research", "client_view"]


class SessionContext(BaseModel):
    """The single source of truth for "who is doing what, where, with which assumptions"."""

    user_email: Optional[str] = None
    # None on the very first visit so the UI can show the institutional
    # landing card. The first explicit mode pick by the advisor persists.
    mode: Optional[Mode] = None
    client_id: Optional[str] = None
    universe: str = "Teroxx Core (9)"
    profile: str = "Balanced"
    portfolio_value: float = 100_000.0
    # ISO-8601 UTC. When None, downstream code substitutes "now". Phase 8
    # will let advisors pin this for what-if scenarios.
    as_of: Optional[str] = None

    def touch(self) -> "SessionContext":
        """Refresh as_of to current UTC; chainable."""
        self.as_of = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return self


def load_context(request: Request) -> SessionContext:
    """FastAPI dependency. Pulls the context from session storage.

    Falls back to defaults seeded from the advisor's previously saved
    preferences so a fresh session lands on a sensible state. Always
    refreshes `as_of` so any tab using the context sees a current stamp.
    """
    raw = request.session.get("ctx") or {}
    if not isinstance(raw, dict):
        raw = {}

    # Carry forward legacy `prefs` keys if present (profile/universe/mode/portfolio_value).
    prefs = request.session.get("prefs") or {}
    for key in ("profile", "universe", "portfolio_value"):
        if key not in raw and key in prefs:
            raw[key] = prefs[key]

    # Always keep the logged-in advisor email aligned with the auth session.
    if "user_email" not in raw or raw.get("user_email") != request.session.get("user_email"):
        raw["user_email"] = request.session.get("user_email")

    ctx = SessionContext(**raw)
    ctx.touch()
    request.session["ctx"] = ctx.model_dump()
    return ctx


def save_context(request: Request, ctx: SessionContext) -> SessionContext:
    """Persist a (possibly mutated) context back to the session."""
    ctx.touch()
    request.session["ctx"] = ctx.model_dump()
    return ctx


def patch_context(request: Request, **updates) -> SessionContext:
    """Convenience: load, apply field updates, save."""
    ctx = load_context(request)
    known = set(SessionContext.model_fields.keys())
    for key, value in updates.items():
        if key in known and value is not None:
            setattr(ctx, key, value)
    return save_context(request, ctx)
