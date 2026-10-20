"""Stripe TEST-mode helpers. Key used: STRIPE_SECRET_KEY (must be a test key).
Calls give up after 20 seconds so a slow Stripe never freezes the chat or the admin page."""
import concurrent.futures

import stripe

from app.config import settings

TIMEOUT = 20


def _call(fn, *args, **kwargs):
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn, *args, **kwargs).result(timeout=TIMEOUT)
    except concurrent.futures.TimeoutError:
        raise TimeoutError("Stripe did not answer in time")
    finally:
        pool.shutdown(wait=False)


def _ready() -> None:
    key = settings.STRIPE_SECRET_KEY
    if not key:
        raise RuntimeError("Stripe key is not configured.")
    if not key.startswith(("sk_test_", "rk_test_")):
        raise RuntimeError("Only Stripe TEST keys are allowed in this project.")
    stripe.api_key = key


def create_test_payment(amount: float, order_id: int) -> str:
    """Creates and confirms a test payment (test card) and returns its PaymentIntent id."""
    _ready()
    payment = _call(
        stripe.PaymentIntent.create,
        amount=int(round(amount * 100)), currency="usd", payment_method="pm_card_visa", confirm=True,
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        metadata={"order_id": str(order_id)},
    )
    return payment.id


def refund_payment(payment_intent_id: str, amount: float) -> str:
    """Refunds (part of) a payment and returns the refund id."""
    _ready()
    refund = _call(stripe.Refund.create, payment_intent=payment_intent_id, amount=int(round(amount * 100)))
    return refund.id
