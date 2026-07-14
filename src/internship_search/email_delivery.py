"""Send emails through a simple SMTP provider."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Callable

from internship_search.env_loader import get_env, load_env_into_process


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_address: str
    use_tls: bool = True


SendSmtpEmail = Callable[[str, str, str, SmtpConfig], None]


@dataclass(frozen=True)
class EmailDeliveryResult:
    sent: bool
    recipient: str
    error: str = ""


def get_smtp_config() -> SmtpConfig | None:
    load_env_into_process()
    from_address = get_env("EMAIL_FROM")
    password = get_env("EMAIL_SMTP_PASSWORD") or get_env("EMAIL_PASSWORD")
    if not from_address or not password:
        return None

    host = get_env("EMAIL_SMTP_HOST", "smtp.gmail.com") or "smtp.gmail.com"
    port_text = get_env("EMAIL_SMTP_PORT", "587") or "587"
    username = get_env("EMAIL_SMTP_USER", from_address) or from_address
    use_tls = get_env("EMAIL_SMTP_USE_TLS", "true").lower() not in {"0", "false", "no"}

    return SmtpConfig(
        host=host,
        port=int(port_text),
        username=username,
        password=password,
        from_address=from_address,
        use_tls=use_tls,
    )


def deliver_email(
    *,
    subject: str,
    body: str,
    recipient: str,
    config: SmtpConfig | None = None,
    sender: SendSmtpEmail | None = None,
) -> EmailDeliveryResult:
    if not recipient.strip():
        return EmailDeliveryResult(sent=False, recipient=recipient, error="Recipient is not configured.")

    smtp_config = config or get_smtp_config()
    if smtp_config is None:
        return EmailDeliveryResult(
            sent=False,
            recipient=recipient,
            error="Email credentials are not configured. Set EMAIL_FROM and EMAIL_SMTP_PASSWORD in .env.",
        )

    try:
        (sender or send_smtp_email)(subject, body, recipient, smtp_config)
    except Exception as error:  # noqa: BLE001 - return safe CLI-facing delivery errors.
        return EmailDeliveryResult(sent=False, recipient=recipient, error=str(error))

    return EmailDeliveryResult(sent=True, recipient=recipient)


def send_smtp_email(subject: str, body: str, recipient: str, config: SmtpConfig) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.from_address
    message["To"] = recipient
    message.set_content(body)

    if config.use_tls:
        with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(config.username, config.password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(config.host, config.port, timeout=30) as smtp:
        smtp.login(config.username, config.password)
        smtp.send_message(message)


def summarize_email_delivery(result: EmailDeliveryResult) -> str:
    if result.sent:
        return f"Email sent to {result.recipient}"
    if result.error:
        return f"Email not sent: {result.error}"
    return "Email not sent"
