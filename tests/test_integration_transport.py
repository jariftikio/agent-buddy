import os

import pytest

from telegram_client import TelegramClient


@pytest.mark.integration
def test_send_message_integration_smoke():
    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        pytest.skip("Telegram credentials are not configured")

    client = TelegramClient()
    response = client.send_message(os.getenv("TELEGRAM_CHAT_ID", ""), "Hello from integration test")

    assert response["ok"] is True


def test_send_message_splits_long_text(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    sent = []

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"ok": True}

    def fake_post(url, json, timeout):
        sent.append(json["text"])
        return FakeResponse()

    monkeypatch.setattr("telegram_client.requests.post", fake_post)

    result = TelegramClient().send_message("42", "B" * 5000)

    assert result["ok"] is True
    assert [len(chunk) for chunk in sent] == [4096, 904]
