from typing import Any, Dict, Optional

from services.memory import ConversationMemory
from services.defensive_handler import InputSanitizer, DefensiveRouter
from telegram_client import TelegramClient
from openrouter_client import OpenRouterClient
from hermes_modules.language_config import LanguageDetector


class AIService:
    def __init__(self, ai_client: OpenRouterClient, memory: ConversationMemory, telegram_client: TelegramClient) -> None:
        self.ai_client = ai_client
        self.memory = memory
        self.telegram_client = telegram_client
        self.sanitizer = InputSanitizer()
        self.router = DefensiveRouter()

    def generate_reply(self, message: str, session_id: str = "default") -> Dict[str, Any]:
        """Generate reply with input sanitization and defensive routing."""
        # Step 1: Analyze input for sensitivity
        sensitivity, keyword, is_bengali = self.sanitizer.analyze_input(message)

        # Step 2: If critical, reject the request
        if sensitivity.value == "critical":
            return self.router.generate_rejection_response(sensitivity, keyword, is_bengali)

        # Step 3: Check if input should use local handler instead of LLM
        should_use_local, handler_type = self.router.should_use_local_handler(message)

        if should_use_local and handler_type:
            # Route to local handler instead of LLM
            local_response = self.router.generate_safe_response(handler_type, message, is_bengali)
            # Still add to memory for context
            self.memory.add_message(session_id, "user", message)
            self.memory.add_message(session_id, "assistant", local_response.get("response", ""))
            return local_response

        # Step 4: If warning sensitivity, still proceed but log it
        if sensitivity.value == "warning":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Suspicious pattern detected in input: {keyword}")

        # Step 5: Normal LLM processing
        self.memory.add_message(session_id, "user", message)
        history = self.memory.get_history(session_id)
        prompt = self._build_prompt(history)
        response = self.ai_client.generate_response(prompt)
        if response.get("ok"):
            self.memory.add_message(session_id, "assistant", response.get("response", ""))
        return response

    def send_to_telegram(self, message: str) -> Dict[str, Any]:
        return self.telegram_client.send_message(message)

    def _build_prompt(self, history: list[dict]) -> str:
        if not history:
            return "You are a helpful assistant."

        return "\n".join(
            f"{item['role']}: {item['content']}" for item in history[-8:]
        )
