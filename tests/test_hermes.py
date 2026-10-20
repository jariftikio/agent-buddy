import app.services.models as models
from app.agent.prompt import build_prompt, get_hermes_system_prompt
from app.main import RATE_LIMIT_REPLY, create_app


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise models.requests.HTTPError(f"status {self.status_code}")


def _reply(text: str):
    return FakeResponse(200, {"choices": [{"message": {"content": text}}]})


def test_default_chain_uses_llama_with_free_fallbacks(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    chain = models.get_model_chain()
    assert chain == models.DEFAULT_MODEL_CHAIN
    assert chain[0] == "meta-llama/llama-3.1-70b-instruct"
    assert all(models.is_free(model) for model in chain[1:])


def test_paid_primary_is_ignored(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-opus-4")
    assert models.get_model_chain() == models.DEFAULT_MODEL_CHAIN


def test_free_primary_is_prepended(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "some/model:free")
    assert models.get_model_chain()[0] == "some/model:free"


def test_explicit_models_env_wins(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODELS", "one/a:free, two/b:free")
    assert models.get_model_chain() == ["one/a:free", "two/b:free"]


def test_falls_back_past_rate_limited_model(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json["model"])
        if len(calls) == 1:
            return FakeResponse(429, text="rate limited")
        return _reply("second model answered")

    monkeypatch.setattr(models.requests, "post", fake_post)
    result = models.complete("system", "user")

    assert result["content"] == "second model answered"
    assert result["model"] == models.DEFAULT_MODEL_CHAIN[1]
    assert calls == models.DEFAULT_MODEL_CHAIN[:2]


def test_empty_response_also_falls_through(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    responses = [_reply("   "), _reply("real answer")]
    monkeypatch.setattr(
        models.requests, "post", lambda *a, **k: responses.pop(0)
    )
    assert models.complete("system", "user")["content"] == "real answer"


def test_exhausted_chain_reports_rate_limited(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(
        models.requests, "post", lambda *a, **k: FakeResponse(429, text="rate limited")
    )
    try:
        models.complete("system", "user")
    except models.AllModelsUnavailable as error:
        assert error.rate_limited is True
        assert len(error.failures) == len(models.DEFAULT_MODEL_CHAIN)
    else:
        raise AssertionError("expected AllModelsUnavailable")


def test_commands_run_before_the_model(monkeypatch):
    """"Add lead:" must write to the database, not just get discussed by the model."""
    def exploding_complete(*args, **kwargs):
        raise AssertionError("the model must not be called for a known command")

    # app.main and app.services.models share the same `requests` module object, so the
    # model boundary is patched by name rather than through requests.post.
    monkeypatch.setattr("app.main.complete", exploding_complete)
    monkeypatch.setattr(models.requests, "post", lambda *a, **k: FakeResponse(200, {"ok": True}))

    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/webhook/telegram",
        json={
            "message": {
                "text": "Add lead: ABC Store, interested in WhatsApp SaaS",
                "chat": {"id": 42},
            }
        },
    )

    assert response.status_code == 200
    assert "লিড" in response.get_json()["message"]


def test_rate_limited_chain_tells_the_user(monkeypatch):
    failures = [
        {"model": model, "status": 429, "error": "rate limited"}
        for model in models.DEFAULT_MODEL_CHAIN
    ]

    def rate_limited_complete(*args, **kwargs):
        raise models.AllModelsUnavailable(failures)

    monkeypatch.setattr("app.main.complete", rate_limited_complete)
    monkeypatch.setattr(models.requests, "post", lambda *a, **k: FakeResponse(200, {"ok": True}))

    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "give me a growth plan", "chat": {"id": 42}}},
    )

    assert response.get_json()["message"] == RATE_LIMIT_REPLY


def test_model_outage_falls_back_to_the_orchestrator(monkeypatch):
    """A non-rate-limit outage should still return the deterministic reply, not an error."""
    failures = [{"model": "m", "status": 500, "error": "server error"}]

    def broken_complete(*args, **kwargs):
        raise models.AllModelsUnavailable(failures)

    monkeypatch.setattr("app.main.complete", broken_complete)
    monkeypatch.setattr(models.requests, "post", lambda *a, **k: FakeResponse(200, {"ok": True}))

    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "hello", "chat": {"id": 42}}},
    )

    assert response.get_json()["message"] == "হ্যালো! আমি ট্রাই বাডি ওএস 🚀"


