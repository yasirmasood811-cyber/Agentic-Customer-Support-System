"""Emails about tickets. Keys used: Gmail SMTP (SMTP_EMAIL, SMTP_APP_PASSWORD) and SUPPORT_TEAM_EMAIL.
Every function logs problems instead of raising, so a mail failure never breaks a ticket."""
import logging
from typing import Optional

from app.config import settings
from app.tools.email_tools import deliver_email

log = logging.getLogger(__name__)

STATUS_LABEL = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved"}


def notify_support_team(ticket_id: int, reason: str, summary: str, order_id: Optional[int],
                        customer_name: Optional[str], contact_email: Optional[str]) -> None:
    """New ticket -> email to the support team (skipped if SUPPORT_TEAM_EMAIL is empty)."""
    if not settings.SUPPORT_TEAM_EMAIL:
        return
    body = (
        f"A new support ticket needs a human agent.\n\n"
        f"Ticket:   #{ticket_id}\n"
        f"Reason:   {reason}\n"
        f"Customer: {customer_name or 'unknown'} <{contact_email or 'no email'}>\n"
        f"Order:    {('#' + str(order_id)) if order_id else '-'}\n\n"
        f"Summary from the AI assistant:\n{summary}\n\n"
        f"Open the Admin page of the support app to handle this ticket."
    )
    result = deliver_email(settings.SUPPORT_TEAM_EMAIL, f"[ShopEase] New ticket #{ticket_id}: {reason}", body)
    if not result.startswith("Email sent"):
        log.warning("Support team notification failed for ticket #%s: %s", ticket_id, result)


def notify_customer_ticket_update(ticket_id: int, reason: str, status: str, note: Optional[str],
                                  to_email: Optional[str], customer_name: Optional[str]) -> str:
    """Ticket updated by an admin -> email to the customer. Returns 'sent to ...', 'skipped: ...' or 'failed: ...'."""
    if not to_email:
        return "skipped: this ticket has no contact email"
    label = STATUS_LABEL.get(status, status)
    lines = [
        f"Hello {customer_name or 'Customer'},",
        "",
        f"Your support ticket #{ticket_id} (\"{reason}\") has been updated.",
        f"Current status: {label}",
    ]
    if note:
        lines += ["", "Message from our support team:", note]
    lines += [
        "",
        f"You can also ask our chat assistant for the latest status using your ticket number #{ticket_id} and this email address.",
        "",
        "Regards,",
        "ShopEase Customer Support",
    ]
    result = deliver_email(to_email, f"[ShopEase] Update on your ticket #{ticket_id}: {label}",
                           "\n".join(lines), reply_to=settings.SUPPORT_TEAM_EMAIL or None)
    if result.startswith("Email sent"):
        return f"sent to {to_email}"
    log.warning("Customer notification failed for ticket #%s: %s", ticket_id, result)
    return f"failed: {result}"


def send_verification_code(to_email: str, code: str, order_id: int) -> bool:
    """Emails the 6-digit identity code. The code is never logged."""
    body = (
        f"Your ShopEase verification code is: {code}\n\n"
        f"Type it in the chat to continue with order #{order_id}. It is valid for 10 minutes.\n\n"
        "If you did not ask for this code, ignore this email. Nobody can see or change your order without it."
    )
    result = deliver_email(to_email, "[ShopEase] Your verification code", body)
    if not result.startswith("Email sent"):
        log.warning("Verification email could not be sent: %s", result)
        return False
    return True
