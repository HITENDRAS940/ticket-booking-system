from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import customer_only
from app.db.session import get_db
from app.models import Booking, BookingSeat, Event, Seat, SeatHoldItem, ShowSeat, User, Venue
from app.schemas import ConfirmBooking, HoldCreate
from app.services.booking_service import (
    booking_email_context, cancel_booking, cancel_hold, confirm_hold, create_hold, offer_email_context,
)
from app.services.mail_service import send_booking_email, send_waitlist_offer_email
from app.services.seat_service import get_owned_hold
from app.websocket.manager import manager

router = APIRouter(tags=["holds", "bookings"])


def booking_payload(db: Session, booking: Booking):
    event = db.get(Event, booking.event_id)
    venue = db.get(Venue, event.venue_id)
    seats = db.execute(select(BookingSeat, ShowSeat, Seat).join(ShowSeat, ShowSeat.id == BookingSeat.show_seat_id).join(Seat, Seat.id == ShowSeat.seat_id).where(BookingSeat.booking_id == booking.id).order_by(Seat.row_label, Seat.seat_number)).all()
    return {
        "id": booking.id, "booking_reference": booking.booking_reference, "event_id": event.id,
        "event_title": event.title, "venue_name": venue.name, "show_date": event.show_date, "show_time": event.show_time,
        "total_amount": booking.total_amount, "status": booking.status, "qr_code_path": booking.qr_code_path,
        "created_at": booking.created_at, "cancelled_at": booking.cancelled_at,
        "seats": [{"show_seat_id": ss.id, "label": f"{seat.row_label}{seat.seat_number}", "price": bs.price} for bs, ss, seat in seats],
    }


@router.post("/api/events/{event_id}/holds", status_code=201)
async def hold(event_id: int, payload: HoldCreate, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    value = create_hold(db, event_id, user.id, payload.show_seat_ids)
    await manager.broadcast(event_id, "held", payload.show_seat_ids)
    return {"id": value.id, "event_id": event_id, "expires_at": value.expires_at, "status": value.status, "show_seat_ids": payload.show_seat_ids}


@router.get("/api/holds/{hold_id}")
def get_hold(hold_id: int, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    value = get_owned_hold(db, hold_id, user.id)
    ids = db.scalars(select(SeatHoldItem.show_seat_id).where(SeatHoldItem.hold_id == hold_id)).all()
    return {"id": value.id, "event_id": value.event_id, "expires_at": value.expires_at, "status": value.status, "show_seat_ids": ids}


@router.delete("/api/holds/{hold_id}")
async def release_hold(hold_id: int, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    event_id, ids = cancel_hold(db, hold_id, user.id)
    await manager.broadcast(event_id, "released", ids)
    return {"message": "Hold released"}


@router.post("/api/bookings/confirm", status_code=201)
async def confirm(payload: ConfirmBooking, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    booking, ids = confirm_hold(db, payload.hold_id, user.id)
    email_user, event, venue, labels = booking_email_context(db, booking)
    await send_booking_email(db, user=email_user, event=event, venue=venue, booking=booking, seats=labels)
    await manager.broadcast(booking.event_id, "booked", ids)
    return booking_payload(db, booking)


@router.get("/api/bookings/my")
def my_bookings(db: Session = Depends(get_db), user: User = Depends(customer_only)):
    bookings = db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())).all()
    return [booking_payload(db, b) for b in bookings]


@router.get("/api/bookings/{booking_id}")
def get_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    return booking_payload(db, booking)


@router.post("/api/bookings/{booking_id}/cancel")
async def cancel(booking_id: int, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    booking, ids, offers = cancel_booking(db, booking_id, user.id)
    for offer in offers:
        recipient, event, category = offer_email_context(db, offer)
        await send_waitlist_offer_email(db, user=recipient, event=event, category=category, offer=offer)
    await manager.broadcast(booking.event_id, "cancelled", ids)
    return booking_payload(db, booking)

