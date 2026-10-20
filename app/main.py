import atexit
import hmac
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, request

from app.api.health import health_bp
from app.agent.orchestrator import AgentOrchestrator
from app.agent.prompt import build_prompt
from app.db.session import init_db
from app.services.models import AllModelsUnavailable, complete
from app.services.vision import describe, fetch_telegram_photo
from app.tools.web import as_context, fetch_pages, find_urls
from telegram_client import split_telegram_message

load_dotenv()


def configure_logging() -> None:
    """Give the app's loggers a handler, at INFO by default.

    Nothing configured the root logger before: gunicorn sets up only its own
    "gunicorn.error" and "gunicorn.access" loggers, and Flask does not touch the
    root either. So every logging.getLogger(__name__) in this package had no
    handler at all and fell through to logging.lastResort, which drops anything
    below WARNING -- "Update queued", "Command handled", "Agent reply | model=...",
    "Model answered" and "Telegram dispatch success" were all silently discarded in
    production. Failures were visible, confirmations never were, which is backwards
    for a bot whose replies are sent from a background worker nobody is waiting on.

    Under gunicorn the app reuses gunicorn's own handlers, so these lines land in
    --error-logfile with the same formatting instead of a second, differently
    formatted stream. gunicorn marks that logger propagate=False, so reusing its
    handlers here does not double up its own output.
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root = logging.getLogger()
    gunicorn_handlers = logging.getLogger("gunicorn.error").handlers

    if gunicorn_handlers:
        root.handlers = gunicorn_handlers
    elif not root.handlers:
        logging.basicConfig(format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    root.setLevel(level)


configure_logging()

logger = logging.getLogger(__name__)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1").rstrip("/")

RATE_LIMIT_REPLY = (
    "মডেলগুলো এখন quota বা rate limit-এর কারণে unavailable। কয়েক মিনিট পরে আবার চেষ্টা করুন, "
    "অথবা ছোট করে প্রশ্নটি পাঠান।\n\n"
    "The configured models are temporarily unavailable due to quota or rate limits. "
    "Please try again in a few minutes, "
    "or send a shorter request."
)
GENERIC_ERROR_REPLY = "I ran into an issue and could not process that request right now."
PHOTO_ERROR_REPLY = "I could not download that image from Telegram. Please try sending it again."
STORAGE_ERROR_REPLY = (
    "ডেটাবেস এখন পাওয়া যাচ্ছে না, তাই এটি সেভ করা যায়নি। DATABASE_URL ঠিক আছে কিনা দেখুন।\n\n"
    "Storage is unreachable, so that could not be saved. Check DATABASE_URL -- "
    "nothing was written."
)
BUSY_REPLY = (
    "অনেকগুলো অনুরোধ একসাথে আসছে। একটু পরে আবার পাঠান।\n\n"
    "I am working through a backlog of messages right now. Please resend in a moment."
)


# Telegram waits only so long for the webhook to answer, and it retries the update
# when it does not -- which is how one slow model call turns into duplicate replies,
# or none at all when the worker is killed first. So the request only validates and
# parses the update, then hands the slow part (photo download, page fetches, the
# model chain, sending the reply) to this pool and answers 200 right away.
def _worker_count() -> int:
    try:
        return max(1, int(os.getenv("WEBHOOK_WORKERS", "4")))
    except ValueError:
        return 4


# Queued work is bounded on purpose. An unbounded queue on a small instance turns a
# burst into memory growth and replies that arrive long after they are useful; past
# this depth it is more honest to tell the sender to try again.
def _max_pending() -> int:
    try:
        return max(1, int(os.getenv("WEBHOOK_MAX_PENDING", "32")))
    except ValueError:
        return 32


_executor = ThreadPoolExecutor(
    max_workers=_worker_count(), thread_name_prefix="telegram-update"
)
_pending_lock = threading.Lock()
_pending = 0

# Let in-flight replies finish instead of dying with the interpreter. gunicorn bounds
# this by --graceful-timeout, so a restart can still cut off a long reply.
atexit.register(lambda: _executor.shutdown(wait=True))


def _stored_facts(orchestrator) -> list:
    """Facts the team saved via "Remember that ...", folded into the system prompt.

    A memory lookup must never cost us the reply, so failures degrade to no facts.
    """
    try:
        return orchestrator.memory.search("")
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not load stored facts | error=%s", error)
        return []


def _build_reply(orchestrator, text: str, photo_file_id: str, caption: str) -> str:
    """Produce the reply for one update. Always returns something sendable."""
    photo_bytes = fetch_telegram_photo(photo_file_id) if photo_file_id else None
    prompt_content = text
    if photo_bytes and not prompt_content:
        prompt_content = caption or "Describe this image."
    if not prompt_content and not photo_bytes:
        # Only reachable when the photo was the whole message and the download failed.
        return PHOTO_ERROR_REPLY

    # Deterministic commands must run before the model so database writes are explicit.
    # Only the command paths touch storage, so a failure here means a command could not
    # be written -- say so, because silence looks identical to the bot being down.
    try:
        command_result = orchestrator.handle_message(prompt_content)
    except Exception as error:  # noqa: BLE001
        logger.exception("Command failed, storage may be unavailable | error=%s", error)
        return STORAGE_ERROR_REPLY

    if command_result.get("handled"):
        logger.info("Command handled")
        return command_result.get("message") or GENERIC_ERROR_REPLY

    try:
        system_prompt = build_prompt(_stored_facts(orchestrator))

        if photo_bytes:
            result = describe(photo_bytes, prompt_content, system_prompt, mime="image/jpeg")
        else:
            pages = fetch_pages(find_urls(prompt_content)[:3])
            if pages:
                system_prompt += as_context(pages)
            result = complete(system_prompt, prompt_content)

        logger.info("Agent reply | model=%s", result["model"])
        return result["content"]

    except AllModelsUnavailable as error:
        logger.warning("Free model chain exhausted | error=%s", error)
        if error.rate_limited:
            return RATE_LIMIT_REPLY
        return command_result.get("message") or GENERIC_ERROR_REPLY

    except Exception as error:  # noqa: BLE001 - never drop a Telegram update
        logger.exception("Model call failed | error=%s", error)
        return command_result.get("message") or GENERIC_ERROR_REPLY


def _dispatch_reply(chat_id: Any, ai_text: str) -> Tuple[str, Optional[str]]:
    """Send a reply, split to Telegram's length limit.

    Returns ("sent"|"rejected"|"failed", detail). Never raises: in the background
    there is no caller left to handle an exception, only a log to write.
    """
    send_url = f"{TELEGRAM_API_URL}/sendMessage"
    chunks = split_telegram_message(ai_text)

    try:
        for index, chunk in enumerate(chunks, start=1):
            dispatch_response = requests.post(
                send_url,
                json={"chat_id": chat_id, "text": chunk},
                timeout=10,
            )
            dispatch_response.raise_for_status()
            try:
                telegram_result = dispatch_response.json()
            except ValueError:
                logger.error(
                    "Telegram dispatch returned invalid JSON | chat_id=%s part=%s/%s",
                    chat_id, index, len(chunks),
                )
                return "rejected", "invalid response"

            if not isinstance(telegram_result, dict) or telegram_result.get("ok") is not True:
                detail = (
                    telegram_result.get("description", "invalid response")
                    if isinstance(telegram_result, dict)
                    else "invalid response"
                )
                logger.error(
                    "Telegram rejected message | chat_id=%s part=%s/%s description=%s",
                    chat_id, index, len(chunks), detail,
                )
                return "rejected", detail

            logger.info(
                "Telegram dispatch success | chat_id=%s part=%s/%s status=%s",
                chat_id, index, len(chunks), dispatch_response.status_code,
            )
    except requests.RequestException as error:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        logger.error(
            "Telegram dispatch failed | chat_id=%s status=%s error_type=%s",
            chat_id, status_code, type(error).__name__,
        )
        return "failed", type(error).__name__

    return "sent", None


def _process_update(orchestrator, chat_id: Any, text: str, photo_file_id: str, caption: str) -> None:
    """Background half of the webhook. Owns its own errors: nothing is waiting on it."""
    global _pending
    try:
        ai_text = _build_reply(orchestrator, text, photo_file_id, caption)
        _dispatch_reply(chat_id, ai_text)
    except Exception as error:  # noqa: BLE001 - a dead thread must not be silent
        logger.exception("Background update processing failed | chat_id=%s error=%s", chat_id, error)
    finally:
        with _pending_lock:
            _pending -= 1


def telegram_webhook():
    global _pending

    testing = current_app.config["TESTING"]
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not webhook_secret and not testing:
        logger.error("Telegram webhook rejected | TELEGRAM_WEBHOOK_SECRET is not configured")
        return jsonify({"status": "error", "reason": "webhook_secret_not_configured"}), 503
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if (
        webhook_secret
        and (provided_secret or not testing)
        and not hmac.compare_digest(provided_secret, webhook_secret)
    ):
        logger.warning("Telegram webhook rejected | invalid secret header")
        return jsonify({"status": "ignored", "reason": "invalid_secret"}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        logger.warning("Telegram webhook ignored | request body is not a JSON object")
        return jsonify({"status": "ignored", "reason": "invalid_payload"}), 200

    message = payload.get("message") or payload.get("edited_message") or {}
    if not isinstance(message, dict):
        logger.warning("Telegram webhook ignored | message field is invalid")
        return jsonify({"status": "ignored", "reason": "invalid_message"}), 200

    sender = message.get("from")
    if not isinstance(sender, dict):
        sender = {}
    chat = message.get("chat")
    if not isinstance(chat, dict):
        chat = {}
    chat_id = chat.get("id")
    message_text = message.get("text")
    incoming_text = message_text.strip() if isinstance(message_text, str) else ""
    raw_caption = message.get("caption")
    caption = raw_caption.strip() if isinstance(raw_caption, str) else ""

    logger.info(
        "Incoming Telegram webhook | update_id=%s chat_id_present=%s",
        payload.get("update_id"),
        chat_id is not None,
    )

    if sender.get("is_bot") is True:
        return jsonify({"status": "ignored", "reason": "loop_protection"}), 200

    # Only the file_id is read here; the download itself belongs to the slow half.
    # Telegram sends several sizes, and the last is the largest.
    photos = message.get("photo")
    if not isinstance(photos, list):
        photos = []
    photos = [photo for photo in photos if isinstance(photo, dict) and photo.get("file_id")]
    photo_file_id = photos[-1]["file_id"] if photos else ""

    if not incoming_text and not photo_file_id:
        return jsonify({"status": "ignored", "reason": "missing_context"}), 200

    if not TELEGRAM_BOT_TOKEN and not testing:
        logger.error("Cannot reply to Telegram update | TELEGRAM_BOT_TOKEN is not configured")
        return jsonify({"status": "error", "reason": "telegram_token_not_configured"}), 503

    orchestrator = current_app.config.get("agent_orchestrator")

    if chat_id is None and testing:
        result = orchestrator.handle_message(incoming_text)
        logger.info("Testing fallback reply")
        return jsonify(result), 200

    if chat_id is None:
        return jsonify({"status": "ignored", "reason": "missing_context"}), 200

    # Tests assert on the finished reply, so they take the same code path start to
    # finish rather than racing a thread.
    if testing:
        ai_text = _build_reply(orchestrator, incoming_text, photo_file_id, caption)
        outcome, _detail = _dispatch_reply(chat_id, ai_text)
        if outcome == "rejected":
            return jsonify({"status": "dispatch_error"}), 502
        if outcome == "failed":
            return jsonify({"ok": False, "message": "Telegram message dispatch failed"}), 500
        return jsonify({"ok": True, "message": ai_text}), 200

    with _pending_lock:
        if _pending >= _max_pending():
            logger.warning(
                "Webhook backlog full, shedding update | chat_id=%s pending=%s",
                chat_id,
                _pending,
            )
            # Answer 200 either way: a non-2xx only makes Telegram redeliver an update
            # this process has already declined to queue.
            _dispatch_reply(chat_id, BUSY_REPLY)
            return jsonify({"status": "busy", "pending": _pending}), 200
        _pending += 1

    _executor.submit(
        _process_update, orchestrator, chat_id, incoming_text, photo_file_id, caption
    )
    logger.info("Update queued | chat_id=%s pending=%s", chat_id, _pending)

    # 200 now, before any model work: Telegram stops waiting and will not redeliver.
    return jsonify({"status": "accepted", "processed_chat": chat_id}), 200



def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing
    init_db()

    orchestrator = AgentOrchestrator()
    app.config["agent_orchestrator"] = orchestrator

    @app.get("/")
    def index():
        return jsonify({"status": "ok", "service": "tri-buddy-agent"})

    from app.api.webhook import register_telegram_webhook, webhook_bp
    app.register_blueprint(webhook_bp)
    app.register_blueprint(health_bp)
    registration_status = "not_attempted"
    if not testing:
        if os.getenv("RENDER_EXTERNAL_URL", "").strip():
            registration_status = (
                "registered" if register_telegram_webhook() else "failed"
            )
        else:
            registration_status = "skipped_missing_public_url"
    app.config["telegram_webhook_registration_status"] = registration_status
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
