import hmac
import logging
import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from flask import Flask, current_app, jsonify, request

from app.api.health import health_bp
from app.agent.orchestrator import AgentOrchestrator
from app.agent.prompt import build_prompt
from app.db.session import init_db
from app.services.models import AllModelsUnavailable, complete
from app.services.vision import describe, fetch_telegram_photo
from app.tools.web import as_context, fetch_page, find_urls
from telegram_client import split_telegram_message

load_dotenv()

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


def _stored_facts(orchestrator) -> list:
    """Facts the team saved via "Remember that ...", folded into the system prompt.

    A memory lookup must never cost us the reply, so failures degrade to no facts.
    """
    try:
        return orchestrator.memory.search("")
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not load stored facts | error=%s", error)
        return []


def telegram_webhook():
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not webhook_secret and not current_app.config["TESTING"]:
        logger.error("Telegram webhook rejected | TELEGRAM_WEBHOOK_SECRET is not configured")
        return jsonify({"status": "error", "reason": "webhook_secret_not_configured"}), 503
    provided_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if (
        webhook_secret
        and (provided_secret or not current_app.config["TESTING"])
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

    logger.info(
        "Incoming Telegram webhook | update_id=%s chat_id_present=%s",
        payload.get("update_id"),
        chat_id is not None,
    )

    if sender.get("is_bot") is True:
        return jsonify({"status": "ignored", "reason": "loop_protection"}), 200

    photo_bytes = None
    photos = message.get("photo")
    if not isinstance(photos, list):
        photos = []
    photos = [photo for photo in photos if isinstance(photo, dict) and photo.get("file_id")]
    if photos:
        # Telegram sends several sizes; the last is the largest.
        photo_bytes = fetch_telegram_photo(photos[-1].get("file_id", ""))
        if photo_bytes and not incoming_text:
            caption = message.get("caption")
            incoming_text = (
                caption.strip() if isinstance(caption, str) else ""
            ) or "Describe this image."

    if not incoming_text and not photo_bytes:
        return jsonify({"status": "ignored", "reason": "missing_context"}), 200

    if not TELEGRAM_BOT_TOKEN and not current_app.config["TESTING"]:
        logger.error("Cannot reply to Telegram update | TELEGRAM_BOT_TOKEN is not configured")
        return jsonify({"status": "error", "reason": "telegram_token_not_configured"}), 503

    prompt_content = incoming_text

    if chat_id is None and current_app.config["TESTING"]:
        result = current_app.config.get("agent_orchestrator").handle_message(prompt_content)
        logger.info("Testing fallback reply")
        return jsonify(result), 200

    if chat_id is None:
        return jsonify({"status": "ignored", "reason": "missing_context"}), 200

    orchestrator = current_app.config.get("agent_orchestrator")

    # Deterministic commands must run before the model so database writes are explicit.
    command_result = orchestrator.handle_message(prompt_content)
    if command_result.get("handled"):
        ai_text = command_result.get("message") or GENERIC_ERROR_REPLY
        logger.info("Command handled | chat_id=%s", chat_id)
    else:
        try:
            system_prompt = build_prompt(_stored_facts(orchestrator))

            if photo_bytes:
                result = describe(photo_bytes, prompt_content, system_prompt, mime="image/jpeg")
            else:
                pages = [fetch_page(url) for url in find_urls(prompt_content)[:3]]
                if pages:
                    system_prompt += as_context(pages)
                result = complete(system_prompt, prompt_content)

            ai_text = result["content"]
            logger.info("Agent reply | chat_id=%s model=%s", chat_id, result["model"])

        except AllModelsUnavailable as error:
            logger.warning("Free model chain exhausted | chat_id=%s error=%s", chat_id, error)
            ai_text = RATE_LIMIT_REPLY if error.rate_limited else (
                command_result.get("message") or GENERIC_ERROR_REPLY
            )

        except Exception as error:  # noqa: BLE001 - never drop a Telegram update
            logger.exception("Model call failed | chat_id=%s error=%s", chat_id, error)
            ai_text = command_result.get("message") or GENERIC_ERROR_REPLY

    logger.info("Prepared Telegram reply | chat_id=%s", chat_id)

    send_url = f"{TELEGRAM_API_URL}/sendMessage"

    logger.info("Sending reply to Telegram | chat_id=%s", chat_id)
    try:
        chunks = split_telegram_message(ai_text)
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
                    chat_id,
                    index,
                    len(chunks),
                )
                return jsonify({"status": "dispatch_error"}), 502

            if not isinstance(telegram_result, dict) or telegram_result.get("ok") is not True:
                logger.error(
                    "Telegram rejected message | chat_id=%s part=%s/%s description=%s",
                    chat_id,
                    index,
                    len(chunks),
                    telegram_result.get("description", "invalid response")
                    if isinstance(telegram_result, dict)
                    else "invalid response",
                )
                return jsonify({"status": "dispatch_error"}), 502

            logger.info(
                "Telegram dispatch success | chat_id=%s part=%s/%s status=%s",
                chat_id,
                index,
                len(chunks),
                dispatch_response.status_code,
            )
    except requests.RequestException as error:
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        logger.error(
            "Telegram dispatch failed | chat_id=%s status=%s error_type=%s",
            chat_id,
            status_code,
            type(error).__name__,
        )
        if current_app.config["TESTING"]:
            return jsonify({"ok": False, "message": "Telegram message dispatch failed"}), 500
        return jsonify({"status": "dispatch_error"}), 500

    if current_app.config["TESTING"]:
        return jsonify({"ok": True, "message": ai_text}), 200

    return jsonify({"status": "success", "processed_chat": chat_id}), 200


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
