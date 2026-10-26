"""
Updated Hermes Agent Core - Integrated with Advanced Intent Classification

This version supports:
- LLM-based semantic intent classification
- Keyword-based fallback classification
- Composite two-tier architecture
- Dynamic classifier switching
"""

import logging
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .intent_classifiers import (
    CompositeIntentClassifier,
    LLMIntentClassifier,
    KeywordBasedIntentClassifier,
    Intent,
    TaskType,
)

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_type: TaskType
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_type": self.task_type.value,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentContext:
    """Context for agent execution with enhanced intent data."""

    session_id: str
    user_input: str
    intent: Optional[Intent] = None
    results: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: TaskResult) -> None:
        """Add a task result to context."""
        self.results.append(result)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_input": self.user_input,
            "intent": self.intent.to_dict() if self.intent else None,
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }


class HermesAgent:
    """
    Enhanced Hermes agent with intelligent intent classification.

    Features:
    - Two-tier intent classification (LLM + keyword fallback)
    - Dynamic classifier configuration
    - LLM client injection
    - Backward compatible with keyword-only mode
    """

    def __init__(
        self,
        enable_logging: bool = True,
        llm_client: Optional[Any] = None,
        llm_confidence_threshold: float = 0.7,
        use_llm: bool = True,
    ):
        """
        Initialize the Hermes agent.

        Args:
            enable_logging: Enable logging of agent operations.
            llm_client: LLM API client (e.g., Anthropic Anthropic.Anthropic())
            llm_confidence_threshold: Minimum confidence to trust LLM (0.0-1.0)
            use_llm: Enable LLM-based classification (fall back to keyword if False)
        """
        self.enable_logging = enable_logging

        # Initialize composite classifier (LLM + keyword fallback)
        self.classifier = CompositeIntentClassifier(
            llm_client=llm_client,
            llm_confidence_threshold=llm_confidence_threshold,
            use_llm=use_llm,
        )

        self.task_handlers: Dict[TaskType, Callable] = {}
        self._session_counter = 0

        if enable_logging:
            logger.setLevel(logging.INFO)
            classifier_type = "LLM+Keyword" if use_llm and llm_client else "Keyword-only"
            logger.info(
                f"HermesAgent initialized (Classifier: {classifier_type}, "
                f"LLM threshold: {llm_confidence_threshold:.0%})"
            )

    def register_handler(self, task_type: TaskType, handler: Callable) -> None:
        """
        Register a task handler for a task type.

        Args:
            task_type: The type of task to handle.
            handler: Callable that handles the task.
        """
        self.task_handlers[task_type] = handler
        logger.info(f"Registered handler for {task_type.value}")

    def set_llm_client(self, llm_client: Optional[Any]) -> None:
        """
        Update LLM client at runtime.

        Useful for:
        - Enabling LLM after initialization
        - Switching API providers
        - Updating credentials

        Args:
            llm_client: LLM API client or None to disable LLM tier
        """
        self.classifier.set_llm_client(llm_client)
        logger.info(f"LLM client updated: {'enabled' if llm_client else 'disabled'}")

    def process_input(self, user_input: str) -> AgentContext:
        """
        Process user input through intelligent classification and execution.

        Args:
            user_input: Natural language input from user.

        Returns:
            AgentContext with execution results and enhanced intent data.
        """
        self._session_counter += 1
        session_id = f"session_{self._session_counter}"

        # Create context
        context = AgentContext(session_id=session_id, user_input=user_input)

        # Classify intent (LLM or keyword, or both with fallback)
        intent = self.classifier.classify(user_input)
        context.intent = intent

        if self.enable_logging:
            logger.info(
                f"[{session_id}] Intent: {intent.task_type.value} "
                f"({intent.confidence:.0%}, {intent.classifier_used})"
            )
            logger.debug(f"[{session_id}] Reasoning: {intent.reasoning}")
            if intent.entities:
                logger.debug(f"[{session_id}] Entities: {intent.entities}")

        # Execute appropriate handlers
        self._execute_tasks(context)

        return context

    def _execute_tasks(self, context: AgentContext) -> None:
        """Execute tasks based on classified intent."""
        intent = context.intent

        if intent.task_type == TaskType.COMBINED:
            # Execute both search and monitoring
            self._execute_task(context, TaskType.WEB_SEARCH)
            self._execute_task(context, TaskType.SYSTEM_MONITOR)
        elif intent.task_type == TaskType.HEALTH_REPORT:
            # Execute health report
            self._execute_task(context, TaskType.HEALTH_REPORT)
        elif intent.task_type != TaskType.UNKNOWN:
            # Execute single task
            self._execute_task(context, intent.task_type)
        else:
            logger.warning(f"Unknown task type: {intent.task_type}")

    def _execute_task(self, context: AgentContext, task_type: TaskType) -> None:
        """Execute a single task and store result in context."""
        if task_type not in self.task_handlers:
            logger.warning(f"No handler registered for {task_type.value}")
            return

        handler = self.task_handlers[task_type]
        intent = context.intent

        try:
            if self.enable_logging:
                logger.info(f"Executing task: {task_type.value}")

            # Call handler with context, intent data, and parameters
            result = handler(context, intent)
            context.add_result(result)

            if self.enable_logging:
                logger.info(
                    f"Task {task_type.value} completed "
                    f"(success: {result.success}, {result.execution_time_ms:.1f}ms)"
                )
        except Exception as e:
            logger.error(f"Task {task_type.value} failed: {e}", exc_info=True)
            error_result = TaskResult(
                task_type=task_type,
                success=False,
                data={},
                error=str(e),
            )
            context.add_result(error_result)


