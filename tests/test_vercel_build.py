import os
from unittest.mock import patch

import pytest

from scripts.vercel_build import main


def test_preview_does_not_migrate():
    with patch.dict(os.environ, {"VERCEL_ENV": "preview"}, clear=True):
        with patch("scripts.vercel_build.run") as run:
            main()
    run.assert_called_once_with("-m", "pip", "install", "-e", ".")


def test_production_requires_database():
    with patch.dict(os.environ, {"VERCEL_ENV": "production"}, clear=True):
        with patch("scripts.vercel_build.run"):
            with pytest.raises(SystemExit, match="DATABASE_URL"):
                main()


def test_production_runs_migrations():
    env = {"VERCEL_ENV": "production", "DATABASE_URL": "postgresql+psycopg://example",
           "JWT_SECRET": "x" * 40}
    with patch.dict(os.environ, env, clear=True):
        with patch("scripts.vercel_build.run") as run:
            main()
    run.assert_any_call("-m", "alembic", "upgrade", "head")
