from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import EventStatus, EventType, Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.customer


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORMModel):
    id: int
    name: str
    email: EmailStr
    role: Role


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color_label: str | None = None


class VenueCreate(BaseModel):
    name: str
    address: str
    rows: int = Field(ge=1, le=100)
    columns: int = Field(ge=1, le=200)
    categories: list[CategoryIn] = Field(min_length=1)


class VenueUpdate(BaseModel):
    name: str
    address: str
    rows: int = Field(ge=1, le=100)
    columns: int = Field(ge=1, le=200)


class SeatBulkItem(BaseModel):
    row_label: str
    seat_number: int = Field(ge=1)
    category_id: int
    is_active: bool = True


class SeatUpdate(BaseModel):
    category_id: int | None = None
    is_active: bool | None = None


class PriceIn(BaseModel):
    category_id: int
    price: Decimal = Field(gt=0)


class EventCreate(BaseModel):
    venue_id: int
    title: str = Field(min_length=2, max_length=220)
    event_type: EventType
    description: str
    show_date: date
    show_time: time
    status: EventStatus = EventStatus.draft
    prices: list[PriceIn] = Field(min_length=1)


class EventUpdate(EventCreate):
    pass


class HoldCreate(BaseModel):
    show_seat_ids: list[int] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_seats(self):
        if len(set(self.show_seat_ids)) != len(self.show_seat_ids):
            raise ValueError("Duplicate seats are not allowed")
        return self


class ConfirmBooking(BaseModel):
    hold_id: int
    customer_name: str | None = None
    customer_email: EmailStr | None = None


class WaitlistJoin(BaseModel):
    category_id: int


class Message(BaseModel):
    message: str


class HoldOut(BaseModel):
    id: int
    event_id: int
    expires_at: datetime
    status: str
    show_seat_ids: list[int]

