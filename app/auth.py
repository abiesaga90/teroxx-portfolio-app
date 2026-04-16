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
    "leonardo.larieira@teroxx.com": {
        "name": "Leonardo Larieira",
        "password_hash": "a42b73188fb85e19e59e581a2d6419e6:7c032627befa28a8961a8e143e9a5530c87e859c8e2f1ec47c4a794b9209f68b",
    },
    "aleksander.biesaga@teroxx.com": {
        "name": "Aleksander Biesaga",
        "password_hash": "1517ba6d225fda811e2d05800c73beae:6fb03efcd764b4b4c293f6824ee0176ecb70cf609ab77bcb0333651d0f2fe8fb",
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
