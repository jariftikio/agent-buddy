import os
import asyncio
import logging
from typing import Any, Dict

from dotenv import load_dotenv
from flask import Flask

from routes.main import register_routes
from services.ai import AIService
from services.memory import ConversationMemory
from services.async_executor import AsyncHermesExecutor, initialize_async_executor
from telegram_client import TelegramClient
from openrouter_client import OpenRouterClient

load_dotenv()
logger = logging.getLogger(__name__)


def create_app(testing: bool = False, enable_async: bool = True) -> Flask:
    """
    Create Flask app with optional async Layer 5 execution.

    Args:
        testing: Enable test mode
        enable_async: Enable async task routing (default True)

    Returns:
        Configured Flask app instance
    """
    app = Flask(__name__)
    app.config["TESTING"] = testing

    memory = ConversationMemory()
    telegram_client = TelegramClient()
    ai_client = OpenRouterClient()
    ai_service = AIService(
        ai_client=ai_client,
        memory=memory,
        telegram_client=telegram_client,
    )

    # Initialize async executor if enabled
    if enable_async:
        try:
            async_executor = initialize_async_executor(ai_service)
            ai_service.set_async_executor(async_executor)
            logger.info("✅ Async Layer 5 execution enabled")
            app.async_executor = async_executor
        except Exception as e:
            logger.warning(f"⚠️ Async executor initialization failed: {e}")

    register_routes(app, ai_service)
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"🚀 Hermes Agent v2.0 + Async Layer 5 starting on port {port}")
    app.run(host="0.0.0.0", port=port)
