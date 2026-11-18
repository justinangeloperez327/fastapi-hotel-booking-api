# Hotel Booking API

Production-oriented **FastAPI + PostgreSQL** portfolio project for managing hotels, physical rooms, availability, reservations and simulated payments. API-only; interactive OpenAPI documentation is available at `/docs`.

## Features

- Guest registration, secure Argon2 password hashing, signed JWT access tokens, admin-only management routes.
- Hotel and room CRUD operations (create/update and public listing), city/name search, pagination.
- Room availability with half-open dates: `[check_in, check_out)`.
- Reservation creation with **PostgreSQL GiST exclusion constraint** preventing overlapping active reservations even under concurrent requests.
- Server-calculated price snapshots, maximum occupancy checks, cancellation of unpaid reservations.
- Simulated payment success/failure, payment deduplication and automatic booking confirmation.
- Alembic schema migration, Docker Compose, CI, Pytest, health checks.

> **Portfolio/demo payments only**. This service does not charge cards or integrate with a payment gateway. Paid reservations are intentionally non-cancellable until a refund workflow is implemented.

## Quick start

1. Copy `.env.example` to `.env` and set `JWT_SECRET` to a unique random value of at least 32 characters.
2. Run `docker compose up -d --build`.
3. Run `docker compose exec api alembic upgrade head`.
4. Create an administrator: `docker compose exec api python -m app.cli create-admin --email admin@example.com`.
5. Open `http://localhost:8000/docs`.

Alternatively use a local Python environment, PostgreSQL and `pip install -e '.[dev]'`, followed by `alembic upgrade head` and `uvicorn app.main:app --reload`.

## API

| Verb | URL | Access |
|---|---|---|
| POST | `/api/v1/auth/register` | Public |
| POST | `/api/v1/auth/login` | Public |
| GET | `/api/v1/users/me` | Authenticated |
| GET | `/api/v1/hotels` | Public |
| GET | `/api/v1/hotels/{id}` | Public |
| GET | `/api/v1/hotels/{id}/rooms` | Public |
| GET | `/api/v1/rooms/{id}/availability?check_in=2027-01-15&check_out=2027-01-18` | Public |
| POST | `/api/v1/admin/hotels` | Admin |
| PATCH | `/api/v1/admin/hotels/{id}` | Admin |
| POST | `/api/v1/admin/hotels/{id}/rooms` | Admin |
| PATCH | `/api/v1/admin/rooms/{id}` | Admin |
| POST | `/api/v1/bookings` | Authenticated |
| GET | `/api/v1/bookings` | Authenticated |
| GET | `/api/v1/bookings/{id}` | Owner or Admin |
| POST | `/api/v1/bookings/{id}/cancel` | Owner or Admin |
| POST | `/api/v1/bookings/{id}/payments` | Owner or Admin |
| GET | `/api/v1/admin/bookings` | Admin |
| GET | `/health/live`, `/health/ready` | Public |

### Example guest flow

1. `POST /api/v1/auth/register` with `name`, `email`, and `password` (min 12 chars).
2. `POST /api/v1/auth/login` with email/password and use `Authorization: Bearer <access_token>`.
3. `GET /api/v1/hotels?city=Abu%20Dhabi` and list hotel rooms.
4. `GET /api/v1/rooms/{id}/availability?check_in=2027-01-15&check_out=2027-01-18`.
5. `POST /api/v1/bookings` with `{ "room_id": "<UUID>", "check_in": "2027-01-15", "check_out": "2027-01-18", "guests": 2 }`.
6. `POST /api/v1/bookings/{id}/payments` with `{ "simulate_success": true }` to mark paid/confirmed.

## Architecture and consistency

A modular monolith separates REST routing (`app/api`), Pydantic contracts (`app/schemas`), SQLAlchemy persistence (`app/models`), business rules (`app/services`), and authentication (`app/core`). PostgreSQL is the source of truth.

Availability reads provide an informational snapshot and can become stale. **The final overlapping-reservations guarantee is the database exclusion constraint**, not an application-level read-before-write check. `pending` and `confirmed` reservations block overlapping bookings; `cancelled` does not. Two adjacent bookings where one checks out on the other's check-in date are allowed. Price, currency and guest count are validated and snapshotted at booking creation.

The simulated payment endpoint locks its booking row and ensures one payment record per booking. A repeated successful payment request returns the existing payment. Failed simulated payments are recorded, but reattempting after a failure is deliberately not supported in v1.

## Commands

```bash
pip install -e '.[dev]'
alembic upgrade head
pytest -q
ruff check .
```

## Security and deployment notes

- Set a high-entropy JWT secret in the deployment environment; never commit `.env`.
- Keep PostgreSQL private, enforce HTTPS, use a trusted reverse proxy, and configure access logging/rate limiting at the edge before any public deployment.
- Admin users must be created through the interactive CLI; public registration always creates guests.
- This MVP intentionally excludes real payments, refunds, room inventory by category, multi-currency conversion, email delivery, and check-in operations.
- For public production use, add refresh-token/session revocation, comprehensive audit logs, centralized error reporting, periodic backups, retention rules, and payment-provider webhook verification.
