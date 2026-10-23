"""Email. Brevo API if BREVO_API_KEY is set (works on free hosts), otherwise Gmail SMTP.
Keys used: BREVO_API_KEY + EMAIL_SENDER, or SMTP_EMAIL + SMTP_APP_PASSWORD.
deliver_email() is the plain function; send_email is the tool the Email Agent calls."""
import smtplib
from email.message import EmailMessage
from typing import Optional

import requests
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app import verification
from app.config import settings

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _send_with_brevo(to: str, subject: str, body: str, reply_to: Optional[str]) -> str:
    sender = settings.EMAIL_SENDER or settings.SMTP_EMAIL
    if not sender:
        return "Email failed: EMAIL_SENDER (an address verified in Brevo) is not configured."
    payload = {
        "sender": {"name": "ShopEase Support", "email": sender},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}
    try:
        response = requests.post(
            BREVO_URL, json=payload, timeout=20,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
        )
    except Exception as e:
        return f"Email failed: {e}"
    if response.status_code in (200, 201, 202):
        return f"Email sent to {to} with subject '{subject}'."
    try:
        detail = response.json().get("message") or response.text
    except Exception:
        detail = response.text
    return f"Email failed: Brevo answered {response.status_code}: {str(detail)[:200]}"


def _send_with_smtp(to: str, subject: str, body: str, reply_to: Optional[str]) -> str:
    if not (settings.SMTP_EMAIL and settings.SMTP_APP_PASSWORD):
        return "Email failed: SMTP credentials are not configured."
    msg = EmailMessage()
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_APP_PASSWORD)
            server.send_message(msg)
        return f"Email sent to {to} with subject '{subject}'."
    except Exception as e:
        return f"Email failed: {e}"


def deliver_email(to: str, subject: str, body: str, reply_to: Optional[str] = None) -> str:
    """Sends one email. Returns a result string and never raises."""
    subject = " ".join(subject.split())  # no line breaks inside a header
    if settings.BREVO_API_KEY:
        return _send_with_brevo(to, subject, body, reply_to)
    return _send_with_smtp(to, subject, body, reply_to)


@tool
def send_email(to: str, subject: str, body: str, config: RunnableConfig) -> str:
    """Send an email to the verified customer (for example a refund or order confirmation).
    The recipient must be the verified customer's own email address."""
    allowed = verification.verified_email(config)
    if not allowed or to.strip().lower() != allowed.strip().lower():
        return "Email not sent: the recipient must be the verified customer's own email address."
    return deliver_email(to, subject, body)
