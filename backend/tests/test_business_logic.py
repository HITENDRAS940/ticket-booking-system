from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import Booking, HoldStatus, OfferStatus, SeatHold, SeatStatus, WaitlistEntry, WaitlistOffer, WaitlistStatus
from app.services.booking_service import accept_offer, cancel_booking, confirm_hold, create_hold, expire_waitlist_offers
from app.services.seat_service import expire_stale_holds, now_utc


def test_user_auth_basics(client):
    created = client.post("/api/auth/register", json={"name": "New Customer", "email": "new@example.com", "password": "Password1!", "role": "customer"})
    assert created.status_code == 201 and created.json()["user"]["role"] == "customer"
    login = client.post("/api/auth/login", json={"email": "new@example.com", "password": "Password1!"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["email"] == "new@example.com"
    assert client.post("/api/auth/register", json={"name": "Bad Admin", "email": "bad@example.com", "password": "Password1!", "role": "admin"}).status_code == 403


def test_holding_available_seats(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    db.refresh(sample["show_seats"][0])
    assert hold.status == HoldStatus.active and sample["show_seats"][0].status == SeatStatus.held


def test_prevent_duplicate_hold_on_same_seat(db, sample):
    seat_id = sample["show_seats"][0].id
    create_hold(db, sample["event"].id, sample["customer"].id, [seat_id])
    with pytest.raises(HTTPException) as exc:
        create_hold(db, sample["event"].id, sample["customer2"].id, [seat_id])
    assert exc.value.status_code == 409


def test_expired_hold_release(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    hold.expires_at = now_utc() - timedelta(seconds=1); db.commit()
    changes = expire_stale_holds(db); db.commit(); db.refresh(hold); db.refresh(sample["show_seats"][0])
    assert changes[sample["event"].id] == [sample["show_seats"][0].id]
    assert hold.status == HoldStatus.expired and sample["show_seats"][0].status == SeatStatus.available


def test_booking_confirmation_from_valid_hold(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    booking, _ = confirm_hold(db, hold.id, sample["customer"].id)
    db.refresh(sample["show_seats"][0])
    assert booking.total_amount == Decimal("100.00") and sample["show_seats"][0].status == SeatStatus.booked


def test_reject_booking_from_expired_hold(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    hold.expires_at = now_utc() - timedelta(seconds=1); db.commit()
    with pytest.raises(HTTPException) as exc:
        confirm_hold(db, hold.id, sample["customer"].id)
    assert exc.value.status_code == 409


def test_cancellation_releases_seat(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    booking, _ = confirm_hold(db, hold.id, sample["customer"].id)
    cancel_booking(db, booking.id, sample["customer"].id); db.refresh(sample["show_seats"][0])
    assert sample["show_seats"][0].status == SeatStatus.available


def test_cancellation_triggers_waitlist_offer(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    booking, _ = confirm_hold(db, hold.id, sample["customer"].id)
    entry = WaitlistEntry(event_id=sample["event"].id, user_id=sample["customer2"].id, category_id=sample["category"].id)
    db.add(entry); db.commit()
    _, _, offers = cancel_booking(db, booking.id, sample["customer"].id)
    assert len(offers) == 1 and offers[0].status == OfferStatus.pending
    db.refresh(sample["show_seats"][0]); assert sample["show_seats"][0].status == SeatStatus.held


def test_expired_offer_moves_to_next_customer(db, sample):
    hold = create_hold(db, sample["event"].id, sample["customer"].id, [sample["show_seats"][0].id])
    booking, _ = confirm_hold(db, hold.id, sample["customer"].id)
    first = WaitlistEntry(event_id=sample["event"].id, user_id=sample["customer2"].id, category_id=sample["category"].id)
    third_user = sample["admin"]
    second = WaitlistEntry(event_id=sample["event"].id, user_id=third_user.id, category_id=sample["category"].id)
    db.add_all([first, second]); db.commit()
    _, _, offers = cancel_booking(db, booking.id, sample["customer"].id)
    offers[0].expires_at = now_utc() - timedelta(seconds=1); db.commit()
    changes = expire_waitlist_offers(db)
    assert changes[0][2] is not None and changes[0][2].user_id == third_user.id
    db.refresh(first); db.refresh(second)
    assert first.status == WaitlistStatus.expired and second.status == WaitlistStatus.offered


def test_revenue_summary_calculation(client, db, sample):
    for seat in sample["show_seats"]:
        hold = create_hold(db, sample["event"].id, sample["customer"].id, [seat.id])
        confirm_hold(db, hold.id, sample["customer"].id)
    token = create_access_token(sample["organiser"].id, "organiser")
    response = client.get(f"/api/organiser/events/{sample['event'].id}/summary", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert Decimal(response.json()["total_revenue"]) == Decimal("200.00")

