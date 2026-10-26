"""
Intent Classification System with LLM and Keyword-based Tiers

Architecture:
- Tier 1: LLM-based classifier (semantic understanding)
- Tier 2: Keyword-based classifier (fast, reliable fallback)
- Composite: Integrates both with intelligent fallback
"""

import logging
import json
import re
from typing import Optional, Dict, Any, List, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import time

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks the agent can handle."""

    WEB_SEARCH = "web_search"
    SYSTEM_MONITOR = "system_monitor"
    SYSTEM_CHECK = "system_check"
    PORT_CHECK = "port_check"
    HEALTH_REPORT = "health_report"
    URL_CHECK = "url_check"
    COMBINED = "combined"
    UNKNOWN = "unknown"


@dataclass
class ExtractedEntity:
    """Structured entity extracted from user input."""

    entity_type: str  # "search_query", "port_number", "metric_type"
    value: Any  # Actual value
    confidence: float  # 0.0-1.0


@dataclass
class Intent:
    """Classified user intent with extracted entities."""

    task_type: TaskType
    primary_query: str
    secondary_queries: List[str]
    parameters: Dict[str, Any]
    entities: List[ExtractedEntity]
    confidence: float
    classifier_used: str  # "llm", "keyword", or "composite"
    reasoning: str  # Explanation of classification

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_type": self.task_type.value,
            "primary_query": self.primary_query,
            "secondary_queries": self.secondary_queries,
            "parameters": self.parameters,
            "entities": [
                {
                    "entity_type": e.entity_type,
                    "value": e.value,
                    "confidence": e.confidence,
                }
                for e in self.entities
            ],
            "confidence": self.confidence,
            "classifier_used": self.classifier_used,
            "reasoning": self.reasoning,
        }


class IntentClassifierBase(ABC):
    """Abstract base class for intent classifiers."""

    @abstractmethod
    def classify(self, user_input: str) -> Intent:
        """Classify user input into an intent."""
        pass

    @abstractmethod
    def name(self) -> str:
        """Return classifier name."""
        pass


class KeywordBasedIntentClassifier(IntentClassifierBase):
    """Fast, reliable keyword-based intent classifier (Tier 2 fallback)."""

    # Keywords mapping for intent detection
    SEARCH_KEYWORDS = {
        "search",
        "find",
        "look up",
        "query",
        "web",
        "internet",
        "latest",
        "trending",
        "how to",
        "what is",
        "tell me about",
        "research",
        "investigate",
    }

    MONITOR_KEYWORDS = {
        "cpu",
        "memory",
        "ram",
        "usage",
        "load",
        "performance",
        "monitor",
        "check system",
        "health",
        "status",
        "diagnostics",
        "metrics",
    }

    PORT_KEYWORDS = {
        "port",
        "listening",
        "connection",
        "network",
        "process",
        "service",
        "daemon",
    }

    URL_KEYWORDS = {
        "url",
        "link",
        "domain",
        "website",
        "check",
        "safe",
        "phishing",
        "malicious",
        "security",
        "verify",
        "suspicious",
    }

    def classify(self, user_input: str) -> Intent:
        """Classify using keyword matching."""
        lower_input = user_input.lower()
        logger.debug(f"Keyword classifier analyzing: '{user_input}'")

        # Check for combined requests
        has_search = any(kw in lower_input for kw in self.SEARCH_KEYWORDS)
        has_monitor = any(kw in lower_input for kw in self.MONITOR_KEYWORDS)
        has_port = any(kw in lower_input for kw in self.PORT_KEYWORDS)
        has_url = any(kw in lower_input for kw in self.URL_KEYWORDS)

        # Determine task type
        if has_search and has_monitor:
            task_type = TaskType.COMBINED
            primary_query = self._extract_search_query(user_input)
            entities = [
                ExtractedEntity("search_query", primary_query, 0.85),
                ExtractedEntity("monitor_flag", True, 0.8),
            ]
        elif has_search:
            task_type = TaskType.WEB_SEARCH
            primary_query = self._extract_search_query(user_input)
            entities = [ExtractedEntity("search_query", primary_query, 0.85)]
        elif has_port:
            task_type = TaskType.PORT_CHECK
            port_num = self._extract_port_number(user_input)
            primary_query = f"Check port {port_num}" if port_num else "Port check"
            entities = (
                [ExtractedEntity("port_number", port_num, 0.9)]
                if port_num
                else []
            )
        elif has_url:
            task_type = TaskType.URL_CHECK
            url = self._extract_url(user_input)
            primary_query = url if url else user_input
            entities = (
                [ExtractedEntity("url", url, 0.95)]
                if url
                else []
            )
        elif "health" in lower_input or "report" in lower_input:
            task_type = TaskType.HEALTH_REPORT
            primary_query = "Generate system health report"
            entities = []
        elif has_monitor:
            task_type = TaskType.SYSTEM_MONITOR
            primary_query = "Check CPU and memory usage"
            entities = [ExtractedEntity("monitor_flag", True, 0.85)]
        else:
            task_type = TaskType.UNKNOWN
            primary_query = user_input
            entities = []

        confidence = self._calculate_confidence(task_type, has_search, has_monitor)

        intent = Intent(
            task_type=task_type,
            primary_query=primary_query,
            secondary_queries=[],
            parameters=self._build_parameters(task_type, entities),
            entities=entities,
            confidence=confidence,
            classifier_used="keyword",
            reasoning=f"Matched keywords: {self._get_matched_keywords(user_input)}",
        )

        logger.debug(f"Keyword classifier: {task_type.value} ({confidence:.0%})")
        return intent

    def name(self) -> str:
        """Return classifier name."""
        return "keyword"

    @staticmethod
    def _extract_search_query(user_input: str) -> str:
        """Extract search query from user input."""
        prefixes = ("search for", "find", "look up", "query", "tell me about")
        query = user_input.lower()

        for prefix in prefixes:
            if query.startswith(prefix):
                query = query[len(prefix) :].strip()
                break

        return query.strip() or user_input

    @staticmethod
    def _extract_port_number(user_input: str) -> Optional[int]:
        """Extract port number from user input."""
        match = re.search(r"\b(\d{1,5})\b", user_input)
        if match:
            port = int(match.group(1))
            if 0 < port < 65536:
                return port
        return None

    @staticmethod
    def _extract_url(user_input: str) -> Optional[str]:
        """Extract URL from user input."""
        url_pattern = r'https?://[^\s]+'
        match = re.search(url_pattern, user_input)
        if match:
            return match.group(0)
        return None

    @staticmethod
    def _calculate_confidence(
        task_type: TaskType, has_search: bool, has_monitor: bool
    ) -> float:
        """Calculate confidence score for classification."""
        if task_type == TaskType.UNKNOWN:
            return 0.5
        elif task_type == TaskType.COMBINED:
            return 0.8
        elif has_search or has_monitor:
            return 0.9
        else:
            return 0.7

    @staticmethod
    def _get_matched_keywords(user_input: str) -> List[str]:
        """Get list of matched keywords."""
        matched = []
        lower_input = user_input.lower()
        all_keywords = (
            KeywordBasedIntentClassifier.SEARCH_KEYWORDS
            | KeywordBasedIntentClassifier.MONITOR_KEYWORDS
            | KeywordBasedIntentClassifier.PORT_KEYWORDS
            | KeywordBasedIntentClassifier.URL_KEYWORDS
        )
        for kw in all_keywords:
            if kw in lower_input:
                matched.append(kw)
        return matched[:3]  # Top 3

    @staticmethod
    def _build_parameters(
        task_type: TaskType, entities: List[ExtractedEntity]
    ) -> Dict[str, Any]:
        """Build parameters dict from entities."""
        params = {}
        for entity in entities:
            if entity.entity_type == "search_query":
                params["search_query"] = entity.value
                params["max_results"] = 5
            elif entity.entity_type == "port_number":
                params["port"] = entity.value
            elif entity.entity_type == "url":
                params["url"] = entity.value
            elif entity.entity_type == "monitor_flag":
                params["include_load_average"] = True
        return params


class LLMIntentClassifier(IntentClassifierBase):
    """Semantic intent classifier using LLM (Tier 1)."""

    # Supported task types for LLM classification
    SUPPORTED_TASKS = [
        "web_search",
        "system_monitor",
        "port_check",
        "health_report",
        "url_check",
        "combined",
    ]

    def __init__(
        self,
        api_client=None,
        model: str = "claude-3-5-sonnet-20241022",
        timeout: int = 10,
    ):
        """
        Initialize LLM classifier.

        Args:
            api_client: LLM API client (e.g., Anthropic client)
            model: Model to use for classification
            timeout: API request timeout in seconds
        """
        self.api_client = api_client
        self.model = model
        self.timeout = timeout
        self._classification_cache = {}  # Simple cache

        if api_client:
            logger.info(f"LLM classifier initialized with model: {model}")
        else:
            logger.warning("LLM classifier initialized without API client")

    def classify(self, user_input: str) -> Intent:
        """Classify using LLM semantic understanding."""
        if not self.api_client:
            logger.warning("No API client configured, skipping LLM classification")
            return self._create_unknown_intent(user_input)

        # Check cache
        cache_key = hash(user_input)
        if cache_key in self._classification_cache:
            logger.debug("Using cached LLM classification")
            return self._classification_cache[cache_key]

        try:
            logger.debug(f"LLM classifier analyzing: '{user_input}'")
            intent = self._classify_with_llm(user_input)
            self._classification_cache[cache_key] = intent
            return intent
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return self._create_unknown_intent(user_input, error_reason=str(e))

    def name(self) -> str:
        """Return classifier name."""
        return "llm"

    def _classify_with_llm(self, user_input: str) -> Intent:
        """Perform LLM-based classification."""
        start_time = time.time()

        # Build classification prompt
        prompt = self._build_classification_prompt(user_input)

        # Call LLM API
        response = self.api_client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
            timeout=self.timeout,
        )

        classification_text = response.content[0].text
        execution_time = time.time() - start_time

        logger.debug(f"LLM response ({execution_time:.2f}s): {classification_text[:200]}")

        # Parse LLM response
        intent = self._parse_llm_response(classification_text, user_input, execution_time)
        return intent

    def _build_classification_prompt(self, user_input: str) -> str:
        """Build the prompt for LLM classification."""
        task_types_desc = "\n".join(
            [
                f"- {tt}: {self._get_task_description(tt)}"
                for tt in self.SUPPORTED_TASKS
            ]
        )

        prompt = f"""You are an intelligent intent classifier for a system automation agent.

