import logging
import os
import time
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

# Llama 3.1 70B always answers first. It is paid, so it may incur OpenRouter charges
# on every message -- that is the deliberate trade for the best model answering before
# any free one gets a turn. Nothing in the environment can displace it; see
# get_model_chain().
PRIMARY_MODEL = "meta-llama/llama-3.1-70b-instruct"

# Tried in order, only after the primary fails or is unavailable. All free.
# thinkingmachines/inkling:free is deliberately absent: OpenRouter gates it behind
# "agentic harnesses" and returns a permanent 403 to a plain webhook like this one,
# so including it would only add a wasted round-trip to every fallback.
DEFAULT_FALLBACK_CHAIN: List[str] = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
]

DEFAULT_MODEL_CHAIN: List[str] = [PRIMARY_MODEL, *DEFAULT_FALLBACK_CHAIN]

# Statuses that mean "this model is unavailable right now, try the next one"
# rather than "the request itself is malformed".
FALLBACK_STATUSES = {402, 403, 408, 429, 500, 502, 503, 504}

# Seconds the whole chain may spend before it has to give up and let the caller
# answer. Walking four models at OPENROUTER_TIMEOUT each outlasts both the
# gunicorn worker timeout and Telegram's wait for the webhook, and a killed
# worker sends no reply at all -- so a partial answer beats an exhausted one.
DEFAULT_BUDGET = 45

# A remaining slice shorter than this cannot complete a model call, so spending
# it only delays the fallback reply.
MIN_ATTEMPT_SECONDS = 5


class AllModelsUnavailable(RuntimeError):
    """Every configured model in the chain failed."""

    def __init__(self, failures: List[Dict[str, Any]]) -> None:
        self.failures = failures
        detail = "; ".join(f"{item['model']}: {item['error']}" for item in failures)
        super().__init__(f"all configured models unavailable ({detail})")

    @property
    def rate_limited(self) -> bool:
        """True when every model that was actually tried was rate limited or out of credit.

        Models skipped because the response budget ran out say nothing about why the
        chain failed, so counting them would hide a genuine rate limit behind the
        vaguer fallback reply.
        """
        attempted = [item for item in self.failures if not item.get("skipped")]
        if not attempted:
            return False
        return all(item.get("status") in {402, 429} for item in attempted)


def is_free(model: str) -> bool:
    """A model is free-tier if OpenRouter marks it with the ":free" suffix."""
    return model.endswith(":free") or model == "openrouter/free"


def get_model_chain() -> List[str]:
    """Resolve the model chain. PRIMARY_MODEL is always first.

    The environment configures the *fallbacks*, never the primary. Llama 3.1 70B is
    pinned at the head and deduplicated out of the rest, so no configuration -- and
    no stale value left in a dashboard -- can quietly demote it behind a free model
    and leave the best model answering second.

    OPENROUTER_MODELS replaces the fallback list wholesale. OPENROUTER_MODEL adds a
    single free model as the *first* fallback; it used to be the primary, which is no
    longer something the environment decides. A paid value there is still ignored,
    because an unreviewed paid model should not join the chain by accident.
    """
    configured = os.getenv("OPENROUTER_MODELS", "").strip()
    parsed = [model.strip() for model in configured.split(",") if model.strip()]
    if parsed:
        rest = parsed
    else:
        # Either unset, or set to something that parses to nothing (a stray comma). A
        # misconfigured value should not strip the primary of every fallback.
        rest = list(DEFAULT_FALLBACK_CHAIN)
        extra = os.getenv("OPENROUTER_MODEL", "").strip()
        if extra and extra != PRIMARY_MODEL and extra not in rest:
            if is_free(extra):
                rest = [extra, *rest]
            else:
                logger.warning(
                    "Ignoring paid OPENROUTER_MODEL=%s; paid models must be listed "
                    "explicitly in OPENROUTER_MODELS.",
                    extra,
                )

    return [PRIMARY_MODEL, *[model for model in rest if model != PRIMARY_MODEL]]


def _base_url() -> str:
    return os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1").rstrip("/")


def _timeout() -> int:
    try:
        return int(os.getenv("OPENROUTER_TIMEOUT", "25"))
    except ValueError:
        return 25


def budget(default: int = DEFAULT_BUDGET) -> int:
    try:
        return max(MIN_ATTEMPT_SECONDS, int(os.getenv("OPENROUTER_BUDGET", str(default))))
    except ValueError:
        return default


def attempt_timeout(deadline: float, per_model: int) -> float:
    """Seconds this attempt may take, or 0 when the budget is spent."""
    remaining = deadline - time.monotonic()
    if remaining < MIN_ATTEMPT_SECONDS:
        return 0.0
    return min(float(per_model), remaining)


def complete(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """Call each model in the chain until one answers.

    Returns {"model": <model that answered>, "content": <reply>}.
    Raises AllModelsUnavailable if the whole chain fails.
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}",
        "HTTP-Referer": os.getenv("APP_URL", "https://onrender.com"),
        "X-Title": "Hermes",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    failures: List[Dict[str, Any]] = []
    deadline = time.monotonic() + budget()
    per_model = _timeout()

    for model in get_model_chain():
        timeout = attempt_timeout(deadline, per_model)
        if not timeout:
            logger.warning(
                "Response budget spent, not trying remaining models | last=%s", model
            )
            failures.append(
                {
                    "model": model,
                    "status": None,
                    "error": "response budget spent",
                    "skipped": True,
                }
            )
            break

        try:
            response = requests.post(
                f"{_base_url()}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages},
                timeout=timeout,
            )

            if response.status_code in FALLBACK_STATUSES:
                logger.warning(
                    "Model unavailable, trying next | model=%s status=%s",
                    model,
                    response.status_code,
                )
                failures.append(
                    {
                        "model": model,
                        "status": response.status_code,
                        "error": response.text[:200],
                    }
                )
                continue

            response.raise_for_status()
            content = (
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )

            if not content:
                failures.append({"model": model, "status": None, "error": "empty response"})
                continue

            logger.info("Model answered | model=%s", model)
            return {"model": model, "content": content}

        except requests.RequestException as error:
            logger.warning("Model request failed, trying next | model=%s error=%s", model, error)
            failures.append({"model": model, "status": None, "error": str(error)[:200]})

    raise AllModelsUnavailable(failures)
