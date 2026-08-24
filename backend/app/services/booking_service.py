import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Booking, BookingSeat, BookingStatus, Event, EventCategoryPrice, HoldStatus, OfferStatus,
    Seat, SeatCategory, SeatHold, SeatHoldItem, SeatStatus, ShowSeat, User, Venue,
    WaitlistEntry, WaitlistOffer, WaitlistStatus,
)
from app.services.qr_service import generate_booking_qr
from app.services.seat_service import expire_stale_holds, get_owned_hold, now_utc


def create_hold(db: Session, event_id: int, user_id: int, show_seat_ids: list[int]) -> SeatHold:
    event = db.get(Event, event_id)
    if not event or event.status.value != "published":
        raise HTTPException(404, "Published event not found")
    expire_stale_holds(db, event_id)
    seats = db.scalars(
        select(ShowSeat).where(ShowSeat.event_id == event_id, ShowSeat.id.in_(show_seat_ids)).order_by(ShowSeat.id).with_for_update()
    ).all()
    if len(seats) != len(show_seat_ids):
        db.rollback()
        raise HTTPException(400, "One or more seats do not belong to this event")
    if any(seat.status != SeatStatus.available for seat in seats):
        db.rollback()
        raise HTTPException(409, "One or more seats are no longer available")
    hold = SeatHold(event_id=event_id, user_id=user_id, expires_at=now_utc() + timedelta(minutes=settings.seat_hold_ttl_minutes))
    db.add(hold)
    db.flush()
    for seat in seats:
        db.add(SeatHoldItem(hold_id=hold.id, show_seat_id=seat.id))
        seat.status, seat.current_hold_id = SeatStatus.held, hold.id
    db.commit()
    db.refresh(hold)
    return hold


def cancel_hold(db: Session, hold_id: int, user_id: int) -> tuple[int, list[int]]:
    hold = get_owned_hold(db, hold_id, user_id, lock=True)
    if hold.status != HoldStatus.active:
        raise HTTPException(409, "Hold is not active")
    ids = db.scalars(select(SeatHoldItem.show_seat_id).where(SeatHoldItem.hold_id == hold.id)).all()
    seats = db.scalars(select(ShowSeat).where(ShowSeat.id.in_(ids)).with_for_update()).all()
    for seat in seats:
        if seat.current_hold_id == hold.id:
            seat.status, seat.current_hold_id = SeatStatus.available, None
    hold.status = HoldStatus.cancelled
    db.commit()
    return hold.event_id, list(ids)


def _price_map(db: Session, event_id: int, show_seats: list[ShowSeat]) -> dict[int, Decimal]:
    category_by_show = dict(db.execute(
        select(ShowSeat.id, Seat.category_id).join(Seat, Seat.id == ShowSeat.seat_id).where(ShowSeat.id.in_([s.id for s in show_seats]))
    ).all())
    prices = dict(db.execute(select(EventCategoryPrice.category_id, EventCategoryPrice.price).where(EventCategoryPrice.event_id == event_id)).all())
    try:
        return {sid: prices[category] for sid, category in category_by_show.items()}
    except KeyError as exc:
        raise HTTPException(409, "A selected seat category has no event price") from exc


def confirm_hold(db: Session, hold_id: int, user_id: int) -> tuple[Booking, list[int]]:
    hold = get_owned_hold(db, hold_id, user_id, lock=True)
    if hold.status != HoldStatus.active or hold.expires_at <= now_utc():
        if hold.status == HoldStatus.active:
            expire_stale_holds(db, hold.event_id)
            db.commit()
        raise HTTPException(409, "Hold has expired or is no longer active")
    ids = db.scalars(select(SeatHoldItem.show_seat_id).where(SeatHoldItem.hold_id == hold.id)).all()
    seats = db.scalars(select(ShowSeat).where(ShowSeat.id.in_(ids)).order_by(ShowSeat.id).with_for_update()).all()
    if len(seats) != len(ids) or any(s.status != SeatStatus.held or s.current_hold_id != hold.id for s in seats):
        db.rollback()
        raise HTTPException(409, "Held seats are no longer valid")
    price_map = _price_map(db, hold.event_id, seats)
    booking = Booking(
        booking_reference=f"TKT-{secrets.token_hex(5).upper()}", event_id=hold.event_id,
        user_id=user_id, total_amount=sum(price_map.values(), Decimal("0.00")),
    )
    db.add(booking)
    db.flush()
    for seat in seats:
        db.add(BookingSeat(booking_id=booking.id, show_seat_id=seat.id, price=price_map[seat.id]))
        seat.status, seat.current_booking_id, seat.current_hold_id = SeatStatus.booked, booking.id, None
    hold.status = HoldStatus.converted
    db.commit()
    booking.qr_code_path = generate_booking_qr(booking.booking_reference)
    db.commit()
    db.refresh(booking)
    return booking, list(ids)


def _next_waiter(db: Session, event_id: int, category_id: int) -> WaitlistEntry | None:
    return db.scalar(select(WaitlistEntry).where(
        WaitlistEntry.event_id == event_id, WaitlistEntry.category_id == category_id,
        WaitlistEntry.status == WaitlistStatus.waiting,
    ).order_by(WaitlistEntry.created_at, WaitlistEntry.id).with_for_update(skip_locked=True).limit(1))


