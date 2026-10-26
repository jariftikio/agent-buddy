"""
OpenRouter API Client for Llama Model Integration

Provides simplified interface to OpenRouter's Llama models with Bengali support.
"""

import logging
import json
import os
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API with Llama model support."""

    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL = "meta-llama/llama-2-70b-chat"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout: int = 30,
    ):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (from env var if not provided)
            model: Model to use (default: Llama 2 70B Chat)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. Set OPENROUTER_API_KEY environment variable."
            )

        self.model = model
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://hermes-agent.local",
            "X-Title": "Hermes Agent",
            "Content-Type": "application/json",
        }

        logger.info(f"Initialized OpenRouter client with model: {model}")

    def complete(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a completion request to OpenRouter.

        Args:
            messages: List of message dicts with "role" and "content"
            system_prompt: System message to prepend
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response

        Raises:
            Exception: On API error
        """
        try:
            # Prepare messages with system prompt
            request_messages = messages
            if system_prompt:
                request_messages = [
                    {"role": "system", "content": system_prompt},
                    *messages
                ]

            # Make API request
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": request_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=self.timeout,
            )

            response.raise_for_status()
            data = response.json()

            # Extract response text
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0].get("message", {}).get("content", "")
                logger.debug(f"OpenRouter response: {content[:100]}...")
                return content
            else:
                raise Exception(f"Unexpected response format: {data}")

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API error: {e}")
            raise Exception(f"OpenRouter API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenRouter response: {e}")
            raise Exception(f"Failed to parse API response: {str(e)}")

    def classify_intent_bengali(
        self,
        user_input: str,
        system_prompt: str,
    ) -> Dict[str, Any]:
        """
        Classify Bengali user input intent using LLM.

        Args:
            user_input: Bengali language user input
            system_prompt: System prompt for Bengali context

        Returns:
            Classification result with task type and confidence
        """
        classification_prompt = f"""বাংলায় নিম্নলিখিত ব্যবহারকারী ইনপুট বিশ্লেষণ করুন এবং তার অভিপ্রায় শনাক্ত করুন।

সম্ভাব্য অভিপ্রায়:
- web_search: ওয়েব অনুসন্ধান/গবেষণা সম্পর্কিত
- system_monitor: সিস্টেম অবস্থা/কর্মক্ষমতা পরীক্ষা
- port_check: পোর্ট/সংযোগ পরীক্ষা
- health_report: সম্পূর্ণ সিস্টেম স্বাস্থ্য রিপোর্ট
- url_check: ইউআরএল নিরাপত্তা পরীক্ষা

ব্যবহারকারীর ইনপুট: "{user_input}"

JSON ফর্ম্যাটে উত্তর দিন:
{{"task_type": "...", "confidence": 0.0-1.0, "reasoning": "..."}}
"""

        try:
            response = self.complete(
                messages=[{"role": "user", "content": classification_prompt}],
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=200,
            )

            # Parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                logger.debug(f"Classification result: {result}")
                return result
            else:
                logger.warning(f"Could not parse classification JSON from: {response}")
                return {
                    "task_type": "unknown",
                    "confidence": 0.0,
                    "reasoning": "Failed to parse LLM response",
                }

        except Exception as e:
            logger.error(f"Classification error: {e}")
            return {
                "task_type": "unknown",
                "confidence": 0.0,
                "reasoning": f"Error during classification: {str(e)}",
            }

    def translate_to_english(
        self,
        bengali_text: str,
        system_prompt: str,
    ) -> str:
        """
        Translate Bengali text to English for processing.

        Args:
            bengali_text: Bengali language text
            system_prompt: System prompt context

        Returns:
            English translation
        """
        try:
            response = self.complete(
                messages=[
                    {
                        "role": "user",
                        "content": f"শুধুমাত্র এই বাংলা পাঠ্যটি ইংরেজিতে অনুবাদ করুন, অন্য কিছু যোগ করবেন না:\n\n{bengali_text}"
                    }
                ],
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=500,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return bengali_text  # Return original on error

    @staticmethod
    def list_available_models() -> List[str]:
        """
        List available Llama models on OpenRouter.

        Returns:
            List of model identifiers
        """
        # Common Llama models available on OpenRouter
        return [
            "meta-llama/llama-2-70b-chat",
            "meta-llama/llama-2-13b-chat",
            "meta-llama/llama-2-7b-chat",
            "gryphe/mythomax-l2-13b",
            "teknium/openhermes-2-mistral-7b",
        ]
