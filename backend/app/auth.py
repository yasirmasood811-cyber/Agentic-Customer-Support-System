"""Admin login. Key used: ADMIN_PASSWORD (from .env).
Tokens live in memory, so restarting the server logs everyone out."""
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException

from app.config import settings

TOKEN_TTL = 8 * 3600        # seconds a login stays valid
MAX_FAILED = 5              # wrong passwords allowed ...
WINDOW = 300                # ... per 5 minutes per IP

_tokens: dict[str, float] = {}
_failed: dict[str, deque] = defaultdict(deque)


def _require_configured():
    if not settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Admin password is not configured on the server (ADMIN_PASSWORD in .env).")


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def login(password: str, ip: str) -> str:
    _require_configured()
    now = time.time()
    attempts = _failed[ip]
    while attempts and now - attempts[0] > WINDOW:
        attempts.popleft()
    if len(attempts) >= MAX_FAILED:
        raise HTTPException(status_code=429, detail="Too many wrong attempts. Try again in a few minutes.")

    if not hmac.compare_digest(password.encode(), settings.ADMIN_PASSWORD.encode()):
        attempts.append(now)
        raise HTTPException(status_code=401, detail="Wrong password.")

    attempts.clear()
    for t in [t for t, exp in _tokens.items() if exp < now]:  # drop expired tokens
        del _tokens[t]
    token = secrets.token_urlsafe(32)
    _tokens[token] = now + TOKEN_TTL
    return token


def logout(token: Optional[str]) -> None:
    if token:
        _tokens.pop(token, None)


def require_admin(authorization: Optional[str] = Header(default=None)) -> None:
    """FastAPI dependency: protects admin endpoints."""
    _require_configured()
    token = bearer_token(authorization)
    expires = _tokens.get(token) if token else None
    if not expires or expires < time.time():
        raise HTTPException(status_code=401, detail="Please log in as admin.")
