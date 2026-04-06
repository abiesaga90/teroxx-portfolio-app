"""Authentication — simple session-based login with salted SHA256 passwords."""
import hashlib
import os
from starlette.requests import Request
from starlette.responses import RedirectResponse

# ── Users (email → {name, password_hash as "salt:hash"}) ──
USERS = {
    "jannick.broering@teroxx.com": {
        "name": "Jannick Broering",
        "password_hash": "bddd2fc909fa210bfa62d3748e918f5e:dfffd955c8d495fc19c093b969a542a4a495a88bfc2e61f0d050b7877d9fade6",
    },
}

SESSION_SECRET = os.environ.get("SESSION_SECRET", "teroxx-dev-secret-change-in-prod")


def verify_password(email: str, password: str) -> bool:
    user = USERS.get(email.lower())
    if not user:
        return False
    salt, stored_hash = user["password_hash"].split(":", 1)
    computed = hashlib.sha256((salt + password).encode()).hexdigest()
    return computed == stored_hash


def get_current_user(request: Request) -> dict:
    email = request.session.get("user_email")
    if not email:
        return None
    user = USERS.get(email)
    if not user:
        return None
    return {"email": email, "name": user["name"]}


def require_auth(request: Request):
    """Returns user dict if authenticated, or RedirectResponse to /login."""
    user = get_current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=302)
    return user
