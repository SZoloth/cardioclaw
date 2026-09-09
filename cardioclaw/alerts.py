from __future__ import annotations

import smtplib
from email.message import EmailMessage

from cardioclaw.config import Settings


def send_alert(settings: Settings, subject: str, body: str) -> None:
    if not (
        settings.alert_email_to
        and settings.alert_email_from
        and settings.alert_email_password_value
    ):
        return

    message = EmailMessage()
    message["Subject"] = f"[Cardiology Claw] {subject}"
    message["From"] = settings.alert_email_from
    message["To"] = settings.alert_email_to
    message.set_content(body)

    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
        server.login(settings.alert_email_from, settings.alert_email_password_value)
        server.send_message(message)
