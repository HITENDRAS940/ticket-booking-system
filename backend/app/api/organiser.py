from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import organiser_only
from app.db.session import get_db
from app.models import (
    Booking, BookingStatus, Event, EventCategoryPrice, EventStatus, Seat, SeatCategory,
    SeatStatus, ShowSeat, User, Venue, WaitlistEntry, WaitlistStatus,
)
from app.schemas import EventCreate, EventUpdate

router = APIRouter(prefix="/api/organiser", tags=["organiser"])


def event_payload(db: Session, event: Event):
    venue = db.get(Venue, event.venue_id)
    prices = db.execute(select(EventCategoryPrice, SeatCategory).join(SeatCategory, SeatCategory.id == EventCategoryPrice.category_id).where(EventCategoryPrice.event_id == event.id)).all()
    return {
        "id": event.id, "title": event.title, "event_type": event.event_type, "description": event.description,
        "venue_id": event.venue_id, "venue_name": venue.name, "show_date": event.show_date, "show_time": event.show_time,
        "status": event.status, "prices": [{"category_id": p.category_id, "category_name": c.name, "price": p.price} for p, c in prices],
    }


def validate_prices(db: Session, venue_id: int, prices):
    categories = set(db.scalars(select(SeatCategory.id).where(SeatCategory.venue_id == venue_id)).all())
    if not categories or {p.category_id for p in prices} != categories:
        raise HTTPException(400, "Provide exactly one price for every venue category")


@router.post("/events", status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db), user: User = Depends(organiser_only)):
    if not db.get(Venue, payload.venue_id):
        raise HTTPException(404, "Venue not found")
    validate_prices(db, payload.venue_id, payload.prices)
    data = payload.model_dump(exclude={"prices"})
    event = Event(organiser_id=user.id, **data)
    db.add(event)
    db.flush()
    for price in payload.prices:
        db.add(EventCategoryPrice(event_id=event.id, **price.model_dump()))
    seats = db.scalars(select(Seat).where(Seat.venue_id == event.venue_id, Seat.is_active.is_(True))).all()
    for seat in seats:
        db.add(ShowSeat(event_id=event.id, seat_id=seat.id))
    db.commit()
    return event_payload(db, event)


@router.get("/events")
def list_events(db: Session = Depends(get_db), user: User = Depends(organiser_only)):
    return [event_payload(db, e) for e in db.scalars(select(Event).where(Event.organiser_id == user.id).order_by(Event.show_date.desc())).all()]


def own_event(db, event_id, user_id):
    event = db.get(Event, event_id)
    if not event or event.organiser_id != user_id:
        raise HTTPException(404, "Event not found")
    return event


@router.get("/venues")
def organiser_venues(db: Session = Depends(get_db), _: User = Depends(organiser_only)):
    venues = db.scalars(select(Venue).order_by(Venue.name)).all()
    return [{
        "id": venue.id, "name": venue.name,
        "categories": [{"id": c.id, "name": c.name} for c in db.scalars(select(SeatCategory).where(SeatCategory.venue_id == venue.id).order_by(SeatCategory.id)).all()],
    } for venue in venues]


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db), user: User = Depends(organiser_only)):
    return event_payload(db, own_event(db, event_id, user.id))


@router.put("/events/{event_id}")
def update_event(event_id: int, payload: EventUpdate, db: Session = Depends(get_db), user: User = Depends(organiser_only)):
    event = own_event(db, event_id, user.id)
    if event.venue_id != payload.venue_id and db.scalar(select(Booking.id).where(Booking.event_id == event.id).limit(1)):
        raise HTTPException(409, "Venue cannot change after bookings exist")
    validate_prices(db, payload.venue_id, payload.prices)
    old_venue = event.venue_id
    for key, value in payload.model_dump(exclude={"prices"}).items():
        setattr(event, key, value)
    db.execute(delete(EventCategoryPrice).where(EventCategoryPrice.event_id == event.id))
    for price in payload.prices:
        db.add(EventCategoryPrice(event_id=event.id, **price.model_dump()))
    if old_venue != event.venue_id:
        db.execute(delete(ShowSeat).where(ShowSeat.event_id == event.id))
        for seat in db.scalars(select(Seat).where(Seat.venue_id == event.venue_id, Seat.is_active.is_(True))):
            db.add(ShowSeat(event_id=event.id, seat_id=seat.id))
    db.commit()
    return event_payload(db, event)


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db), user: User = Depends(organiser_only)):
    event = own_event(db, event_id, user.id)
    if db.scalar(select(Booking.id).where(Booking.event_id == event.id).limit(1)):
        raise HTTPException(409, "Events with booking history cannot be deleted; set status to cancelled")
    db.delete(event)
    db.commit()
    return Response(status_code=204)


@router.get("/events/{event_id}/summary")
def event_summary(event_id: int, db: Session = Depends(get_db), user: User = Depends(organiser_only)):
    event = own_event(db, event_id, user.id)
    counts = dict(db.execute(select(ShowSeat.status, func.count()).where(ShowSeat.event_id == event.id).group_by(ShowSeat.status)).all())
    cancelled = db.scalar(select(func.count()).select_from(Booking).where(Booking.event_id == event.id, Booking.status == BookingStatus.cancelled)) or 0
    waitlist = db.scalar(select(func.count()).select_from(WaitlistEntry).where(WaitlistEntry.event_id == event.id, WaitlistEntry.status.in_([WaitlistStatus.waiting, WaitlistStatus.offered]))) or 0
    revenue = db.scalar(select(func.coalesce(func.sum(Booking.total_amount), 0)).where(Booking.event_id == event.id, Booking.status == BookingStatus.confirmed)) or Decimal("0")
    total = sum(counts.values())
    return {
        "event_id": event.id, "title": event.title, "total_seats": total,
        "booked_seats": counts.get(SeatStatus.booked, 0), "available_seats": counts.get(SeatStatus.available, 0),
        "held_seats": counts.get(SeatStatus.held, 0), "cancelled_bookings": cancelled,
        "waitlist_count": waitlist, "total_revenue": revenue,
    }
