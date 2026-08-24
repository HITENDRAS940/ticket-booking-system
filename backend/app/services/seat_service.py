from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HoldStatus, SeatHold, SeatHoldItem, SeatStatus, ShowSeat


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def expire_stale_holds(db: Session, event_id: int | None = None) -> dict[int, list[int]]:
    query = select(SeatHold).where(SeatHold.status == HoldStatus.active, SeatHold.expires_at <= now_utc()).with_for_update()
    if event_id is not None:
        query = query.where(SeatHold.event_id == event_id)
    expired = db.scalars(query).all()
    changed: dict[int, list[int]] = {}
    for hold in expired:
        ids = db.scalars(select(SeatHoldItem.show_seat_id).where(SeatHoldItem.hold_id == hold.id)).all()
        seats = db.scalars(select(ShowSeat).where(ShowSeat.id.in_(ids)).with_for_update()).all() if ids else []
        for seat in seats:
            if seat.current_hold_id == hold.id and seat.status == SeatStatus.held:
                seat.status = SeatStatus.available
                seat.current_hold_id = None
                changed.setdefault(hold.event_id, []).append(seat.id)
        hold.status = HoldStatus.expired
    return changed


def get_owned_hold(db: Session, hold_id: int, user_id: int, lock: bool = False) -> SeatHold:
    query = select(SeatHold).where(SeatHold.id == hold_id)
    if lock:
        query = query.with_for_update()
    hold = db.scalar(query)
    if not hold or hold.user_id != user_id:
        raise HTTPException(404, "Hold not found")
    return hold

