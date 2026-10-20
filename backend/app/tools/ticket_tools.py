"""Escalation / ticket tools. Key used: DATABASE_URL (+ Gmail SMTP through app.notifications)."""
import re
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import func

from app import verification
from app.db.database import SessionLocal
from app.db.models import Customer, Order, Ticket
from app.notifications import notify_support_team

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@tool
def escalate_to_human(reason: str, summary: str, config: RunnableConfig, order_id: Optional[int] = None,
                      contact_email: Optional[str] = None) -> str:
    """Escalate the case to a human agent by creating a ticket.
    reason = short label (e.g. 'Refund above limit'); summary = full context: what the customer wants,
    what was already tried, order details. Pass order_id when an order number is known: it is linked
    only if the customer is verified for that order.
    contact_email = the customer's own email; REQUIRED when the customer is not verified for an order.
    If the result says NEED_CONTACT_EMAIL, ask the customer for their email (no ticket exists yet)."""
    db = SessionLocal()
    try:
        customer = None
        verified_id = verification.verified_customer_id(config)
        if order_id is not None and verified_id is not None:
            order = db.get(Order, order_id)
            if order and order.customer_id == verified_id:
                customer = order.customer
        if not customer:
            order_id = None  # an unverified person must not attach a ticket to somebody's order

        if customer:
            email = customer.email  # trusted: comes from our own records
        else:
            email = (contact_email or "").strip()
            if not EMAIL_RE.match(email):
                return ("NEED_CONTACT_EMAIL: there is no verified order and no valid email address. "
                        "Ask the customer for their email so a human agent can reach them. No ticket was created.")
            customer = db.query(Customer).filter(func.lower(Customer.email) == email.lower()).first()

        ticket = Ticket(customer_id=customer.id if customer else None, order_id=order_id,
                        contact_email=email, reason=reason, summary=summary)
        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        notify_support_team(ticket.id, reason, summary, order_id,
                            customer.name if customer else None, email)
        return (f"Ticket #{ticket.id} created and forwarded to a human agent "
                "(reply within 24 hours).")
    finally:
        db.close()


@tool
def check_ticket_status(ticket_id: int, email: str) -> str:
    """Check the status of a support ticket. Needs BOTH the ticket number and the email address the
    customer gave for that ticket. Never reveal anything if they do not match."""
    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if (not ticket or not ticket.contact_email
                or ticket.contact_email.strip().lower() != email.strip().lower()):
            return "No ticket found with that number and email."
        note = ticket.resolution_note or "none yet"
        return f"Ticket #{ticket.id}: {ticket.reason}, status: {ticket.status}, message from support: {note}"
    finally:
        db.close()
