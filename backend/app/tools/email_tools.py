"""Email: Gmail SMTP. Keys used: SMTP_EMAIL, SMTP_APP_PASSWORD.
deliver_email() is the plain function; send_email is the tool the Email Agent calls."""
import smtplib
from email.message import EmailMessage
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app import verification
from app.config import settings


def deliver_email(to: str, subject: str, body: str, reply_to: Optional[str] = None) -> str:
    """Sends one email. Returns a result string and never raises."""
    if not (settings.SMTP_EMAIL and settings.SMTP_APP_PASSWORD):
        return "Email failed: SMTP credentials are not configured."
    subject = " ".join(subject.split())  # no line breaks inside a header
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


@tool
def send_email(to: str, subject: str, body: str, config: RunnableConfig) -> str:
    """Send an email to the verified customer (for example a refund or order confirmation).
    The recipient must be the verified customer's own email address."""
    allowed = verification.verified_email(config)
    if not allowed or to.strip().lower() != allowed.strip().lower():
        return "Email not sent: the recipient must be the verified customer's own email address."
    return deliver_email(to, subject, body)
