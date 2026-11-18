import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import current_user, hash_password, issue_token, require_admin, verify_password
from app.models import Booking, BookingStatus, Hotel, Payment, PaymentStatus, Room, User
from app.schemas.resources import (
    AvailabilityOut, BookingIn, BookingOut, HotelIn, HotelOut, HotelPatch,
    LoginIn, PaymentIn, PaymentOut, RoomIn, RoomOut, RoomPatch, TokenOut,
    UserCreate, UserOut,
)
from app.services.bookings import calculate_price, is_available

router = APIRouter(prefix="/api/v1")


def commit_or_conflict(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


@router.post("/auth/register", response_model=UserOut, status_code=201, tags=["Authentication"])
def register(body: UserCreate, db: Session = Depends(get_db)):
    user = User(name=body.name, email=str(body.email).lower(), password_hash=hash_password(body.password))
    db.add(user)
    commit_or_conflict(db, "Email already registered")
    return user


@router.post("/auth/login", response_model=TokenOut, tags=["Authentication"])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=issue_token(user))


@router.get("/users/me", response_model=UserOut, tags=["Users"])
def me(user: User = Depends(current_user)):
    return user


@router.get("/hotels", response_model=list[HotelOut], tags=["Hotels"])
def hotels(city: str | None = None, search: str | None = None,
           limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
           db: Session = Depends(get_db)):
    query = select(Hotel).where(Hotel.active.is_(True))
    if city:
        query = query.where(Hotel.city.ilike(city))
    if search:
        term = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Hotel.name.ilike(f"%{term}%", escape="\\"))
    return db.scalars(query.order_by(Hotel.name, Hotel.id).limit(limit).offset(offset)).all()


@router.get("/hotels/{hotel_id}", response_model=HotelOut, tags=["Hotels"])
def hotel_detail(hotel_id: uuid.UUID, db: Session = Depends(get_db)):
    hotel = db.get(Hotel, hotel_id)
    if hotel is None or not hotel.active:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


@router.get("/hotels/{hotel_id}/rooms", response_model=list[RoomOut], tags=["Rooms"])
def hotel_rooms(hotel_id: uuid.UUID, db: Session = Depends(get_db)):
    hotel = hotel_detail(hotel_id, db)
    return db.scalars(select(Room).where(Room.hotel_id == hotel.id, Room.active.is_(True)).order_by(Room.number)).all()


@router.get("/rooms/{room_id}/availability", response_model=AvailabilityOut, tags=["Rooms"])
def room_availability(room_id: uuid.UUID, check_in: date, check_out: date,
                      db: Session = Depends(get_db)):
    if check_in < date.today() or check_out <= check_in:
        raise HTTPException(status_code=422, detail="Invalid booking dates")
    room = db.scalar(select(Room).options(joinedload(Room.hotel)).where(Room.id == room_id))
    if room is None or not room.active or not room.hotel.active:
        raise HTTPException(status_code=404, detail="Room not found")
    return AvailabilityOut(room_id=room_id, check_in=check_in, check_out=check_out,
                           available=is_available(db, room, check_in, check_out))


@router.post("/admin/hotels", response_model=HotelOut, status_code=201, tags=["Administration"])
def create_hotel(body: HotelIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    hotel = Hotel(**body.model_dump())
    db.add(hotel)
    db.commit()
    return hotel


@router.patch("/admin/hotels/{hotel_id}", response_model=HotelOut, tags=["Administration"])
def edit_hotel(hotel_id: uuid.UUID, body: HotelPatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(hotel, key, value)
    db.commit()
    return hotel


@router.post("/admin/hotels/{hotel_id}/rooms", response_model=RoomOut, status_code=201, tags=["Administration"])
def create_room(hotel_id: uuid.UUID, body: RoomIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.get(Hotel, hotel_id) is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    room = Room(hotel_id=hotel_id, **body.model_dump())
    db.add(room)
    commit_or_conflict(db, "Room number already exists in this hotel")
    return room


@router.patch("/admin/rooms/{room_id}", response_model=RoomOut, tags=["Administration"])
def edit_room(room_id: uuid.UUID, body: RoomPatch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(room, key, value)
    db.commit()
    return room


@router.post("/bookings", response_model=BookingOut, status_code=201, tags=["Bookings"])
def create_booking(body: BookingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if body.check_in < date.today():
        raise HTTPException(status_code=422, detail="Cannot book dates in the past")
    room = db.scalar(select(Room).options(joinedload(Room.hotel)).where(Room.id == body.room_id))
    if room is None or not room.active or not room.hotel.active:
        raise HTTPException(status_code=404, detail="Room not found")
    if body.guests > room.capacity:
        raise HTTPException(status_code=422, detail="Guest count exceeds room capacity")
    booking = Booking(
        user_id=user.id, room_id=room.id, check_in=body.check_in, check_out=body.check_out,
        guests=body.guests, total_amount=calculate_price(room.nightly_rate, body.check_in, body.check_out),
        currency=room.currency, status=BookingStatus.pending,
    )
    db.add(booking)
    commit_or_conflict(db, "Room is unavailable for the selected dates")
    return booking


@router.get("/bookings", response_model=list[BookingOut], tags=["Bookings"])
def my_bookings(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Booking).where(Booking.user_id == user.id)
                      .order_by(Booking.created_at.desc(), Booking.id.desc()).limit(limit).offset(offset)).all()


def owned_booking(booking_id: uuid.UUID, db: Session, user: User) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or (booking.user_id != user.id and user.role.value != "admin"):
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.get("/bookings/{booking_id}", response_model=BookingOut, tags=["Bookings"])
def booking_detail(booking_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return owned_booking(booking_id, db, user)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut, tags=["Bookings"])
def cancel_booking(booking_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None or (booking.user_id != user.id and user.role.value != "admin"):
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status == BookingStatus.cancelled:
        return booking
    if booking.status == BookingStatus.confirmed:
        raise HTTPException(status_code=409, detail="Paid bookings require a refund workflow; cancellation unavailable")
    booking.status = BookingStatus.cancelled
    db.commit()
    return booking


@router.post("/bookings/{booking_id}/payments", response_model=PaymentOut, status_code=201, tags=["Payments"])
def simulate_payment(booking_id: uuid.UUID, body: PaymentIn, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
    if booking is None or (booking.user_id != user.id and user.role.value != "admin"):
        raise HTTPException(status_code=404, detail="Booking not found")
    payment = db.scalar(select(Payment).where(Payment.booking_id == booking_id))
    if payment:
        if payment.status == PaymentStatus.succeeded:
            response.status_code = 200
            return payment
        raise HTTPException(status_code=409, detail="Previous payment failed; retry not supported in MVP")
    if booking.status != BookingStatus.pending:
        raise HTTPException(status_code=409, detail="Only pending bookings can be paid")
    payment = Payment(booking_id=booking.id, amount=booking.total_amount, currency=booking.currency,
                      status=PaymentStatus.succeeded if body.simulate_success else PaymentStatus.failed)
    db.add(payment)
    if body.simulate_success:
        booking.status = BookingStatus.confirmed
    db.commit()
    return payment


@router.get("/admin/bookings", response_model=list[BookingOut], tags=["Administration"])
def all_bookings(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.scalars(select(Booking).order_by(Booking.created_at.desc(), Booking.id.desc())
                      .limit(limit).offset(offset)).all()
