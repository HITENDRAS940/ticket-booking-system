from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import customer_only
from app.db.session import get_db
from app.models import Event, EventCategoryPrice, OfferStatus, Seat, SeatCategory, SeatStatus, ShowSeat, User, WaitlistEntry, WaitlistOffer, WaitlistStatus
from app.schemas import WaitlistJoin
from app.services.booking_service import accept_offer, booking_email_context, decline_offer, offer_email_context
from app.services.mail_service import send_booking_email, send_waitlist_offer_email
from app.websocket.manager import manager

router = APIRouter(tags=["waitlist"])


def entry_payload(db: Session, entry: WaitlistEntry):
    event, category = db.get(Event, entry.event_id), db.get(SeatCategory, entry.category_id)
    offer = db.scalar(select(WaitlistOffer).where(WaitlistOffer.waitlist_entry_id == entry.id).order_by(WaitlistOffer.created_at.desc()).limit(1))
    return {
        "id": entry.id, "event_id": entry.event_id, "event_title": event.title, "category_id": entry.category_id,
        "category_name": category.name, "status": entry.status, "created_at": entry.created_at,
        "offer": None if not offer else {"token": offer.token, "status": offer.status, "expires_at": offer.expires_at},
    }


@router.post("/api/events/{event_id}/waitlist", status_code=201)
def join_waitlist(event_id: int, payload: WaitlistJoin, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    event = db.get(Event, event_id)
    category = db.get(SeatCategory, payload.category_id)
    if not event or not category or category.venue_id != event.venue_id:
        raise HTTPException(404, "Event category not found")
    if not db.scalar(select(EventCategoryPrice.id).where(EventCategoryPrice.event_id == event_id, EventCategoryPrice.category_id == payload.category_id)):
        raise HTTPException(400, "Category is not priced for this event")
    available = db.scalar(select(func.count()).select_from(ShowSeat).join(Seat, Seat.id == ShowSeat.seat_id).where(ShowSeat.event_id == event_id, Seat.category_id == payload.category_id, ShowSeat.status == SeatStatus.available))
    if available:
        raise HTTPException(409, "Seats are still available in this category")
    entry = WaitlistEntry(event_id=event_id, user_id=user.id, category_id=payload.category_id)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You are already active on this waitlist")
    db.refresh(entry)
    return entry_payload(db, entry)


@router.get("/api/waitlist/my")
def my_waitlist(db: Session = Depends(get_db), user: User = Depends(customer_only)):
    entries = db.scalars(select(WaitlistEntry).where(WaitlistEntry.user_id == user.id).order_by(WaitlistEntry.created_at.desc())).all()
    return [entry_payload(db, e) for e in entries]


@router.get("/api/waitlist/offers/{token}")
def get_offer(token: str, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    offer = db.scalar(select(WaitlistOffer).where(WaitlistOffer.token == token, WaitlistOffer.user_id == user.id))
    if not offer:
        raise HTTPException(404, "Offer not found")
    event, category = db.get(Event, offer.event_id), db.get(SeatCategory, offer.category_id)
    return {"event_title": event.title, "category_name": category.name, "expires_at": offer.expires_at, "status": offer.status}


@router.post("/api/waitlist/offers/{token}/accept")
async def accept(token: str, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    booking, seat_id = accept_offer(db, token, user.id)
    email_user, event, venue, labels = booking_email_context(db, booking)
    await send_booking_email(db, user=email_user, event=event, venue=venue, booking=booking, seats=labels)
    await manager.broadcast(booking.event_id, "booked", [seat_id])
    return {"booking_id": booking.id, "booking_reference": booking.booking_reference}


@router.post("/api/waitlist/offers/{token}/decline")
async def decline(token: str, db: Session = Depends(get_db), user: User = Depends(customer_only)):
    event_id, seat_id, next_offer = decline_offer(db, token, user.id)
    if next_offer:
        recipient, event, category = offer_email_context(db, next_offer)
        await send_waitlist_offer_email(db, user=recipient, event=event, category=category, offer=next_offer)
    await manager.broadcast(event_id, "waitlist-reassigned" if next_offer else "released", [seat_id])
    return {"message": "Offer declined"}

