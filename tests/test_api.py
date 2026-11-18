from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

from app.services.bookings import calculate_price


def dates(start=14, nights=3):
    begin = date.today() + timedelta(days=start)
    return begin.isoformat(), (begin + timedelta(days=nights)).isoformat()


def booking_payload(room_id, start=14, nights=3, guests=2):
    check_in, check_out = dates(start, nights)
    return {"room_id": room_id, "check_in": check_in, "check_out": check_out, "guests": guests}


def test_price_calculation():
    check_in = date(2027, 1, 15)
    assert calculate_price(Decimal("99.99"), check_in, date(2027, 1, 18)) == Decimal("299.97")


def test_public_catalog_and_admin_security(client, guest, admin, room):
    response = client.get("/api/v1/hotels?city=Abu%20Dhabi")
    assert response.status_code == 200
    hotels = response.json()
    assert len(hotels) == 1
    assert client.get(f"/api/v1/hotels/{hotels[0]['id']}/rooms").json()[0]["id"] == room["id"]
    assert client.post("/api/v1/admin/hotels", headers=guest,
                       json={"name": "Not allowed", "city": "Dubai", "address": "Anywhere"}).status_code == 403
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/users/me", headers=guest).json()["role"] == "guest"


def test_booking_availability_and_adjacent_stays(client, guest, room):
    payload = booking_payload(room["id"])
    availability_url = f"/api/v1/rooms/{room['id']}/availability"
    initial = client.get(availability_url, params={"check_in": payload["check_in"], "check_out": payload["check_out"]})
    assert initial.json()["available"] is True
    booking = client.post("/api/v1/bookings", headers=guest, json=payload)
    assert booking.status_code == 201, booking.text
    assert booking.json()["total_amount"] == "450.00"
    assert booking.json()["status"] == "pending"
    conflict = client.post("/api/v1/bookings", headers=guest, json=payload)
    assert conflict.status_code == 409
    assert client.get(availability_url, params={"check_in": payload["check_in"], "check_out": payload["check_out"]}).json()["available"] is False
    assert client.post("/api/v1/bookings", headers=guest, json=booking_payload(room["id"], start=17)).status_code == 201
    assert client.post("/api/v1/bookings", headers=guest, json=booking_payload(room["id"], start=15)).status_code == 409
    assert client.post(f"/api/v1/bookings/{booking.json()['id']}/cancel", headers=guest).status_code == 200
    assert client.post("/api/v1/bookings", headers=guest, json=payload).status_code == 201


def test_validation_and_payment(client, guest, room):
    payload = booking_payload(room["id"])
    assert client.post("/api/v1/bookings", headers=guest, json={**payload, "guests": 3}).status_code == 422
    assert client.post("/api/v1/bookings", headers=guest, json={**payload, "check_out": payload["check_in"]}).status_code == 422
    booking = client.post("/api/v1/bookings", headers=guest, json=payload).json()
    payment_url = f"/api/v1/bookings/{booking['id']}/payments"
    first = client.post(payment_url, headers=guest, json={"simulate_success": True})
    assert first.status_code == 201
    assert first.json()["status"] == "succeeded"
    repeat = client.post(payment_url, headers=guest, json={"simulate_success": True})
    assert repeat.json()["id"] == first.json()["id"]
    assert client.get(f"/api/v1/bookings/{booking['id']}", headers=guest).json()["status"] == "confirmed"
    assert client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=guest).status_code == 409


def test_failed_payment_is_not_retried(client, guest, room):
    booking = client.post("/api/v1/bookings", headers=guest, json=booking_payload(room["id"])).json()
    url = f"/api/v1/bookings/{booking['id']}/payments"
    assert client.post(url, headers=guest, json={"simulate_success": False}).json()["status"] == "failed"
    assert client.post(url, headers=guest, json={"simulate_success": True}).status_code == 409
    assert client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=guest).status_code == 200


def test_booking_privacy(client, guest, room):
    booking = client.post("/api/v1/bookings", headers=guest, json=booking_payload(room["id"])).json()
    client.post("/api/v1/auth/register", json={"name": "Guest Two", "email": "two@example.com", "password": "secure-password-123"})
    token = client.post("/api/v1/auth/login", json={"email": "two@example.com", "password": "secure-password-123"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/v1/bookings/{booking['id']}", headers=other).status_code == 404
    assert client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=other).status_code == 404
    assert client.post(f"/api/v1/bookings/{booking['id']}/payments", headers=other, json={}).status_code == 404
    assert client.get("/api/v1/bookings", headers=other).json() == []


def test_concurrent_booking_only_one_wins(client, guest, room):
    payload = booking_payload(room["id"])

    def reserve(_):
        # Each TestClient request obtains its own DB session/transaction.
        return client.post("/api/v1/bookings", headers=guest, json=payload).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(reserve, range(2)))
    assert statuses == [201, 409]
