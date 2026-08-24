import os
import sys
from pathlib import Path
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://tickets:tickets@localhost:5432/tickets_test")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SMTP_HOST"] = ""

from app.api.deps import get_db
from app.core.security import hash_password
from app.db.base import Base
from app.main import app
from app.models import Event, EventCategoryPrice, EventStatus, EventType, Role, Seat, SeatCategory, ShowSeat, User, Venue

engine = create_engine(os.environ["DATABASE_URL"])
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def override():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()
    app.dependency_overrides[get_db] = override
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


@pytest.fixture
def sample(db):
    admin = User(name="Admin", email="admin@test.com", password_hash=hash_password("Password1!"), role=Role.admin)
    organiser = User(name="Organiser", email="org@test.com", password_hash=hash_password("Password1!"), role=Role.organiser)
    customer = User(name="Customer", email="customer@test.com", password_hash=hash_password("Password1!"), role=Role.customer)
    customer2 = User(name="Next Customer", email="customer2@test.com", password_hash=hash_password("Password1!"), role=Role.customer)
    db.add_all([admin, organiser, customer, customer2]); db.flush()
    venue = Venue(name="Test Hall", address="Test Address", rows=1, columns=2, created_by_admin_id=admin.id)
    db.add(venue); db.flush()
    category = SeatCategory(venue_id=venue.id, name="Premium")
    db.add(category); db.flush()
    seats = [Seat(venue_id=venue.id, row_label="A", seat_number=i, category_id=category.id) for i in (1, 2)]
    db.add_all(seats); db.flush()
    event = Event(organiser_id=organiser.id, venue_id=venue.id, title="Test Event", event_type=EventType.movie, description="Test", show_date=date.today() + timedelta(days=2), show_time=time(19), status=EventStatus.published)
    db.add(event); db.flush()
    db.add(EventCategoryPrice(event_id=event.id, category_id=category.id, price=Decimal("100.00")))
    show_seats = [ShowSeat(event_id=event.id, seat_id=seat.id) for seat in seats]
    db.add_all(show_seats); db.commit()
    return {"admin": admin, "organiser": organiser, "customer": customer, "customer2": customer2, "venue": venue, "category": category, "event": event, "show_seats": show_seats}
