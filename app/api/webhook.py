import logging
import os
import re

import requests
from flask import Blueprint, jsonify

from app.main import telegram_webhook

logger = logging.getLogger(__name__)

TELEGRAM_WEBHOOK_PATH = "/api/webhook/telegram"
webhook_bp = Blueprint("webhook", __name__)


def register_telegram_webhook() -> bool:
    """Register this Render service's webhook when its public URL is available."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    public_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")

    if not public_url:
        logger.info("Skipping Telegram webhook registration | RENDER_EXTERNAL_URL is not set")
        return False
    if not token or not secret:
        logger.error(
            "Skipping Telegram webhook registration | TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_WEBHOOK_SECRET are required"
        )
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
        logger.error("Skipping Telegram webhook registration | secret format is invalid")
        return False

    url = f"{public_url}{TELEGRAM_WEBHOOK_PATH}"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": url, "secret_token": secret},
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as error:
        logger.error(
            "Telegram webhook registration request failed | error_type=%s",
            type(error).__name__,
        )
        return False

    if not isinstance(result, dict) or not result.get("ok"):
        logger.error(
            "Telegram rejected webhook registration | description=%s",
            result.get("description", "invalid response") if isinstance(result, dict) else "invalid response",
        )
        return False

    logger.info("Telegram webhook registered | endpoint=%s", url)
    return True


@webhook_bp.route(TELEGRAM_WEBHOOK_PATH, methods=["POST"])
def proxy_webhook():
    """Receive Telegram updates and pass them to the agent handler."""
    return telegram_webhook()


@webhook_bp.get(TELEGRAM_WEBHOOK_PATH)
def webhook_status():
    """Expose non-sensitive setup status for a simple endpoint check."""
    configured = bool(
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        and os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    )
    return jsonify({
        "status": "ok",
        "endpoint": TELEGRAM_WEBHOOK_PATH,
        "credentials_configured": configured,
        "registration": "automatic on Render startup",
    })