def assign_offer(db: Session, show_seat: ShowSeat) -> WaitlistOffer | None:
    category_id = db.scalar(select(Seat.category_id).where(Seat.id == show_seat.seat_id))
    entry = _next_waiter(db, show_seat.event_id, category_id)
    if not entry:
        show_seat.status, show_seat.current_hold_id, show_seat.current_booking_id = SeatStatus.available, None, None
        return None
    offer = WaitlistOffer(
        waitlist_entry_id=entry.id, event_id=show_seat.event_id, user_id=entry.user_id,
        category_id=category_id, show_seat_id=show_seat.id, token=secrets.token_urlsafe(32),
        expires_at=now_utc() + timedelta(minutes=settings.waitlist_offer_ttl_minutes),
    )
    db.add(offer)
    entry.status = WaitlistStatus.offered
    show_seat.status, show_seat.current_hold_id, show_seat.current_booking_id = SeatStatus.held, None, None
    db.flush()
    return offer


def cancel_booking(db: Session, booking_id: int, user_id: int) -> tuple[Booking, list[int], list[WaitlistOffer]]:
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if not booking or booking.user_id != user_id:
        raise HTTPException(404, "Booking not found")
    if booking.status != BookingStatus.confirmed:
        raise HTTPException(409, "Booking is already cancelled")
    ids = db.scalars(select(BookingSeat.show_seat_id).where(BookingSeat.booking_id == booking.id)).all()
    seats = db.scalars(select(ShowSeat).where(ShowSeat.id.in_(ids)).order_by(ShowSeat.id).with_for_update()).all()
    booking.status, booking.cancelled_at = BookingStatus.cancelled, now_utc()
    offers = []
    for seat in seats:
        seat.current_booking_id = None
        offer = assign_offer(db, seat)
        if offer:
            offers.append(offer)
    db.commit()
    return booking, list(ids), offers


def accept_offer(db: Session, token: str, user_id: int) -> tuple[Booking, int]:
    offer = db.scalar(select(WaitlistOffer).where(WaitlistOffer.token == token).with_for_update())
    if not offer or offer.user_id != user_id:
        raise HTTPException(404, "Offer not found")
    if offer.status != OfferStatus.pending or offer.expires_at <= now_utc():
        raise HTTPException(409, "Offer has expired or is no longer available")
    seat = db.scalar(select(ShowSeat).where(ShowSeat.id == offer.show_seat_id).with_for_update())
    if not seat or seat.status != SeatStatus.held:
        raise HTTPException(409, "Offered seat is no longer reserved")
    price = db.scalar(select(EventCategoryPrice.price).where(EventCategoryPrice.event_id == offer.event_id, EventCategoryPrice.category_id == offer.category_id))
    booking = Booking(booking_reference=f"TKT-{secrets.token_hex(5).upper()}", event_id=offer.event_id, user_id=user_id, total_amount=price)
    db.add(booking)
    db.flush()
    db.add(BookingSeat(booking_id=booking.id, show_seat_id=seat.id, price=price))
    seat.status, seat.current_booking_id, seat.current_hold_id = SeatStatus.booked, booking.id, None
    offer.status = OfferStatus.accepted
    entry = db.get(WaitlistEntry, offer.waitlist_entry_id)
    entry.status = WaitlistStatus.fulfilled
    db.commit()
    booking.qr_code_path = generate_booking_qr(booking.booking_reference)
    db.commit()
    return booking, seat.id


def decline_offer(db: Session, token: str, user_id: int) -> tuple[int, int, WaitlistOffer | None]:
    offer = db.scalar(select(WaitlistOffer).where(WaitlistOffer.token == token).with_for_update())
    if not offer or offer.user_id != user_id:
        raise HTTPException(404, "Offer not found")
    if offer.status != OfferStatus.pending:
        raise HTTPException(409, "Offer is not pending")
    seat = db.scalar(select(ShowSeat).where(ShowSeat.id == offer.show_seat_id).with_for_update())
    offer.status = OfferStatus.cancelled
    db.get(WaitlistEntry, offer.waitlist_entry_id).status = WaitlistStatus.cancelled
    next_offer = assign_offer(db, seat)
    db.commit()
    return offer.event_id, seat.id, next_offer


def expire_waitlist_offers(db: Session) -> list[tuple[int, int, WaitlistOffer | None]]:
    offers = db.scalars(select(WaitlistOffer).where(WaitlistOffer.status == OfferStatus.pending, WaitlistOffer.expires_at <= now_utc()).with_for_update(skip_locked=True)).all()
    changes = []
    for offer in offers:
        seat = db.scalar(select(ShowSeat).where(ShowSeat.id == offer.show_seat_id).with_for_update())
        offer.status = OfferStatus.expired
        db.get(WaitlistEntry, offer.waitlist_entry_id).status = WaitlistStatus.expired
        next_offer = assign_offer(db, seat)
        changes.append((offer.event_id, seat.id, next_offer))
    db.commit()
    return changes


def booking_email_context(db: Session, booking: Booking):
    user = db.get(User, booking.user_id)
    event = db.get(Event, booking.event_id)
    venue = db.get(Venue, event.venue_id)
    labels = db.scalars(select(func.concat(Seat.row_label, Seat.seat_number)).join(ShowSeat, ShowSeat.seat_id == Seat.id).join(BookingSeat, BookingSeat.show_seat_id == ShowSeat.id).where(BookingSeat.booking_id == booking.id)).all()
    return user, event, venue, list(labels)


def offer_email_context(db: Session, offer: WaitlistOffer):
    return db.get(User, offer.user_id), db.get(Event, offer.event_id), db.get(SeatCategory, offer.category_id)

