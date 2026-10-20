"""Postgres backend tests.

Skipped unless TEST_DATABASE_URL points at a database you are happy to have
tables created in. They run against a dedicated schema, never public.
"""
import importlib
import os

import pytest

TEST_DB = os.getenv("TEST_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL not set")

SCHEMA = "tri_buddy_test"


@pytest.fixture()
def pg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    monkeypatch.setenv("DB_SCHEMA", SCHEMA)

    import app.db.session as session

    importlib.reload(session)

    # Start from nothing so each test sees a clean schema.
    with session.get_db_connection() as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
        conn.execute(f'CREATE SCHEMA "{SCHEMA}"')
        conn.commit()

    session.init_db()

    for module in ("app.tools.leads", "app.services.memory"):
        importlib.reload(importlib.import_module(module))

    yield session

    # Re-pin the schema before connecting. This fixture shares one function-scoped
    # monkeypatch with the test, and finalizers run before monkeypatch undoes the
    # environment -- so a test that deliberately leaves DB_SCHEMA invalid (which is
    # the whole point of the refusal tests) would otherwise make schema_name() raise
    # in here, turning a passing test into a teardown error and leaking the schema.
    monkeypatch.setenv("DB_SCHEMA", SCHEMA)
    monkeypatch.delenv("DB_ALLOW_PUBLIC_SCHEMA", raising=False)

    with session.get_db_connection() as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
        conn.commit()
    importlib.reload(session)


def test_tables_land_in_our_schema_only(pg):
    with pg.get_db_connection() as conn:
        ours = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            (SCHEMA,)).fetchall()}
    assert {"leads", "memories"} <= ours
    assert "seo_audits" not in ours


def test_nothing_is_created_in_public(pg):
    with pg.get_db_connection() as conn:
        public = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()}
    assert not ({"leads", "memories"} & public), (
        "the bot must never create its tables in the public schema"
    )


def test_public_schema_is_refused(pg, monkeypatch):
    monkeypatch.setenv("DB_SCHEMA", "public")
    with pytest.raises(ValueError, match="Refusing to use the public schema"):
        pg.schema_name()


def test_public_schema_override_is_possible(pg, monkeypatch):
    monkeypatch.setenv("DB_SCHEMA", "public")
    monkeypatch.setenv("DB_ALLOW_PUBLIC_SCHEMA", "1")
    assert pg.schema_name() == "public"


def test_schema_name_rejects_injection(pg, monkeypatch):
    monkeypatch.setenv("DB_SCHEMA", 'x"; DROP SCHEMA public CASCADE; --')
    with pytest.raises(ValueError, match="Invalid DB_SCHEMA"):
        pg.schema_name()


def test_init_db_is_idempotent_and_keeps_rows(pg):
    from app.tools.leads import create_lead, recent_leads

    create_lead("Rahim", "01712345678", "Garments", "", 80, "telegram")
    pg.init_db()
    pg.init_db()
    assert len(recent_leads(10)) == 1, "re-running init_db must not drop rows"


def test_lead_ref_is_generated(pg):
    from app.tools.leads import create_lead

    assert create_lead("Rahim", None, None, "", 55, "telegram")["lead_ref"] == "LD-00001"


def test_memory_upsert_replaces(pg):
    from app.services.memory import MemoryService

    memory = MemoryService()
    memory.remember("website", "old.example")
    memory.remember("website", "https://example.com")
    assert memory.recall("website") == "https://example.com"
    assert len([m for m in memory.search("") if m["key"] == "website"]) == 1


def test_bengali_round_trips(pg):
    from app.services.memory import MemoryService

    memory = MemoryService()
    memory.remember("tagline", "বিক্রি ও বিলিং সহজ")
    assert memory.recall("tagline") == "বিক্রি ও বিলিং সহজ"


def test_duplicate_lead_detection(pg):
    from app.tools.leads import create_lead, lead_exists

    create_lead("Rahim", "01712345678", "Garments", "", 80, "telegram")
    assert lead_exists("01712345678", "Someone") is True
    assert lead_exists("01999999999", "Nobody") is False
