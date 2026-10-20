"""Action Agent tools: order status, refund (Stripe test mode), record update.
Keys used: DATABASE_URL, STRIPE_SECRET_KEY (refund only)."""
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app import payments, verification
from app.db.database import SessionLocal
from app.db.models import Order

REFUND_LIMIT = 200.0  # USD. Above this a human must approve (matches refund_policy.txt)
REFUNDABLE_STATUSES = ("delivered", "cancelled")

VERIFICATION_REQUIRED = (
    "VERIFICATION_REQUIRED: the customer is not verified yet. Ask for the order number, call "
    "request_verification, then ask for the 6-digit code from their email and call confirm_verification.")


def _own_order(db, order_id: int, config):
    """Returns (order, error). The order is returned only when this conversation is verified for the
    customer who owns it. Other people's orders look exactly like orders that do not exist."""
    customer_id = verification.verified_customer_id(config)
    if customer_id is None:
        return None, VERIFICATION_REQUIRED
    order = db.get(Order, order_id)
    if not order or order.customer_id != customer_id:
        return None, f"No order found with number {order_id}."
    return order, None


@tool
def get_order_status(order_id: int, config: RunnableConfig) -> str:
    """Get the status, item, amount, ETA and refund state of an order by its order number.
    Works only after the customer is verified (and only for their own orders)."""
    db = SessionLocal()
    try:
        order, error = _own_order(db, order_id, config)
        if error:
            return error
        refund = f"Refunded (ref: {order.refund_reference})" if order.refunded else "Not refunded"
        return (f"Order {order.id}: {order.item}, amount ${order.amount:.2f}, "
                f"status: {order.status}, ETA: {order.eta}, "
                f"ship to: {order.shipping_address}, refund: {refund}, "
                f"customer: {order.customer.name} <{order.customer.email}>")
    finally:
        db.close()


@tool
def process_refund(order_id: int, amount: float, config: RunnableConfig) -> str:
    """Refund an order (full or partial) via Stripe test mode.
    Only delivered or cancelled orders can be refunded, only once, and only up to 200 USD.
    If the result says REFUND_NEEDS_APPROVAL, do NOT retry: escalate to a human agent."""
    db = SessionLocal()
    try:
        order, error = _own_order(db, order_id, config)
        if error:
            return error
        if order.refunded:
            return f"Order {order_id} was already refunded (ref: {order.refund_reference})."
        if order.status not in REFUNDABLE_STATUSES:
            return (f"Order {order_id} is '{order.status}' and cannot be refunded yet. "
                    "Only delivered or cancelled orders are refundable.")
        if amount <= 0 or amount > order.amount:
            return f"Invalid amount. Refund must be between 0 and the order amount (${order.amount:.2f})."
        if amount > REFUND_LIMIT:
            return (f"REFUND_NEEDS_APPROVAL: ${amount:.2f} is above the ${REFUND_LIMIT:.0f} limit. "
                    "A human agent must approve this refund.")
        payment_id = order.payment_intent_id
        if not payment_id:
            # Seed orders have no payment on record, so in TEST mode we first create a test payment and
            # refund that. Orders made in the admin page keep their own payment id and use the branch above.
            payment_id = payments.create_test_payment(amount, order_id)
        refund_id = payments.refund_payment(payment_id, amount)

        order.refunded = True
        order.refund_reference = refund_id
        if amount >= order.amount - 0.005:  # full refund: the order status says so too
            order.status = "refunded"
        db.commit()
        return f"Refund of ${amount:.2f} for order {order_id} processed. Reference: {refund_id}"
    except Exception as e:  # Stripe/network errors
        db.rollback()
        return f"Refund failed: {e}"
    finally:
        db.close()


@tool
def update_record(order_id: int, field: str, value: str, config: RunnableConfig) -> str:
    """Update a customer detail linked to an order. field must be 'shipping_address'
    (only while the order is 'processing') or 'phone'. Email changes are NOT allowed here.
    Works only for the verified customer's own orders."""
    db = SessionLocal()
    try:
        order, error = _own_order(db, order_id, config)
        if error:
            return error
        if field == "shipping_address":
            if order.status != "processing":
                return (f"Address cannot be changed: order {order_id} is '{order.status}'. "
                        "Only orders in 'processing' status can change address.")
            order.shipping_address = value
        elif field == "phone":
            order.customer.phone = value
        else:
            return "Only 'shipping_address' and 'phone' can be updated by the assistant."
        db.commit()
        return f"Order {order_id}: {field} updated to '{value}'."
    finally:
        db.close()
