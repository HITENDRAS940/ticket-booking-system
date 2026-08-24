from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import admin_only
from app.db.session import get_db
from app.models import Seat, SeatCategory, User, Venue
from app.schemas import CategoryIn, SeatBulkItem, SeatUpdate, VenueCreate, VenueUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])


def venue_payload(db: Session, venue: Venue):
    categories = db.scalars(select(SeatCategory).where(SeatCategory.venue_id == venue.id).order_by(SeatCategory.id)).all()
    seats = db.scalars(select(Seat).where(Seat.venue_id == venue.id).order_by(Seat.row_label, Seat.seat_number)).all()
    return {
        "id": venue.id, "name": venue.name, "address": venue.address, "rows": venue.rows, "columns": venue.columns,
        "categories": [{"id": c.id, "name": c.name, "color_label": c.color_label} for c in categories],
        "seats": [{"id": s.id, "row_label": s.row_label, "seat_number": s.seat_number, "category_id": s.category_id, "is_active": s.is_active} for s in seats],
    }


@router.post("/venues", status_code=201)
def create_venue(payload: VenueCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    venue = Venue(name=payload.name, address=payload.address, rows=payload.rows, columns=payload.columns, created_by_admin_id=admin.id)
    db.add(venue)
    db.flush()
    for item in payload.categories:
        db.add(SeatCategory(venue_id=venue.id, name=item.name, color_label=item.color_label))
    db.commit()
    db.refresh(venue)
    return venue_payload(db, venue)


@router.get("/venues")
def list_venues(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return [venue_payload(db, v) for v in db.scalars(select(Venue).order_by(Venue.name)).all()]


@router.get("/venues/{venue_id}")
def get_venue(venue_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(404, "Venue not found")
    return venue_payload(db, venue)


@router.put("/venues/{venue_id}")
def update_venue(venue_id: int, payload: VenueUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(404, "Venue not found")
    for key, value in payload.model_dump().items():
        setattr(venue, key, value)
    db.commit()
    return venue_payload(db, venue)


@router.delete("/venues/{venue_id}", status_code=204)
def delete_venue(venue_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(404, "Venue not found")
    db.delete(venue)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Venue is used by an event and cannot be deleted")
    return Response(status_code=204)


@router.post("/venues/{venue_id}/seats/bulk")
def bulk_seats(venue_id: int, payload: list[SeatBulkItem], db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(404, "Venue not found")
    categories = set(db.scalars(select(SeatCategory.id).where(SeatCategory.venue_id == venue_id)).all())
    if any(item.category_id not in categories for item in payload):
        raise HTTPException(400, "Every category must belong to this venue")
    existing = {(s.row_label, s.seat_number): s for s in db.scalars(select(Seat).where(Seat.venue_id == venue_id)).all()}
    for item in payload:
        key = (item.row_label.upper(), item.seat_number)
        if key in existing:
            existing[key].category_id, existing[key].is_active = item.category_id, item.is_active
        else:
            db.add(Seat(venue_id=venue_id, row_label=key[0], seat_number=item.seat_number, category_id=item.category_id, is_active=item.is_active))
    db.commit()
    return venue_payload(db, venue)


@router.put("/seats/{seat_id}")
def update_seat(seat_id: int, payload: SeatUpdate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    seat = db.get(Seat, seat_id)
    if not seat:
        raise HTTPException(404, "Seat not found")
    if payload.category_id is not None:
        category = db.get(SeatCategory, payload.category_id)
        if not category or category.venue_id != seat.venue_id:
            raise HTTPException(400, "Category must belong to the seat's venue")
        seat.category_id = payload.category_id
    if payload.is_active is not None:
        seat.is_active = payload.is_active
    db.commit()
    return {"id": seat.id, "category_id": seat.category_id, "is_active": seat.is_active}


@router.post("/venues/{venue_id}/categories", status_code=201)
def create_category(venue_id: int, payload: CategoryIn, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    if not db.get(Venue, venue_id):
        raise HTTPException(404, "Venue not found")
    category = SeatCategory(venue_id=venue_id, **payload.model_dump())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category name already exists for this venue")
    db.refresh(category)
    return {"id": category.id, "name": category.name, "color_label": category.color_label}


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryIn, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    category = db.get(SeatCategory, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    category.name, category.color_label = payload.name, payload.color_label
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category name already exists for this venue")
    return {"id": category.id, "name": category.name, "color_label": category.color_label}


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    category = db.get(SeatCategory, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    db.delete(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Category is assigned to seats or event prices")
    return Response(status_code=204)
