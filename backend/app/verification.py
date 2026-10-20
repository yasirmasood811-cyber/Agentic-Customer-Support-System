"""Email-code (OTP) identity check. State lives in server memory, per conversation (thread_id).

The LLM never sees a code and never decides who is verified: the order tools ask this module.
A restart clears all codes and sessions (like the conversation memory)."""
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Optional

from app.db.database import SessionLocal
from app.db.models import Customer

CODE_TTL = 600                      # a code is valid for 10 minutes
SESSION_TTL = 1800                  # after verifying, orders stay accessible for 30 minutes
MAX_ATTEMPTS = 5                    # wrong tries per code
SEND_LIMIT, SEND_WINDOW = 3, 900    # codes per customer AND per conversation per 15 minutes
FAIL_LIMIT, FAIL_WINDOW = 10, 3600  # wrong codes per customer per hour, then locked

_lock = threading.Lock()
_pending: dict[str, dict] = {}
_verified: dict[str, dict] = {}
_sends_customer: dict[int, deque] = defaultdict(deque)
_sends_thread: dict[str, deque] = defaultdict(deque)
_fails_customer: dict[int, deque] = defaultdict(deque)


def _now() -> float:
    return time.time()


def thread_id_of(config) -> Optional[str]:
    """The conversation id that LangGraph passes to every tool (None when called without a conversation)."""
    try:
        tid = (config or {}).get("configurable", {}).get("thread_id")
    except AttributeError:
        return None
    return str(tid) if tid else None


def _trim(dq: deque, window: int, now: float) -> None:
    while dq and now - dq[0] > window:
        dq.popleft()


def _cleanup(now: float) -> None:
    for store in (_pending, _verified):
        for tid in [t for t, v in store.items() if v["expires"] < now]:
            del store[tid]


def _digest(salt: str, code: str) -> str:
    return hashlib.sha256((salt + code).encode()).hexdigest()


def issue_code(thread_id: str, customer_id: int, order_id: int) -> tuple[Optional[str], str]:
    """Creates a code for this conversation. Returns (code, 'ok') or (None, 'rate_limited' | 'locked')."""
    now = _now()
    with _lock:
        _cleanup(now)
        fails = _fails_customer[customer_id]
        _trim(fails, FAIL_WINDOW, now)
        if len(fails) >= FAIL_LIMIT:
            return None, "locked"
        by_customer, by_thread = _sends_customer[customer_id], _sends_thread[thread_id]
        _trim(by_customer, SEND_WINDOW, now)
        _trim(by_thread, SEND_WINDOW, now)
        if len(by_customer) >= SEND_LIMIT or len(by_thread) >= SEND_LIMIT:
            return None, "rate_limited"

        code = f"{secrets.randbelow(10 ** 6):06d}"
        salt = secrets.token_hex(8)
        _pending[thread_id] = {"customer_id": customer_id, "order_id": order_id, "salt": salt,
                               "digest": _digest(salt, code), "attempts": 0, "expires": now + CODE_TTL}
        by_customer.append(now)
        by_thread.append(now)
        return code, "ok"


def cancel(thread_id: str) -> None:
    with _lock:
        _pending.pop(thread_id, None)


def check(thread_id: str, code: str) -> tuple[str, int]:
    """Checks a typed code. Returns (status, attempts_left) with status in
    ok | wrong | no_code | too_many | locked."""
    now = _now()
    digits = re.sub(r"\D", "", code or "")
    with _lock:
        _cleanup(now)
        pending = _pending.get(thread_id)
        if not pending:
            return "no_code", 0
        fails = _fails_customer[pending["customer_id"]]
        _trim(fails, FAIL_WINDOW, now)
        if len(fails) >= FAIL_LIMIT:
            del _pending[thread_id]
            return "locked", 0

        if len(digits) == 6 and hmac.compare_digest(_digest(pending["salt"], digits), pending["digest"]):
            del _pending[thread_id]
            _verified[thread_id] = {"customer_id": pending["customer_id"], "expires": now + SESSION_TTL}
            return "ok", MAX_ATTEMPTS

        pending["attempts"] += 1
        fails.append(now)
        left = MAX_ATTEMPTS - pending["attempts"]
        if left <= 0:
            del _pending[thread_id]
            return "too_many", 0
        return "wrong", left


def verified_customer_id(config) -> Optional[int]:
    """The customer this conversation has proven to be, or None."""
    tid = thread_id_of(config)
    if not tid:
        return None
    now = _now()
    with _lock:
        entry = _verified.get(tid)
        if not entry or entry["expires"] < now:
            _verified.pop(tid, None)
            return None
        return entry["customer_id"]


def verified_email(config) -> Optional[str]:
    cid = verified_customer_id(config)
    if cid is None:
        return None
    db = SessionLocal()
    try:
        customer = db.get(Customer, cid)
        return customer.email if customer else None
    finally:
        db.close()


# --- helpers for tests only (no tool or API calls these) ---
def _grant(thread_id: str, customer_id: int) -> None:
    with _lock:
        _verified[thread_id] = {"customer_id": customer_id, "expires": _now() + SESSION_TTL}


def _reset_all() -> None:
    with _lock:
        _pending.clear(); _verified.clear()
        _sends_customer.clear(); _sends_thread.clear(); _fails_customer.clear()