def create_hermes_agent_with_modules(
    enable_logging: bool = True,
    llm_client: Optional[Any] = None,
    use_llm: bool = True,
) -> tuple:
    """
    Factory function to create a fully configured Hermes agent with module handlers.

    This updated version supports both LLM and keyword-based classification.

    Args:
        enable_logging: Enable logging.
        llm_client: LLM API client (e.g., Anthropic Anthropic.Anthropic())
                   If None and use_llm=True, will attempt to create one
        use_llm: Enable LLM-based classification

    Returns:
        Tuple of (agent, context_example).

    Example:
        # With LLM (Claude API)
        from anthropic import Anthropic
        client = Anthropic()
        agent, _ = create_hermes_agent_with_modules(
            llm_client=client,
            use_llm=True
        )

        # Keyword-only (no LLM)
        agent, _ = create_hermes_agent_with_modules(use_llm=False)
    """
    from .web_search import WebSearchClient
    from .system_monitor import SystemMonitor
    from .url_security import URLSecurityHandler

    # Create agent with specified configuration
    agent = HermesAgent(
        enable_logging=enable_logging,
        llm_client=llm_client,
        llm_confidence_threshold=0.7,
        use_llm=use_llm,
    )

    # Initialize modules
    monitor = SystemMonitor(enable_logging=False)
    url_handler = URLSecurityHandler(enable_logging=False)

    try:
        search_client = WebSearchClient()
        search_enabled = True
    except ValueError:
        search_client = None
        search_enabled = False

    # Web Search Handler
    def handle_web_search(context: AgentContext, intent: Intent) -> TaskResult:
        """Handle web search tasks using LLM-extracted parameters."""
        if not search_enabled:
            return TaskResult(
                task_type=TaskType.WEB_SEARCH,
                success=False,
                data={},
                error="Web search not configured (missing API key)",
            )

        start_time = time.time()
        try:
            # Use LLM-extracted query if available
            query = intent.parameters.get("search_query", intent.primary_query)
            max_results = intent.parameters.get("max_results", 5)

            logger.debug(f"Searching: '{query}' (max_results: {max_results})")
            results = search_client.search(query, max_results=max_results)
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.WEB_SEARCH,
                success=True,
                data={
                    "query": query,
                    "results_count": len(results),
                    "results": [r.to_dict() for r in results],
                    "entities": [
                        {
                            "entity_type": e.entity_type,
                            "value": e.value,
                            "confidence": e.confidence,
                        }
                        for e in intent.entities
                        if e.entity_type == "search_query"
                    ],
                },
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return TaskResult(
                task_type=TaskType.WEB_SEARCH,
                success=False,
                data={},
                error=str(e),
            )

    # System Monitor Handler
    def handle_system_monitor(context: AgentContext, intent: Intent) -> TaskResult:
        """Handle system monitoring tasks."""
        start_time = time.time()
        try:
            cpu = monitor.get_cpu_usage()
            mem = monitor.get_memory_usage()
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.SYSTEM_MONITOR,
                success=True,
                data={
                    "cpu": cpu.to_dict(),
                    "memory": mem.to_dict(),
                    "entities": [
                        {
                            "entity_type": e.entity_type,
                            "value": e.value,
                            "confidence": e.confidence,
                        }
                        for e in intent.entities
                    ],
                },
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return TaskResult(
                task_type=TaskType.SYSTEM_MONITOR,
                success=False,
                data={},
                error=str(e),
            )

    # Health Report Handler
    def handle_health_report(context: AgentContext, intent: Intent) -> TaskResult:
        """Handle system health report tasks."""
        start_time = time.time()
        try:
            health = monitor.get_system_health()
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.HEALTH_REPORT,
                success=True,
                data=health,
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return TaskResult(
                task_type=TaskType.HEALTH_REPORT,
                success=False,
                data={},
                error=str(e),
            )

    # Port Check Handler
    def handle_port_check(context: AgentContext, intent: Intent) -> TaskResult:
        """Handle port checking tasks using LLM-extracted port number."""
        start_time = time.time()
        try:
            # Use LLM-extracted port if available
            port = intent.parameters.get("port", 80)

            # Extract port from entities if not in parameters
            for entity in intent.entities:
                if entity.entity_type == "port_number":
                    port = entity.value
                    break

            is_listening = monitor.is_port_listening(port)
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.PORT_CHECK,
                success=True,
                data={
                    "port": port,
                    "is_listening": is_listening,
                    "entities": [
                        {
                            "entity_type": e.entity_type,
                            "value": e.value,
                            "confidence": e.confidence,
                        }
                        for e in intent.entities
                        if e.entity_type == "port_number"
                    ],
                },
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return TaskResult(
                task_type=TaskType.PORT_CHECK,
                success=False,
                data={},
                error=str(e),
            )

    # URL Check Handler
    def handle_url_check(context: AgentContext, intent: Intent) -> TaskResult:
        """Handle URL security assessment tasks."""
        start_time = time.time()
        try:
            # Extract URL from intent
            url = intent.parameters.get("url", intent.primary_query)

            # Assess URL
            result = url_handler.check_url(url)
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.URL_CHECK,
                success=True,
                data={
                    "url": url,
                    "defanged_url": result["defanged_url"],
                    "risk_level": result["risk_level"],
                    "safe_to_visit": result["safe_to_visit"],
                    "assessment": result["assessment"],
                    "recommendations": result["recommendations"],
                    "entities": [
                        {
                            "entity_type": "url",
                            "value": url,
                            "confidence": 0.95,
                        }
                    ],
                },
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return TaskResult(
                task_type=TaskType.URL_CHECK,
                success=False,
                data={},
                error=str(e),
            )

    # Register handlers
    agent.register_handler(TaskType.WEB_SEARCH, handle_web_search)
    agent.register_handler(TaskType.SYSTEM_MONITOR, handle_system_monitor)
    agent.register_handler(TaskType.HEALTH_REPORT, handle_health_report)
    agent.register_handler(TaskType.PORT_CHECK, handle_port_check)
    agent.register_handler(TaskType.URL_CHECK, handle_url_check)

    return agent, None
