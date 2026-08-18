import os
import smtplib
from email.message import EmailMessage


def send_change_summary(recipient: str, subject: str, body: str) -> None:
    """Send a change‑summary email using SMTP."""
    print("Reading environment variables...")
    host = os.getenv("OUTLOOK_SMTP_HOST") or os.getenv("SMTP_HOST")
    port = int(os.getenv("OUTLOOK_SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    user = os.getenv("OUTLOOK_SMTP_USER") or os.getenv("SMTP_USER")
    password = os.getenv("OUTLOOK_SMTP_PASSWORD") or os.getenv("SMTP_PASSWORD")

    print(f"SMTP Configuration: Host={host}, Port={port}, User={user}")

    if not all([host, user, password]):
        raise RuntimeError("SMTP configuration missing in environment variables")

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    print("Connecting to SMTP server...")
    with smtplib.SMTP(host, port) as server:
        print("Starting TLS...")
        server.starttls()
        print("Logging in...")
        server.login(user, password)
        print("Sending message...")
        server.send_message(msg)
    print("Email sent successfully!")


if __name__ == "__main__":
    recipient = "gates.focus@gmail.com"
    subject = "Change‑summary"
    body = "Summary of recent changes..."
    print(f"Sending email...{recipient} {subject} {body}")
    send_change_summary(recipient, subject, body)
    print("Done.")
