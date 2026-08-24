from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Event, EventCategoryPrice, EventStatus, EventType, Role, Seat, SeatCategory, ShowSeat, User, Venue,
)


def seed():
    db = SessionLocal()
    try:
        if db.scalar(select(User.id).limit(1)):
            print("Database already contains users; seed skipped.")
            return
        admin = User(name="Admin User", email="admin@example.com", password_hash=hash_password("Admin123!"), role=Role.admin)
        organiser = User(name="Event Organiser", email="organiser@example.com", password_hash=hash_password("Organiser123!"), role=Role.organiser)
        customer = User(name="Customer User", email="customer@example.com", password_hash=hash_password("Customer123!"), role=Role.customer)
        db.add_all([admin, organiser, customer]); db.flush()
        venue = Venue(name="City Arts Hall", address="12 Central Avenue, Bengaluru", rows=8, columns=12, created_by_admin_id=admin.id)
        db.add(venue); db.flush()
        premium = SeatCategory(venue_id=venue.id, name="Premium", color_label="#F59E0B")
        standard = SeatCategory(venue_id=venue.id, name="Standard", color_label="#9CA3AF")
        db.add_all([premium, standard]); db.flush()
        seats = []
        for row_index in range(8):
            row = chr(65 + row_index)
            for number in range(1, 13):
                # Two rear corner gaps make the example layout realistic.
                active = not (row_index >= 6 and number in (1, 12))
                seat = Seat(venue_id=venue.id, row_label=row, seat_number=number, category_id=premium.id if row_index < 3 else standard.id, is_active=active)
                db.add(seat); seats.append(seat)
        db.flush()
        events = [
            Event(organiser_id=organiser.id, venue_id=venue.id, title="The Last Horizon", event_type=EventType.movie, description="A science-fiction drama about a crew returning to a changed Earth.", show_date=date.today() + timedelta(days=14), show_time=time(19, 0), status=EventStatus.published),
            Event(organiser_id=organiser.id, venue_id=venue.id, title="Midnight Echoes Live", event_type=EventType.concert, description="An intimate live concert featuring acoustic and electronic arrangements.", show_date=date.today() + timedelta(days=30), show_time=time(20, 0), status=EventStatus.published),
        ]
        db.add_all(events); db.flush()
        for event in events:
            db.add_all([EventCategoryPrice(event_id=event.id, category_id=premium.id, price=Decimal("850.00")), EventCategoryPrice(event_id=event.id, category_id=standard.id, price=Decimal("450.00"))])
            for seat in seats:
                if seat.is_active:
                    db.add(ShowSeat(event_id=event.id, seat_id=seat.id))
        db.commit()
        print("Seed complete. Logins: admin@example.com / Admin123!, organiser@example.com / Organiser123!, customer@example.com / Customer123!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

