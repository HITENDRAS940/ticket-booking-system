from app.db.session import SessionLocal
from app.services.booking_service import expire_waitlist_offers, offer_email_context
from app.services.mail_service import send_waitlist_offer_email
from app.services.seat_service import expire_stale_holds
from app.websocket.manager import manager


async def run_expiry_cycle():
    db = SessionLocal()
    try:
        hold_changes = expire_stale_holds(db)
        db.commit()
        offer_changes = expire_waitlist_offers(db)
        for event_id, ids in hold_changes.items():
            await manager.broadcast(event_id, "hold-expired", ids)
        for event_id, seat_id, next_offer in offer_changes:
            if next_offer:
                user, event, category = offer_email_context(db, next_offer)
                await send_waitlist_offer_email(db, user=user, event=event, category=category, offer=next_offer)
            await manager.broadcast(event_id, "offer-reassigned" if next_offer else "released", [seat_id])
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

