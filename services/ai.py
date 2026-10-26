from typing import Any, Dict, Optional
import logging
import time
from requests.exceptions import Timeout, ConnectionError

from services.memory import ConversationMemory
from services.defensive_handler import InputSanitizer, DefensiveRouter
from telegram_client import TelegramClient
from openrouter_client import OpenRouterClient
from hermes_modules.language_config import LanguageDetector

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self, ai_client: OpenRouterClient, memory: ConversationMemory, telegram_client: TelegramClient) -> None:
        self.ai_client = ai_client
        self.memory = memory
        self.telegram_client = telegram_client
        self.sanitizer = InputSanitizer()
        self.router = DefensiveRouter()

    def generate_reply(self, message: str, session_id: str = "default") -> Dict[str, Any]:
        """Generate reply with input sanitization, defensive routing, and timeout protection.

        Handles connection timeouts gracefully to prevent Telegram webhook listener from freezing.
        Routes safe searches to WebSearchClient with Bengali markdown output.
        """
        start_time = time.time()
        is_bengali = False

        try:
            # Step 1: Analyze input for sensitivity
            sensitivity, keyword, is_bengali = self.sanitizer.analyze_input(message)
            logger.debug(f"Input sensitivity: {sensitivity.value}, Bengali: {is_bengali}")

            # Step 2: If critical, reject the request
            if sensitivity.value == "critical":
                logger.warning(f"Critical security violation detected: {keyword}")
                return self.router.generate_rejection_response(sensitivity, keyword, is_bengali)

            # Step 3: Check if input should use local handler instead of LLM
            should_use_local, handler_type = self.router.should_use_local_handler(message)
            logger.debug(f"Local handler match: {should_use_local}, handler: {handler_type}")

            if should_use_local and handler_type:
                # Route to local handler instead of LLM
                try:
                    local_response = self.router.generate_safe_response(handler_type, message, is_bengali)
                    # Still add to memory for context
                    self.memory.add_message(session_id, "user", message)
                    self.memory.add_message(session_id, "assistant", local_response.get("response", ""))
                    logger.info(f"Handler {handler_type} completed in {time.time() - start_time:.2f}s")
                    return local_response
                except (Timeout, ConnectionError) as e:
                    logger.error(f"Handler timeout/connection error for {handler_type}: {e}", exc_info=True)
                    # Graceful fallback without freezing webhook
                    error_msg = "⏱️ অনুরোধটি সময়মত সম্পন্ন হয়নি। পরে আবার চেষ্টা করুন।" if is_bengali else "⏱️ Request timed out. Please try again."
                    return {"ok": False, "response": error_msg, "handler": handler_type, "error": "timeout"}
                except Exception as e:
                    logger.error(f"Handler {handler_type} error: {e}", exc_info=True)
                    error_msg = f"⚠️ {handler_type} প্রসেসিং ত্রুটি" if is_bengali else f"⚠️ {handler_type} processing error"
                    return {"ok": False, "response": error_msg, "handler": handler_type, "error": str(e)}

            # Step 4: If warning sensitivity, still proceed but log it
            if sensitivity.value == "warning":
                logger.warning(f"Suspicious pattern detected: {keyword}")

            # Step 5: Normal LLM processing with timeout protection
            self.memory.add_message(session_id, "user", message)
            history = self.memory.get_history(session_id)
            prompt = self._build_prompt(history)

            try:
                response = self.ai_client.generate_response(prompt)
                if response.get("ok"):
                    self.memory.add_message(session_id, "assistant", response.get("response", ""))
                logger.info(f"LLM response completed in {time.time() - start_time:.2f}s")
                return response
            except (Timeout, ConnectionError) as e:
                logger.error(f"LLM timeout/connection error: {e}", exc_info=True)
                error_msg = "⏱️ এআই সেবা সাড়া দিচ্ছে না। পরে আবার চেষ্টা করুন।" if is_bengali else "⏱️ AI service is unavailable. Please try again."
                return {"ok": False, "response": error_msg, "error": "timeout"}

        except Exception as e:
            logger.error(f"Unexpected error in generate_reply: {e}", exc_info=True)
            error_msg = "❌ অপ্রত্যাশিত ত্রুটি ঘটেছে। দয়া করে আবার চেষ্টা করুন।" if is_bengali else "❌ An unexpected error occurred. Please try again."
            return {"ok": False, "response": error_msg, "error": str(e)}

    def send_to_telegram(self, message: str) -> Dict[str, Any]:
        return self.telegram_client.send_message(message)

    def _build_prompt(self, history: list[dict]) -> str:
        if not history:
            return "You are a helpful assistant."

        return "\n".join(
            f"{item['role']}: {item['content']}" for item in history[-8:]
        )
