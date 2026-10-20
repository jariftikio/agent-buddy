"""The webhook must answer Telegram before doing any slow work.

Telegram stops waiting after a while and redelivers the update, so a handler that
runs the model chain inline either replies twice or -- once the worker is killed
mid-request -- not at all.
"""
import app.main as main


def _app(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(main, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    return main.create_app(testing=False)


def _post(client, text="growth plan please", chat_id=42):
    return client.post(
        "/api/webhook/telegram",
        json={"message": {"message_id": 1, "text": text, "chat": {"id": chat_id}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
    )


def test_webhook_acknowledges_before_calling_the_model(monkeypatch):
    submitted = []
    monkeypatch.setattr(main._executor, "submit", lambda *a, **k: submitted.append(a))
    monkeypatch.setattr(
        main, "complete", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("the model must not run inside the request")
        ),
    )

    response = _post(_app(monkeypatch).test_client())

    assert response.status_code == 200
    assert response.get_json()["status"] == "accepted"
    assert len(submitted) == 1
    # chat_id, text and the photo file_id are captured for the background half.
    assert submitted[0][2] == 42
    assert submitted[0][3] == "growth plan please"


def test_queued_work_sends_the_reply(monkeypatch):
    """The background half is what actually answers the user."""
    sent = []
    monkeypatch.setattr(
        main, "_build_reply", lambda *a, **k: "the answer"
    )
    monkeypatch.setattr(
        main, "_dispatch_reply", lambda chat_id, text: sent.append((chat_id, text)) or ("sent", None)
    )

    main._process_update(object(), 42, "question", "", "")

    assert sent == [(42, "the answer")]


def test_a_failed_reply_does_not_leak_a_pending_slot(monkeypatch):
    """Otherwise repeated failures silently fill the queue and shed real updates."""
    monkeypatch.setattr(
        main, "_build_reply", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    before = main._pending
    main._pending = before + 1

    main._process_update(object(), 42, "question", "", "")

    assert main._pending == before


def test_a_full_backlog_still_answers_the_sender(monkeypatch):
    sent = []
    monkeypatch.setenv("WEBHOOK_MAX_PENDING", "1")
    monkeypatch.setattr(
        main, "_dispatch_reply", lambda chat_id, text: sent.append((chat_id, text)) or ("sent", None)
    )
    monkeypatch.setattr(
        main._executor, "submit", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("a full backlog must not queue more work")
        ),
    )
    monkeypatch.setattr(main, "_pending", 1)

    response = _post(_app(monkeypatch).test_client())

    assert response.status_code == 200
    assert response.get_json()["status"] == "busy"
    assert sent == [(42, main.BUSY_REPLY)]


def test_photo_download_failure_is_reported_not_silent(monkeypatch):
    monkeypatch.setattr(main, "fetch_telegram_photo", lambda _: None)

    reply = main._build_reply(object(), "", "file-123", "")

    assert reply == main.PHOTO_ERROR_REPLY


def test_unreachable_storage_still_gets_a_reply(monkeypatch):
    """A dead DATABASE_URL used to raise past the reply, leaving the user with silence."""
    class Broken:
        def handle_message(self, _):
            raise RuntimeError("could not connect to server")

    reply = main._build_reply(Broken(), "Add lead: XYZ Traders", "", "")

    assert reply == main.STORAGE_ERROR_REPLY
