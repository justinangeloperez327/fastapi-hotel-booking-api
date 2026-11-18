"""Run schema migrations at production build time, never at request time."""
import os
import subprocess
import sys


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True)


def main() -> None:
    run("-m", "pip", "install", "-e", ".")
    if os.getenv("VERCEL_ENV") != "production":
        print("Skipping migrations outside production")
        return
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required for production migrations")
    if len(os.getenv("JWT_SECRET", "")) < 32:
        raise SystemExit("JWT_SECRET must contain at least 32 characters")
    run("-m", "alembic", "upgrade", "head")


if __name__ == "__main__":
    main()
