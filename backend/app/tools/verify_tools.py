"""Identity check tools (Action Agent). Keys used: DATABASE_URL + Gmail SMTP (via app.notifications)."""
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app import verification
from app.db.database import SessionLocal
from app.db.models import Order
from app.notifications import send_verification_code

# Same text whether or not the order exists, so nobody can probe which order numbers are real.
CODE_SENT = ("If that order number is valid, a 6-digit code was sent to the email address on the order. "
             "Ask the customer to type the code here. It is valid for 10 minutes. "
             "If it does not arrive, they should wait a few minutes and check spam.")


@tool
def request_verification(order_id: int, config: RunnableConfig) -> str:
    """Start the identity check: email a 6-digit code to the address on file for this order.
    Needed before any order action. Never reveal the email address or any order detail."""
    thread_id = verification.thread_id_of(config)
    if not thread_id:
        return "VERIFICATION_UNAVAILABLE: this chat cannot be verified right now."
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        if not order:
            return CODE_SENT
        email = order.customer.email
        code, status = verification.issue_code(thread_id, order.customer_id, order_id)
    finally:
        db.close()

    if code is None:
        return CODE_SENT  # rate limited or locked: no mail, but the same answer
    if not send_verification_code(email, code, order_id):
        verification.cancel(thread_id)
        return ("VERIFICATION_UNAVAILABLE: the code could not be sent right now. Ask the customer to try again "
                "later or contact support@shopease.example.")
    return CODE_SENT


@tool
def confirm_verification(code: str, config: RunnableConfig) -> str:
    """Check the 6-digit code the customer typed in the chat. Call it only with a code the customer sent.
    Never guess a code."""
    thread_id = verification.thread_id_of(config)
    if not thread_id:
        return "VERIFICATION_UNAVAILABLE: this chat cannot be verified right now."
    status, left = verification.check(thread_id, code)
    if status == "ok":
        return ("VERIFIED: the customer proved ownership. For the next 30 minutes the order tools work for "
                "this customer's own orders.")
    if status == "wrong":
        return f"WRONG_CODE: that code is not correct. {left} attempts left for this code."
    if status == "too_many":
        return "TOO_MANY_ATTEMPTS: that code is now cancelled. A new code can be requested with request_verification."
    if status == "locked":
        return "TEMPORARILY_LOCKED: too many wrong codes. Ask the customer to try again later."
    return ("NO_ACTIVE_CODE: there is no valid code (it may have expired). Ask for the order number and call "
            "request_verification again.")
