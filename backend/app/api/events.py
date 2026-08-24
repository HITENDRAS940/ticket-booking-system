from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event, EventCategoryPrice, EventStatus, EventType, Seat, SeatCategory, SeatStatus, ShowSeat, Venue

router = APIRouter(prefix="/api/events", tags=["events"])


def public_event(db: Session, event: Event):
    venue = db.get(Venue, event.venue_id)
    available = db.scalar(select(func.count()).select_from(ShowSeat).where(ShowSeat.event_id == event.id, ShowSeat.status == SeatStatus.available)) or 0
    prices = db.execute(select(EventCategoryPrice, SeatCategory).join(SeatCategory, SeatCategory.id == EventCategoryPrice.category_id).where(EventCategoryPrice.event_id == event.id)).all()
    return {
        "id": event.id, "title": event.title, "event_type": event.event_type, "description": event.description,
        "venue": {"id": venue.id, "name": venue.name, "address": venue.address},
        "show_date": event.show_date, "show_time": event.show_time, "status": event.status,
        "available_seats": available,
        "prices": [{"category_id": p.category_id, "category_name": c.name, "color_label": c.color_label, "price": p.price} for p, c in prices],
    }


@router.get("")
def list_events(
    event_type: EventType | None = None, show_date: date | None = None, venue_id: int | None = None,
    availability: bool | None = None, search: str | None = Query(None, max_length=120), db: Session = Depends(get_db),
):
    query = select(Event).where(Event.status == EventStatus.published)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if show_date:
        query = query.where(Event.show_date == show_date)
    if venue_id:
        query = query.where(Event.venue_id == venue_id)
    if search:
        query = query.where(or_(Event.title.ilike(f"%{search}%"), Event.description.ilike(f"%{search}%")))
    if availability is not None:
        available_exists = exists(select(ShowSeat.id).where(ShowSeat.event_id == Event.id, ShowSeat.status == SeatStatus.available))
        query = query.where(available_exists if availability else ~available_exists)
    events = db.scalars(query.order_by(Event.show_date, Event.show_time)).all()
    return [public_event(db, event) for event in events]


@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event or event.status != EventStatus.published:
        raise HTTPException(404, "Published event not found")
    return public_event(db, event)


@router.get("/{event_id}/seat-map")
def seat_map(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event or event.status != EventStatus.published:
        raise HTTPException(404, "Published event not found")
    venue = db.get(Venue, event.venue_id)
    rows = db.execute(
        select(ShowSeat, Seat, SeatCategory, EventCategoryPrice)
        .join(Seat, Seat.id == ShowSeat.seat_id)
        .join(SeatCategory, SeatCategory.id == Seat.category_id)
        .join(EventCategoryPrice, (EventCategoryPrice.event_id == event.id) & (EventCategoryPrice.category_id == Seat.category_id))
        .where(ShowSeat.event_id == event.id).order_by(Seat.row_label, Seat.seat_number)
    ).all()
    return {
        "event_id": event.id, "venue": {"id": venue.id, "name": venue.name, "rows": venue.rows, "columns": venue.columns},
        "seats": [{
            "id": show.id, "seat_id": seat.id, "row_label": seat.row_label, "seat_number": seat.seat_number,
            "category_id": category.id, "category_name": category.name, "color_label": category.color_label,
            "price": price.price, "status": show.status,
        } for show, seat, category, price in rows],
    }

