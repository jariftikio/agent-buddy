#!/usr/bin/env python3
"""
Asynchronous Task Routing & Event Loop Orchestrator

Layer 5 Async Upgrade:
- Non-blocking concurrent task execution
- Real-time telemetry buffering
- Graceful timeout protection
- Backward compatible with v2.0 defensive filtering
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ExecutionTelemetry:
    """Structured telemetry for async task execution"""
    task_id: str
    task_type: str
    status: TaskStatus = TaskStatus.PENDING
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    result: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "result": self.result,
        }


class TelemetryBuffer:
    """Real-time telemetry collection with Bengali formatting"""

    def __init__(self, max_size: int = 100):
        self.buffer: deque = deque(maxlen=max_size)
        self.lock = asyncio.Lock()

    async def add(self, telemetry: ExecutionTelemetry) -> None:
        """Add telemetry entry"""
        async with self.lock:
            self.buffer.append(telemetry)
            await self._log_telemetry(telemetry)

    async def _log_telemetry(self, telemetry: ExecutionTelemetry) -> None:
        """Log telemetry with Bengali formatting"""
        status_emoji = {
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.TIMEOUT: "⏱️",
            TaskStatus.RUNNING: "⚙️",
        }

        emoji = status_emoji.get(telemetry.status, "❓")

        if telemetry.status == TaskStatus.COMPLETED:
            logger.info(
                f"{emoji} টাস্ক সম্পন্ন: {telemetry.task_type} ({telemetry.duration_ms:.2f}ms)"
            )
        elif telemetry.status == TaskStatus.FAILED:
            logger.error(
                f"{emoji} টাস্ক ব্যর্থ: {telemetry.task_type} - {telemetry.error}"
            )
        elif telemetry.status == TaskStatus.TIMEOUT:
            logger.warning(
                f"{emoji} টাস্ক সময়সীমা অতিক্রম: {telemetry.task_type}"
            )

    async def get_summary(self) -> Dict[str, Any]:
        """Get telemetry summary"""
        async with self.lock:
            total = len(self.buffer)
            completed = sum(1 for t in self.buffer if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in self.buffer if t.status == TaskStatus.FAILED)
            timeout = sum(1 for t in self.buffer if t.status == TaskStatus.TIMEOUT)
            avg_duration = (
                sum(t.duration_ms for t in self.buffer if t.duration_ms > 0) /
                max(completed, 1)
            )

            return {
                "total_tasks": total,
                "completed": completed,
                "failed": failed,
                "timeout": timeout,
                "average_duration_ms": avg_duration,
            }


class AsyncTaskQueue:
    """Non-blocking concurrent task queue with timeout protection"""

    def __init__(
        self,
        max_workers: int = 4,
        default_timeout: float = 30.0,
        telemetry_buffer: Optional[TelemetryBuffer] = None,
    ):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.semaphore = asyncio.Semaphore(max_workers)
        self.tasks: Dict[str, asyncio.Task] = {}
        self.telemetry = telemetry_buffer or TelemetryBuffer()
        self.lock = asyncio.Lock()

    async def submit_task(
        self,
        task_id: str,
        task_type: str,
        coro: Any,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Submit async task to queue.

        Args:
            task_id: Unique task identifier
            task_type: Type of task (e.g., "web_search", "system_monitor")
            coro: Coroutine to execute
            timeout: Task timeout in seconds (uses default if None)

        Returns:
            Task ID
        """
        timeout = timeout or self.default_timeout
        telemetry = ExecutionTelemetry(task_id=task_id, task_type=task_type)

        async def wrapped_task():
            async with self.semaphore:
                telemetry.status = TaskStatus.RUNNING
                try:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                    telemetry.status = TaskStatus.COMPLETED
                    telemetry.result = result
                    telemetry.end_time = time.time()
                    telemetry.duration_ms = (telemetry.end_time - telemetry.start_time) * 1000
                    await self.telemetry.add(telemetry)
                    return result

                except asyncio.TimeoutError:
                    telemetry.status = TaskStatus.TIMEOUT
                    telemetry.error = f"Timeout after {timeout}s"
                    telemetry.end_time = time.time()
                    telemetry.duration_ms = (telemetry.end_time - telemetry.start_time) * 1000
                    await self.telemetry.add(telemetry)
                    logger.warning(f"⏱️ টাস্ক সময়সীমা: {task_id}")
                    return {
                        "ok": False,
                        "error": "timeout",
                        "response": "⏱️ অনুরোধটি সময়মত সম্পন্ন হয়নি। পরে আবার চেষ্টা করুন।"
                    }

                except Exception as e:
                    telemetry.status = TaskStatus.FAILED
                    telemetry.error = str(e)
                    telemetry.end_time = time.time()
                    telemetry.duration_ms = (telemetry.end_time - telemetry.start_time) * 1000
                    await self.telemetry.add(telemetry)
                    logger.error(f"❌ টাস্ক ব্যর্থ {task_id}: {e}")
                    return {
                        "ok": False,
                        "error": "execution_failed",
                        "response": f"⚠️ {task_type} প্রসেসিং ত্রুটি: {str(e)}"
                    }

        task = asyncio.create_task(wrapped_task())
        async with self.lock:
            self.tasks[task_id] = task

        return task_id

    async def get_result(self, task_id: str, wait: bool = True) -> Optional[Any]:
        """
        Get task result.

        Args:
            task_id: Task identifier
            wait: If True, wait for completion; if False, return None if pending

        Returns:
            Task result or None
        """
        async with self.lock:
            task = self.tasks.get(task_id)

        if not task:
            return None

        if wait:
            return await task
        else:
            if task.done():
                return task.result()
            return None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel pending task"""
        async with self.lock:
            task = self.tasks.get(task_id)

        if task and not task.done():
            task.cancel()
            return True
        return False

    async def get_telemetry_summary(self) -> Dict[str, Any]:
        """Get telemetry summary"""
        return await self.telemetry.get_summary()


class AsyncHermesExecutor:
    """Non-blocking Hermes agent execution with async task routing"""

    def __init__(
        self,
        ai_service: Any,
        max_workers: int = 4,
        default_timeout: float = 30.0,
    ):
        self.ai_service = ai_service
        self.task_queue = AsyncTaskQueue(
            max_workers=max_workers,
            default_timeout=default_timeout,
        )
        self.telemetry = self.task_queue.telemetry

    async def execute_defensive_filtered_request(
        self,
        message: str,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Execute request through v2.0 defensive filtering with async routing.

        Maintains backward compatibility with existing defensive routing rules
        while adding non-blocking execution.
        """
        task_id = f"req_{session_id}_{int(time.time() * 1000)}"

        async def process():
            # This calls existing AIService (synchronous)
            # In a fully async system, this would be wrapped
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.ai_service.generate_reply,
                message,
                session_id,
            )

        await self.task_queue.submit_task(
            task_id=task_id,
            task_type="defensive_filter_request",
            coro=process(),
            timeout=30.0,
        )

        return {"task_id": task_id}

    async def execute_concurrent_handlers(
        self,
        message: str,
        session_id: str = "default",
        handlers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute multiple handlers concurrently (e.g., web search + system monitor).

        Args:
            message: User query
            session_id: Conversation session ID
            handlers: List of handler types to execute

        Returns:
            Results from all concurrent handlers
        """
        handlers = handlers or ["search", "monitor"]
        task_ids = []

        for handler in handlers:
            task_id = f"{handler}_{session_id}_{int(time.time() * 1000)}"

            async def handler_coro(h=handler):
                loop = asyncio.get_event_loop()
                # Dispatch to appropriate handler
                if h == "search":
                    return await loop.run_in_executor(
                        None,
                        self._execute_search,
                        message,
                    )
                elif h == "monitor":
                    return await loop.run_in_executor(
                        None,
                        self._execute_monitor,
                        message,
                    )

            await self.task_queue.submit_task(
                task_id=task_id,
                task_type=f"handler_{handler}",
                coro=handler_coro(),
                timeout=15.0,  # Per-handler timeout
            )
            task_ids.append(task_id)

        return {
            "concurrent_tasks": task_ids,
            "count": len(task_ids),
        }

    def _execute_search(self, query: str) -> Dict[str, Any]:
        """Execute web search handler (sync wrapper)"""
        # This would call WebSearchClient
        return {
            "type": "search",
            "query": query,
            "status": "executing",
        }

    def _execute_monitor(self, query: str) -> Dict[str, Any]:
        """Execute system monitor handler (sync wrapper)"""
        # This would call SystemMonitor
        return {
            "type": "monitor",
            "query": query,
            "status": "executing",
        }

    async def stream_telemetry_reports(self) -> None:
        """Stream telemetry updates as tasks complete"""
        logger.info("🔄 টেলিমেট্রি স্ট্রিমিং শুরু...")
        while True:
            await asyncio.sleep(1)
            summary = await self.task_queue.get_telemetry_summary()
            logger.info(
                f"📊 রিয়েল-টাইম টেলিমেট্রি: "
                f"সম্পন্ন={summary['completed']}, "
                f"ব্যর্থ={summary['failed']}, "
                f"সময়সীমা={summary['timeout']}"
            )


# Background event loop helper
_global_loop: Optional[asyncio.AbstractEventLoop] = None
_global_executor: Optional[AsyncHermesExecutor] = None


def initialize_async_executor(ai_service: Any) -> AsyncHermesExecutor:
    """Initialize global async executor"""
    global _global_executor
    _global_executor = AsyncHermesExecutor(ai_service)
    return _global_executor


def get_async_executor() -> AsyncHermesExecutor:
    """Get global async executor"""
    if _global_executor is None:
        raise RuntimeError("Async executor not initialized")
    return _global_executor