User Input: "{user_input}"

Classify this user input into one of these task types:
{task_types_desc}

Respond with a JSON object (no markdown, just raw JSON) containing:
{{
    "task_type": "one of: web_search, system_monitor, port_check, health_report, combined",
    "primary_query": "main query/action extracted from input",
    "secondary_queries": ["any additional queries if combined task"],
    "confidence": 0.0-1.0 confidence score,
    "reasoning": "brief explanation of classification",
    "entities": [
        {{
            "entity_type": "e.g., search_query, port_number, metric_type",
            "value": "extracted value",
            "confidence": 0.0-1.0
        }}
    ],
    "parameters": {{
        "key": "value pairs for task execution"
    }}
}}

Be precise in entity extraction:
- For search queries: extract the exact search term
- For ports: extract numeric port (0-65535)
- For metrics: extract CPU, memory, health, etc.
- For combined tasks: identify all components

Respond with ONLY the JSON object, no other text."""

        return prompt

    @staticmethod
    def _get_task_description(task_type: str) -> str:
        """Get human-readable description of task type."""
        descriptions = {
            "web_search": "User wants to search the web for information",
            "system_monitor": "User wants to check CPU, memory, or system metrics",
            "port_check": "User wants to check if a network port is listening",
            "health_report": "User wants a comprehensive system health diagnostic",
            "combined": "User wants multiple tasks (search + monitoring, etc.)",
        }
        return descriptions.get(task_type, "Unknown task type")

    def _parse_llm_response(
        self, response_text: str, user_input: str, execution_time: float
    ) -> Intent:
        """Parse LLM response into Intent object."""
        try:
            # Extract JSON from response
            classification = json.loads(response_text)

            # Validate and normalize
            task_type_str = classification.get("task_type", "unknown")
            try:
                task_type = TaskType[task_type_str.upper()]
            except KeyError:
                task_type = TaskType.UNKNOWN

            # Extract entities
            entities = [
                ExtractedEntity(
                    entity_type=e.get("entity_type", "unknown"),
                    value=e.get("value"),
                    confidence=float(e.get("confidence", 0.7)),
                )
                for e in classification.get("entities", [])
            ]

            confidence = float(classification.get("confidence", 0.7))

            intent = Intent(
                task_type=task_type,
                primary_query=classification.get("primary_query", user_input),
                secondary_queries=classification.get("secondary_queries", []),
                parameters=classification.get("parameters", {}),
                entities=entities,
                confidence=confidence,
                classifier_used="llm",
                reasoning=classification.get(
                    "reasoning", f"LLM classification in {execution_time:.2f}s"
                ),
            )

            logger.debug(f"LLM parsed intent: {task_type.value} ({confidence:.0%})")
            return intent

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return self._create_unknown_intent(user_input, error_reason="Parse error")

    @staticmethod
    def _create_unknown_intent(
        user_input: str, error_reason: str = "Unable to classify"
    ) -> Intent:
        """Create an UNKNOWN intent."""
        return Intent(
            task_type=TaskType.UNKNOWN,
            primary_query=user_input,
            secondary_queries=[],
            parameters={},
            entities=[],
            confidence=0.3,
            classifier_used="llm",
            reasoning=f"Classification failed: {error_reason}",
        )


class CompositeIntentClassifier(IntentClassifierBase):
    """
    Two-tier intent classifier combining LLM and keyword-based approaches.

    Architecture:
    - Tier 1: LLM classifier (semantic understanding, high accuracy)
    - Tier 2: Keyword classifier (fast fallback, reliability)
    - Strategy: Use LLM when confident, fall back to keyword if LLM fails
    """

    def __init__(
        self,
        llm_client=None,
        llm_confidence_threshold: float = 0.7,
        use_llm: bool = True,
    ):
        """
        Initialize composite classifier.

        Args:
            llm_client: LLM API client
            llm_confidence_threshold: Minimum confidence to trust LLM result
            use_llm: Enable LLM tier (disable for pure keyword fallback)
        """
        self.keyword_classifier = KeywordBasedIntentClassifier()
        self.llm_classifier = (
            LLMIntentClassifier(api_client=llm_client)
            if llm_client and use_llm
            else None
        )
        self.llm_confidence_threshold = llm_confidence_threshold

        logger.info(
            f"Composite classifier initialized (LLM: {bool(self.llm_classifier)}, "
            f"threshold: {llm_confidence_threshold:.0%})"
        )

    def classify(self, user_input: str) -> Intent:
        """
        Classify using intelligent two-tier strategy.

        Strategy:
        1. Try LLM classifier if available
        2. If LLM confident (> threshold), use LLM result
        3. Otherwise, use keyword classifier as fallback
        4. If LLM fails, fall back to keyword classifier
        """
        logger.debug(f"Composite classifier analyzing: '{user_input}'")

        # Tier 1: Try LLM classifier
        if self.llm_classifier:
            try:
                llm_intent = self.llm_classifier.classify(user_input)

                # Check if LLM result is confident enough
                if llm_intent.confidence >= self.llm_confidence_threshold:
                    logger.info(
                        f"Using LLM classification: {llm_intent.task_type.value} "
                        f"({llm_intent.confidence:.0%})"
                    )
                    return llm_intent
                else:
                    logger.debug(
                        f"LLM confidence too low ({llm_intent.confidence:.0%}), "
                        f"falling back to keyword"
                    )
            except Exception as e:
                logger.warning(f"LLM classifier failed, falling back: {e}")

        # Tier 2: Keyword classifier (fallback or primary)
        keyword_intent = self.keyword_classifier.classify(user_input)
        logger.info(
            f"Using keyword classification: {keyword_intent.task_type.value} "
            f"({keyword_intent.confidence:.0%})"
        )
        return keyword_intent

    def name(self) -> str:
        """Return classifier name."""
        return "composite"

    def set_llm_client(self, llm_client) -> None:
        """Update LLM client at runtime."""
        if llm_client:
            self.llm_classifier = LLMIntentClassifier(api_client=llm_client)
            logger.info("LLM client updated for composite classifier")
        else:
            self.llm_classifier = None
            logger.info("LLM tier disabled for composite classifier")
