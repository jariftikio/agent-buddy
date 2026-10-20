"""Test-wide isolation from whatever is in the developer's .env.

load_dotenv() runs at import time, so a real DATABASE_URL in .env silently
redirected the whole suite at the production database -- which meant the tests
passed only as long as no .env existed, and failed with connection errors as
soon as one did. The SQLite backend is the documented default for tests;
tests/test_postgres.py opts back in explicitly through its own fixture.
"""
import pytest


@pytest.fixture(autouse=True)
def sqlite_backend(monkeypatch):
    # Autouse fixtures are set up before explicitly requested ones, so the
    # Postgres fixture in test_postgres.py still overrides this.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
