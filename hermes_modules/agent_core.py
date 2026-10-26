"""
Core agent architecture for Hermes.
Provides intent classification, task routing, and execution orchestration.
"""

import logging
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks the agent can handle."""

    WEB_SEARCH = "web_search"
    SYSTEM_MONITOR = "system_monitor"
    SYSTEM_CHECK = "system_check"
    PORT_CHECK = "port_check"
    HEALTH_REPORT = "health_report"
    COMBINED = "combined"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """Classified user intent."""

    task_type: TaskType
    primary_query: str
    secondary_queries: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_type": self.task_type.value,
            "primary_query": self.primary_query,
            "secondary_queries": self.secondary_queries,
            "parameters": self.parameters,
            "confidence": self.confidence,
        }


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
    """Context for agent execution."""

    session_id: str
    user_input: str
    intent: Optional[Intent] = None
    results: List[TaskResult] = field(default_factory=list)
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


class IntentClassifier:
    """Classifies user input into task types."""

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
    }

    PORT_KEYWORDS = {
        "port",
        "listening",
        "connection",
        "network",
        "process",
        "service",
    }

    @classmethod
    def classify(cls, user_input: str) -> Intent:
        """
        Classify user input into an intent.

        Args:
            user_input: Natural language input from user.

        Returns:
            Intent object with classified task type and parameters.
        """
        lower_input = user_input.lower()
        logger.info(f"Classifying intent: '{user_input}'")

        # Check for combined requests
        has_search_intent = any(kw in lower_input for kw in cls.SEARCH_KEYWORDS)
        has_monitor_intent = any(kw in lower_input for kw in cls.MONITOR_KEYWORDS)
        has_port_intent = any(kw in lower_input for kw in cls.PORT_KEYWORDS)

        # Determine task type
        if has_search_intent and has_monitor_intent:
            task_type = TaskType.COMBINED
            primary_query = cls._extract_search_query(user_input)
            parameters = {
                "search_query": primary_query,
                "check_system": True,
            }
        elif has_search_intent:
            task_type = TaskType.WEB_SEARCH
            primary_query = cls._extract_search_query(user_input)
            parameters = {"search_query": primary_query, "max_results": 5}
        elif has_port_intent:
            task_type = TaskType.PORT_CHECK
            port_num = cls._extract_port_number(user_input)
            primary_query = f"Check port {port_num}"
            parameters = {"port": port_num}
        elif "health" in lower_input or "report" in lower_input:
            task_type = TaskType.HEALTH_REPORT
            primary_query = "Generate system health report"
            parameters = {}
        elif has_monitor_intent:
            task_type = TaskType.SYSTEM_MONITOR
            primary_query = "Check CPU and memory usage"
            parameters = {"include_load_average": True}
        else:
            task_type = TaskType.UNKNOWN
            primary_query = user_input
            parameters = {}

        intent = Intent(
            task_type=task_type,
            primary_query=primary_query,
            parameters=parameters,
            confidence=cls._calculate_confidence(task_type, has_search_intent, has_monitor_intent),
        )

        logger.info(f"Classified as: {task_type.value} (confidence: {intent.confidence:.2f})")
        return intent

    @staticmethod
    def _extract_search_query(user_input: str) -> str:
        """Extract search query from user input."""
        # Remove common prefixes
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
        import re

        match = re.search(r"\b(\d{1,5})\b", user_input)
        if match:
            port = int(match.group(1))
            if 0 < port < 65536:
                return port
        return None

    @staticmethod
    def _calculate_confidence(
        task_type: TaskType, has_search: bool, has_monitor: bool
    ) -> float:
        """Calculate confidence score for classification."""
        if task_type == TaskType.UNKNOWN:
            return 0.5
        elif task_type == TaskType.COMBINED:
            return 0.85
        elif has_search or has_monitor:
            return 0.95
        else:
            return 0.7


class AgentTask(ABC):
    """Abstract base class for agent tasks."""

    @abstractmethod
    async def execute(self, context: AgentContext) -> TaskResult:
        """Execute the task."""
        pass


class HermesAgent:
    """
    Main Hermes agent orchestrator.
    Routes user input to appropriate modules and manages execution.
    """

    def __init__(self, enable_logging: bool = True):
        """
        Initialize the Hermes agent.

        Args:
            enable_logging: Enable logging of agent operations.
        """
        self.enable_logging = enable_logging
        self.classifier = IntentClassifier()
        self.task_handlers: Dict[TaskType, Callable] = {}
        self._session_counter = 0

        if enable_logging:
            logger.setLevel(logging.INFO)
            logger.info("HermesAgent initialized")

    def register_handler(self, task_type: TaskType, handler: Callable) -> None:
        """
        Register a task handler for a task type.

        Args:
            task_type: The type of task to handle.
            handler: Callable that handles the task.
        """
        self.task_handlers[task_type] = handler
        logger.info(f"Registered handler for {task_type.value}")

    def process_input(self, user_input: str) -> AgentContext:
        """
        Process user input and execute appropriate tasks.

        Args:
            user_input: Natural language input from user.

        Returns:
            AgentContext with execution results.
        """
        self._session_counter += 1
        session_id = f"session_{self._session_counter}"

        # Create context
        context = AgentContext(session_id=session_id, user_input=user_input)

        # Classify intent
        intent = self.classifier.classify(user_input)
        context.intent = intent

        if self.enable_logging:
            logger.info(f"[{session_id}] Processing: {user_input}")

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
            # Execute health report (requires system monitor)
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

            # Call handler with context and intent parameters
            result = handler(context, intent.parameters)
            context.add_result(result)

            if self.enable_logging:
                logger.info(f"Task {task_type.value} completed successfully")
        except Exception as e:
            logger.error(f"Task {task_type.value} failed: {e}")
            error_result = TaskResult(
                task_type=task_type,
                success=False,
                data={},
                error=str(e),
            )
            context.add_result(error_result)


def create_hermes_agent_with_modules(
    enable_logging: bool = True,
) -> tuple[HermesAgent, AgentContext]:
    """
    Factory function to create a fully configured Hermes agent with module handlers.

    Args:
        enable_logging: Enable logging.

    Returns:
        Tuple of (agent, example_context).
    """
    from .web_search import WebSearchClient
    from .system_monitor import SystemMonitor
    import time

    agent = HermesAgent(enable_logging=enable_logging)

    # Initialize modules
    monitor = SystemMonitor(enable_logging=False)

    try:
        search_client = WebSearchClient()
        search_enabled = True
    except ValueError:
        search_client = None
        search_enabled = False

    # Web Search Handler
    def handle_web_search(context: AgentContext, params: Dict[str, Any]) -> TaskResult:
        """Handle web search tasks."""
        if not search_enabled:
            return TaskResult(
                task_type=TaskType.WEB_SEARCH,
                success=False,
                data={},
                error="Web search not configured (missing API key)",
            )

        start_time = time.time()
        try:
            query = params.get("search_query", context.intent.primary_query)
            max_results = params.get("max_results", 5)

            results = search_client.search(query, max_results=max_results)
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.WEB_SEARCH,
                success=True,
                data={
                    "query": query,
                    "results_count": len(results),
                    "results": [r.to_dict() for r in results],
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
    def handle_system_monitor(context: AgentContext, params: Dict[str, Any]) -> TaskResult:
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
    def handle_health_report(context: AgentContext, params: Dict[str, Any]) -> TaskResult:
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
    def handle_port_check(context: AgentContext, params: Dict[str, Any]) -> TaskResult:
        """Handle port checking tasks."""
        start_time = time.time()
        try:
            port = params.get("port", 80)
            is_listening = monitor.is_port_listening(port)
            execution_time_ms = (time.time() - start_time) * 1000

            return TaskResult(
                task_type=TaskType.PORT_CHECK,
                success=True,
                data={"port": port, "is_listening": is_listening},
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return TaskResult(
                task_type=TaskType.PORT_CHECK,
                success=False,
                data={},
                error=str(e),
            )

    # Register handlers
    agent.register_handler(TaskType.WEB_SEARCH, handle_web_search)
    agent.register_handler(TaskType.SYSTEM_MONITOR, handle_system_monitor)
    agent.register_handler(TaskType.HEALTH_REPORT, handle_health_report)
    agent.register_handler(TaskType.PORT_CHECK, handle_port_check)

    return agent, None
