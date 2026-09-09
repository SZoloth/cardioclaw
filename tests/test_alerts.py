from cardioclaw.alerts import send_alert
from cardioclaw.config import Settings


def test_alert_is_noop_without_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        "cardioclaw.alerts.smtplib.SMTP_SSL",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("SMTP should not open")),
    )

    send_alert(Settings(_env_file=None), "Subject", "Body")


def test_alert_logs_in_and_sends_message(monkeypatch) -> None:
    events = []

    class FakeSMTP:
        def __init__(self, host, port):
            events.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def login(self, username, password):
            events.append(("login", username, password))

        def send_message(self, message):
            events.append(("send", message["Subject"], message.get_content().strip()))

    monkeypatch.setattr("cardioclaw.alerts.smtplib.SMTP_SSL", FakeSMTP)
    settings = Settings(
        _env_file=None,
        alert_email_to="listener@example.test",
        alert_email_from="operator@example.test",
        alert_email_password="secret",
    )

    send_alert(settings, "Published", "Release complete")

    assert events[0] == ("connect", "smtp.gmail.com", 465)
    assert events[1] == ("login", "operator@example.test", "secret")
    assert events[2] == ("send", "[Cardiology Claw] Published", "Release complete")
