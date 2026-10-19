from app.main import create_app
from app.agent.orchestrator import AgentOrchestrator
from app.db.session import init_db


def test_telegram_webhook_status_reports_registration_requirements(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://example.onrender.com")

    response = create_app(testing=True).test_client().get("/api/webhook/telegram")

    assert response.status_code == 200
    assert response.get_json()["token_configured"] is True
    assert response.get_json()["secret_configured"] is False
    assert response.get_json()["public_url_configured"] is True
    assert response.get_json()["registration_ready"] is False
    assert response.get_json()["registration_status"] == "not_attempted"


def test_team_command_and_approval_flow():
    init_db()
    app = create_app(testing=True)
    client = app.test_client()

    task_response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "Assign Rahim to design the homepage"}},
    )
    assert task_response.status_code == 200
    assert "পেয়েছি" in task_response.get_json()["message"]

    approval_response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "Draft a proposal email for ABC Store"}},
    )
    assert approval_response.status_code == 200
    payload = approval_response.get_json()
    assert payload["ok"] is True
    assert "অনুমোদন" in payload["message"]


def test_memory_round_trip():
    init_db()
    orchestrator = AgentOrchestrator()
    orchestrator.handle_message("Remember that my default SaaS package is 299 BDT")
    memory_response = orchestrator.handle_message("What do you know about my business?")
    assert memory_response["ok"] is True
    assert "299 BDT" in memory_response["message"]
