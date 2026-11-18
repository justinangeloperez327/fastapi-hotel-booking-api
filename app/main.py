from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()
if len(settings.jwt_secret) < 32:
    raise RuntimeError("JWT_SECRET must contain at least 32 characters")

app = FastAPI(title="Hotel Booking API", version="1.0.0", description="Hotel catalog, availability, reservations, and simulated payments.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=False, allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Authorization", "Content-Type"])
app.include_router(router)


@app.get("/health/live", tags=["Health"])
def liveness():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"])
def readiness(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
