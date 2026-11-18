import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import BookingStatus, PaymentStatus, Role


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class UserOut(ModelOut):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: Role


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HotelIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=5000)
    city: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=3, max_length=300)


class HotelPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = Field(default=None, max_length=5000)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    address: str | None = Field(default=None, min_length=3, max_length=300)
    active: bool | None = None


class HotelOut(ModelOut):
    id: uuid.UUID
    name: str
    description: str
    city: str
    address: str
    active: bool


class RoomIn(BaseModel):
    number: str = Field(min_length=1, max_length=30)
    room_type: str = Field(min_length=2, max_length=100)
    capacity: int = Field(ge=1, le=30)
    nightly_rate: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="AED", pattern="^[A-Z]{3}$")


class RoomPatch(BaseModel):
    room_type: str | None = Field(default=None, min_length=2, max_length=100)
    capacity: int | None = Field(default=None, ge=1, le=30)
    nightly_rate: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    active: bool | None = None


class RoomOut(ModelOut):
    id: uuid.UUID
    hotel_id: uuid.UUID
    number: str
    room_type: str
    capacity: int
    nightly_rate: Decimal
    currency: str
    active: bool


class BookingIn(BaseModel):
    room_id: uuid.UUID
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=30)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class BookingOut(ModelOut):
    id: uuid.UUID
    user_id: uuid.UUID
    room_id: uuid.UUID
    check_in: date
    check_out: date
    guests: int
    total_amount: Decimal
    currency: str
    status: BookingStatus
    created_at: datetime


class PaymentIn(BaseModel):
    simulate_success: bool = True


class PaymentOut(ModelOut):
    id: uuid.UUID
    booking_id: uuid.UUID
    amount: Decimal
    currency: str
    status: PaymentStatus
    created_at: datetime


class AvailabilityOut(BaseModel):
    room_id: uuid.UUID
    check_in: date
    check_out: date
    available: bool
