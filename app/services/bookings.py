from datetime import date
from decimal import Decimal

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, Room


ACTIVE_STATUSES = (BookingStatus.pending, BookingStatus.confirmed)


def overlaps_query(room_id, check_in: date, check_out: date):
    return select(Booking.id).where(
        Booking.room_id == room_id,
        Booking.status.in_(ACTIVE_STATUSES),
        Booking.check_in < check_out,
        Booking.check_out > check_in,
    )


def is_available(db: Session, room: Room, check_in: date, check_out: date) -> bool:
    if not room.active or not room.hotel.active:
        return False
    return db.scalar(select(exists(overlaps_query(room.id, check_in, check_out).subquery()))) is False


def calculate_price(nightly_rate: Decimal, check_in: date, check_out: date) -> Decimal:
    return (nightly_rate * (check_out - check_in).days).quantize(Decimal("0.01"))
