import logging
from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import EmailLog

logger = logging.getLogger(__name__)


async def send_email(db: Session, recipient: str, subject: str, html: str, attachment: str | None = None):
    status, error = "logged", None
    if not settings.smtp_host:
        logger.info("Development email to %s | %s | %s", recipient, subject, html)
    else:
        message = EmailMessage()
        message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content("This ticket email requires an HTML-capable email client.")
        message.add_alternative(html, subtype="html")
        if attachment:
            path = Path(__file__).resolve().parents[1] / attachment.lstrip("/").replace("static/", "static/")
            if path.exists():
                message.add_attachment(path.read_bytes(), maintype="image", subtype="png", filename=path.name)
        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_username,
                password=settings.smtp_password,
                start_tls=settings.smtp_port != 465,
                use_tls=settings.smtp_port == 465,
            )
            status = "sent"
        except Exception as exc:  # email failure must not undo a paid/confirmed booking
            status, error = "failed", str(exc)
            logger.exception("Email delivery failed")
    db.add(EmailLog(recipient_email=recipient, subject=subject, status=status, error_message=error))
    db.commit()


async def send_booking_email(db: Session, *, user, event, venue, booking, seats: list[str]):
    html = f"""
    <h2>Your ticket is confirmed</h2>
    <p>Hello {user.name},</p><p><strong>{event.title}</strong><br>{venue.name}<br>
    {event.show_date} at {event.show_time.strftime('%H:%M')}<br>Seats: {', '.join(seats)}</p>
    <p>Booking reference: <strong>{booking.booking_reference}</strong></p>
    """
    await send_email(db, user.email, f"Ticket confirmed: {event.title}", html, booking.qr_code_path)


async def send_waitlist_offer_email(db: Session, *, user, event, category, offer):
    link = f"{settings.frontend_url}/offers/{offer.token}"
    html = f"""
    <h2>A seat is available</h2><p>Hello {user.name},</p>
    <p>A {category.name} seat for <strong>{event.title}</strong> is reserved for you until {offer.expires_at}.</p>
    <p><a href="{link}">Accept this time-limited offer</a></p>
    """
    await send_email(db, user.email, f"Waitlist offer: {event.title}", html)

