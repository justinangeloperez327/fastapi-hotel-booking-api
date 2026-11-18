"""Integration suite requires an isolated PostgreSQL database and applied migrations.

WARNING: Tests TRUNCATE all application tables. Never target a shared or production database.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def clear_database():
    database_url = os.environ["DATABASE_URL"]
    if "localhost" not in database_url and "127.0.0.1" not in database_url:
        pytest.skip("Destructive integration tests require localhost PostgreSQL")
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE payments, bookings, rooms, hotels, users RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture
def client():
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as api_client:
        yield api_client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def guest(client):
    assert client.post("/api/v1/auth/register", json={
        "name": "Guest One", "email": "guest@example.com", "password": "secure-password-123"
    }).status_code == 201
    login = client.post("/api/v1/auth/login", json={
        "email": "guest@example.com", "password": "secure-password-123"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client):
    from app.core.security import hash_password
    from app.models import Role, User

    engine = create_engine(os.environ["DATABASE_URL"])
    with sessionmaker(engine)() as db:
        db.add(User(name="Admin", email="admin@example.com", role=Role.admin,
                    password_hash=hash_password("secure-password-456")))
        db.commit()
    engine.dispose()
    token = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": "secure-password-456"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def room(client, admin):
    hotel_response = client.post("/api/v1/admin/hotels", headers=admin, json={
        "name": "Harbor Hotel", "city": "Abu Dhabi", "address": "Corniche Road",
        "description": "Waterfront hotel"
    })
    assert hotel_response.status_code == 201
    hotel = hotel_response.json()
    response = client.post(f"/api/v1/admin/hotels/{hotel['id']}/rooms", headers=admin, json={
        "number": "101", "room_type": "Deluxe", "capacity": 2,
        "nightly_rate": "150.00", "currency": "AED"
    })
    assert response.status_code == 201, response.text
    return response.json()
