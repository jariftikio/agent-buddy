from app.main import create_app
from app.agent.orchestrator import AgentOrchestrator
from app.db.session import init_db


def test_webhook_accepts_explicit_lead_command():
    app = create_app(testing=True)
    client = app.test_client()
    response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "Add lead: ABC Store, interested in WhatsApp SaaS"}},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "লিড" in payload["message"]


def test_agent_adds_lead():
    init_db()
    orchestrator = AgentOrchestrator()

    lead_response = orchestrator.handle_message("Add lead: ABC Store, interested in WhatsApp SaaS")
    assert lead_response["ok"] is True
    assert "ABC Store" in lead_response["message"]


def test_hello_returns_tri_buddy_greeting():
    orchestrator = AgentOrchestrator()

    response = orchestrator.handle_message("Hello")

    assert response["ok"] is True
    assert response["message"] == "হ্যালো! আমি ট্রাই বাডি ওএস 🚀"
