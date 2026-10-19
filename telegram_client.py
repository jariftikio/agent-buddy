import logging
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def split_telegram_message(text: str) -> list[str]:
    chunks = []
    while len(text) > TELEGRAM_MAX_MESSAGE_LENGTH:
        split_at = text.rfind("\n", 0, TELEGRAM_MAX_MESSAGE_LENGTH + 1)
        if split_at <= 0:
            split_at = text.rfind(" ", 0, TELEGRAM_MAX_MESSAGE_LENGTH + 1)
        if split_at <= 0:
            split_at = TELEGRAM_MAX_MESSAGE_LENGTH
        chunks.append(text[:split_at])
        text = text[split_at:]
    chunks.append(text)
    return chunks


class TelegramClient:
    def __init__(self) -> None:
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.default_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def health_check(self) -> Dict[str, Any]:
        if not self.bot_token:
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=15)
            if response.ok:
                return {"ok": True, "status": response.status_code, "body": response.json()}
            return {"ok": False, "error": response.text[:500], "status": response.status_code}
        except requests.RequestException as exc:
            return {"ok": False, "error": str(exc)}

    def send_message(self, chat_id_or_message: str, message: Optional[str] = None) -> Dict[str, Any]:
        if message is None:
            chat_id = self.default_chat_id
            text = chat_id_or_message
        else:
            chat_id = chat_id_or_message
            text = message

        if not self.bot_token:
            return {"ok": False, "error": "TELEGRAM_BOT_TOKEN is not configured"}

        if not chat_id:
            return {"ok": False, "error": "TELEGRAM_CHAT_ID is not configured"}

        try:
            response_body: Dict[str, Any] = {}
            chunks = split_telegram_message(text)
            for index, chunk in enumerate(chunks, start=1):
                logger.info(
                    "Sending Telegram message | chat_id=%s part=%s/%s text=%s",
                    chat_id,
                    index,
                    len(chunks),
                    chunk,
                )
                response = requests.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                    timeout=20,
                )
                logger.info(
                    "Telegram response | status=%s body=%s",
                    response.status_code,
                    response.text[:500],
                )
                if not response.ok:
                    return {
                        "ok": False,
                        "error": response.text[:500],
                        "status": response.status_code,
                    }
                response_body = response.json()
            return {"ok": True, "body": response_body}
        except requests.RequestException as exc:
            logger.warning("Telegram request failed | error=%s", exc)
            return {"ok": False, "error": str(exc)}
