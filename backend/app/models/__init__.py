import enum
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    customer = "customer"
    organiser = "organiser"
    admin = "admin"


class EventType(str, enum.Enum):
    movie = "movie"
    concert = "concert"


class EventStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    completed = "completed"
    cancelled = "cancelled"


class SeatStatus(str, enum.Enum):
    available = "available"
    held = "held"
    booked = "booked"


class HoldStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    converted = "converted"
    cancelled = "cancelled"


class BookingStatus(str, enum.Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"


class WaitlistStatus(str, enum.Enum):
    waiting = "waiting"
    offered = "offered"
    fulfilled = "fulfilled"
    expired = "expired"
    cancelled = "cancelled"


class OfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    expired = "expired"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role_enum"), default=Role.customer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Venue(Base):
    __tablename__ = "venues"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    address: Mapped[str] = mapped_column(Text)
    rows: Mapped[int] = mapped_column(Integer)
    columns: Mapped[int] = mapped_column(Integer)
    created_by_admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeatCategory(Base):
    __tablename__ = "seat_categories"
    __table_args__ = (UniqueConstraint("venue_id", "name", name="uq_category_venue_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    color_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("venue_id", "row_label", "seat_number", name="uq_seat_position"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), index=True)
    row_label: Mapped[str] = mapped_column(String(10))
    seat_number: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(ForeignKey("seat_categories.id", ondelete="RESTRICT"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    organiser_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType, name="event_type_enum"), index=True)
    description: Mapped[str] = mapped_column(Text)
    show_date: Mapped[date] = mapped_column(Date, index=True)
    show_time: Mapped[time] = mapped_column(Time)
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus, name="event_status_enum"), default=EventStatus.draft, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventCategoryPrice(Base):
    __tablename__ = "event_category_prices"
    __table_args__ = (UniqueConstraint("event_id", "category_id", name="uq_event_category_price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("seat_categories.id", ondelete="RESTRICT"))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class ShowSeat(Base):
    __tablename__ = "show_seats"
    __table_args__ = (UniqueConstraint("event_id", "seat_id", name="uq_event_seat"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id", ondelete="RESTRICT"), index=True)
    status: Mapped[SeatStatus] = mapped_column(Enum(SeatStatus, name="seat_status_enum"), default=SeatStatus.available, index=True)
    current_hold_id: Mapped[int | None] = mapped_column(ForeignKey("seat_holds.id", name="fk_show_seat_current_hold", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    current_booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id", name="fk_show_seat_current_booking", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SeatHold(Base):
    __tablename__ = "seat_holds"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[HoldStatus] = mapped_column(Enum(HoldStatus, name="hold_status_enum"), default=HoldStatus.active, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeatHoldItem(Base):
    __tablename__ = "seat_hold_items"
    __table_args__ = (UniqueConstraint("hold_id", "show_seat_id", name="uq_hold_seat"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hold_id: Mapped[int] = mapped_column(ForeignKey("seat_holds.id", ondelete="CASCADE"), index=True)
    show_seat_id: Mapped[int] = mapped_column(ForeignKey("show_seats.id", ondelete="CASCADE"), index=True)


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus, name="booking_status_enum"), default=BookingStatus.confirmed, index=True)
    qr_code_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BookingSeat(Base):
    __tablename__ = "booking_seats"
    __table_args__ = (UniqueConstraint("booking_id", "show_seat_id", name="uq_booking_seat"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    show_seat_id: Mapped[int] = mapped_column(ForeignKey("show_seats.id", ondelete="RESTRICT"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (
        Index("uq_active_waitlist", "event_id", "user_id", "category_id", unique=True, postgresql_where=text("status IN ('waiting', 'offered')")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("seat_categories.id", ondelete="RESTRICT"), index=True)
    status: Mapped[WaitlistStatus] = mapped_column(Enum(WaitlistStatus, name="waitlist_status_enum"), default=WaitlistStatus.waiting, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WaitlistOffer(Base):
    __tablename__ = "waitlist_offers"
    __table_args__ = (Index("uq_pending_offer_seat", "show_seat_id", unique=True, postgresql_where=text("status = 'pending'")),)
    id: Mapped[int] = mapped_column(primary_key=True)
    waitlist_entry_id: Mapped[int] = mapped_column(ForeignKey("waitlist_entries.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("seat_categories.id", ondelete="RESTRICT"))
    show_seat_id: Mapped[int] = mapped_column(ForeignKey("show_seats.id", ondelete="RESTRICT"), index=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[OfferStatus] = mapped_column(Enum(OfferStatus, name="offer_status_enum"), default=OfferStatus.pending, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailLog(Base):
    __tablename__ = "email_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_email: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(30))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