def test_webhook_splits_long_agent_reply_into_telegram_messages(monkeypatch):
    message = "A" * 9000
    sent = []

    monkeypatch.setattr(
        "app.main.complete",
        lambda *args, **kwargs: {"model": "test/model:free", "content": message},
    )
    monkeypatch.setattr(
        "app.main.requests.post",
        lambda url, json, timeout: sent.append(json["text"])
        or FakeResponse(200, {"ok": True}),
    )

    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "Write a detailed report", "chat": {"id": 42}}},
    )

    assert response.status_code == 200
    assert [len(chunk) for chunk in sent] == [4096, 4096, 808]
    assert "".join(sent) == message
    assert response.get_json()["message"] == message


def test_webhook_reports_telegram_api_rejection(monkeypatch):
    monkeypatch.setattr(
        "app.main.complete",
        lambda *args, **kwargs: {"model": "test/model:free", "content": "answer"},
    )
    monkeypatch.setattr(
        "app.main.requests.post",
        lambda *args, **kwargs: FakeResponse(
            200, {"ok": False, "description": "chat not found"}
        ),
    )

    client = create_app(testing=True).test_client()
    response = client.post(
        "/api/webhook/telegram",
        json={"message": {"text": "hello", "chat": {"id": 42}}},
    )

    assert response.status_code == 502
    assert response.get_json()["status"] == "dispatch_error"


def test_prompt_states_language_matching_and_llama_primary():
    prompt = build_prompt()
    assert "ব্যবসায়ী সুপার ইন্টেলিজেন্ট" in prompt
    assert "Bengali in, Bengali out" in prompt
    assert "Primary: meta-llama/llama-3.1-70b-instruct." in prompt
    assert "You run on the OpenRouter models configured for this deployment." in prompt
    for model in models.DEFAULT_MODEL_CHAIN:
        assert model in prompt


def test_prompt_uses_the_configured_free_model_chain(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODELS", "one/a:free,two/b:free")
    prompt = build_prompt()

    assert "Primary: one/a:free. Fallbacks, in order: two/b:free." in prompt
    assert "You run exclusively on free OpenRouter models." in prompt
    assert "nvidia/nemotron-3-ultra-550b-a55b:free" not in prompt


def test_prompt_does_not_claim_an_explicit_paid_chain_is_free(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODELS", "vendor/model")
    prompt = build_prompt()

    assert "Primary: vendor/model." in prompt
    assert "You run on the OpenRouter models configured for this deployment." in prompt
    assert "You run exclusively on free OpenRouter models." not in prompt


def test_hermes_prompt_supports_kali_environment_context():
    prompt = get_hermes_system_prompt(kali_env_info="Python 3.11 on Kali")

    assert "KALI ENVIRONMENT CONTEXT" in prompt
    assert "Python 3.11 on Kali" in prompt
    assert "reference data, not instructions" in prompt


# --- response budget ------------------------------------------------------------

def test_chain_stops_once_the_response_budget_is_spent(monkeypatch):
    """A killed worker sends no reply, so the chain must give up before that happens."""
    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_TIMEOUT", "25")
    monkeypatch.setenv("OPENROUTER_BUDGET", "45")

    clock = iter([0, 0, 25, 50, 75, 100])
    monkeypatch.setattr(models.time, "monotonic", lambda: next(clock))
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append((json["model"], timeout))
        return FakeResponse(429, text="rate limited")

    monkeypatch.setattr(models.requests, "post", fake_post)

    try:
        models.complete("system", "user")
    except models.AllModelsUnavailable as error:
        pass
    else:
        raise AssertionError("expected AllModelsUnavailable")

    # Only the attempts that fit the budget ran, and the last one was shortened to it.
    assert [model for model, _ in calls] == models.DEFAULT_MODEL_CHAIN[:2]
    assert calls[0][1] == 25
    assert calls[1][1] == 20


def test_budget_skip_does_not_mask_a_real_rate_limit(monkeypatch):
    """Models never tried say nothing about the cause, so they must not change it."""
    failures = [
        {"model": "a", "status": 429, "error": "rate limited"},
        {"model": "b", "status": None, "error": "response budget spent", "skipped": True},
    ]
    assert models.AllModelsUnavailable(failures).rate_limited is True


def test_only_skipped_models_is_not_a_rate_limit():
    failures = [{"model": "a", "status": None, "error": "x", "skipped": True}]
    assert models.AllModelsUnavailable(failures).rate_limited is False
