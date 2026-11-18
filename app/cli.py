import argparse
import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Role, User


def main():
    parser = argparse.ArgumentParser(description="Hotel API administration")
    parser.add_argument("command", choices=["create-admin"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    password = getpass.getpass("Admin password (minimum 12 characters): ")
    if len(password) < 12:
        parser.error("Password must contain at least 12 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == args.email.lower())):
            parser.error("Email already registered")
        db.add(User(name=args.name, email=args.email.lower(), password_hash=hash_password(password), role=Role.admin))
        db.commit()
    print("Admin created")


if __name__ == "__main__":
    main()
