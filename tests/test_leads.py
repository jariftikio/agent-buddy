import importlib
import tempfile

import pytest

from app.tools.leads import (
    create_lead,
    find_phone,
    lead_exists,
    parse_lead_command,
    recent_leads,
    score_lead,
)


@pytest.fixture()
def db(monkeypatch):
    monkeypatch.setenv("DB_PATH", tempfile.mktemp(suffix=".db"))
    import app.db.session as session

    importlib.reload(session)
    importlib.reload(__import__("app.tools.leads", fromlist=["x"]))
    session.init_db()
    return session


@pytest.mark.parametrize("text,expected", [
    ("call me on 01712345678", "01712345678"),
    ("+8801812345678", "+8801812345678"),
    ("my number is 017-1234-5678", "01712345678"),
    ("no number here", None),
    ("1234", None),
    ("02233445566", None),
])
def test_phone_detection(text, expected):
    assert find_phone(text) == expected


def test_parse_handles_reordered_fields():
    parsed = parse_lead_command("01712345678 - করিম - মুদি দোকান")
    assert parsed["phone"] == "01712345678"
    assert parsed["name"] == "করিম"
    assert parsed["business_type"] == "মুদি দোকান"


def test_parse_without_phone():
    parsed = parse_lead_command("Rahim - Garments")
    assert parsed["name"] == "Rahim"
    assert parsed["phone"] is None


def test_scoring_matches_the_rubric():
    assert score_lead({"has_business": True}) == 30
    assert score_lead({"asked_pricing": True}) == 25
    assert score_lead({"phone": "01712345678"}) == 25
    assert score_lead({"buying_intent": True}) == 20
    assert score_lead({
        "has_business": True,
        "asked_pricing": True,
        "phone": "01",
        "buying_intent": True,
    }) == 100


def test_score_never_exceeds_100():
    assert score_lead({
        "has_business": 1,
        "asked_pricing": 1,
        "phone": "1",
        "buying_intent": 1,
    }) <= 100


def test_lead_is_persisted_with_a_reference(db):
    lead = create_lead("Rahim", "01712345678", "Garments", "wants trial", 80, "telegram")
    assert lead["lead_ref"].startswith("LD-")
    stored = recent_leads(1)[0]
    assert stored["name"] == "Rahim"
    assert stored["score"] == 80
    assert stored["source"] == "telegram"


def test_duplicate_phone_is_detected(db):
    create_lead("Rahim", "01712345678", "Garments", "", 80, "telegram")
    assert lead_exists("01712345678", "Someone Else") is True
    assert lead_exists("01999999999", "Nobody") is False


def test_legacy_add_lead_still_works(db):
    from app.tools.leads import add_lead

    lead = add_lead("ABC Store, interested in WhatsApp SaaS")
    assert lead["name"] == "ABC Store"
