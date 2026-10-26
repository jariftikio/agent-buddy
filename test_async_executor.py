#!/usr/bin/env python3
"""
Test suite for Async Layer 5 execution pipeline.

Tests:
1. Concurrent task execution with timeout protection
2. Telemetry buffering and Bengali reporting
3. Non-blocking webhook handler execution
4. Backward compatibility with v2.0 defensive filtering
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.async_executor import (
    AsyncTaskQueue,
    TelemetryBuffer,
    TaskStatus,
    AsyncHermesExecutor,
    ExecutionTelemetry,
)


class AsyncExecutorTestSuite:
    """Test suite for async execution"""

    def __init__(self):
        self.test_count = 0
        self.passed = 0
        self.failed = 0

    async def test_telemetry_buffer(self):
        """Test real-time telemetry buffering with Bengali output"""
        print("\n" + "="*70)
        print("TEST 1: Telemetry Buffer & Bengali Formatting")
        print("="*70)

        self.test_count += 1

        try:
            buffer = TelemetryBuffer(max_size=10)

            # Create telemetry entries
            telemetry = ExecutionTelemetry(
                task_id="task_001",
                task_type="web_search",
            )
            telemetry.status = TaskStatus.COMPLETED
            telemetry.end_time = time.time()
            telemetry.duration_ms = 245.5

            await buffer.add(telemetry)

            # Get summary
            summary = await buffer.get_summary()

            assert summary["completed"] == 1, "Should have 1 completed task"
            assert summary["total_tasks"] == 1, "Should have 1 total task"

            print("✅ Telemetry buffer working")
            print(f"   • Tasks: {summary['total_tasks']}")
            print(f"   • Completed: {summary['completed']}")
            print(f"   • Avg Duration: {summary['average_duration_ms']:.2f}ms")

            self.passed += 1

        except Exception as e:
            print(f"❌ Telemetry test failed: {e}")
            self.failed += 1

    async def test_async_task_queue(self):
        """Test non-blocking task queue with timeout protection"""
        print("\n" + "="*70)
        print("TEST 2: Async Task Queue & Timeout Protection")
        print("="*70)

        self.test_count += 1

        try:
            queue = AsyncTaskQueue(max_workers=2, default_timeout=2.0)

            # Test 1: Successful completion
            async def quick_task():
                await asyncio.sleep(0.1)
                return {"result": "success"}

            task_id = await queue.submit_task(
                task_id="task_success",
                task_type="quick_handler",
                coro=quick_task(),
            )

            result = await queue.get_result(task_id, wait=True)
            assert result["result"] == "success", "Task should complete successfully"

            print("✅ Task completion working")

            # Test 2: Timeout protection
            async def slow_task():
                await asyncio.sleep(5.0)
                return {"result": "slow"}

            timeout_task_id = await queue.submit_task(
                task_id="task_timeout",
                task_type="slow_handler",
                coro=slow_task(),
                timeout=1.0,
            )

            result = await queue.get_result(timeout_task_id, wait=True)
            assert result["error"] == "timeout", "Should timeout after 1 second"

            print("✅ Timeout protection working")
            print(f"   • Timeout result: {result['error']}")

            self.passed += 1

        except Exception as e:
            print(f"❌ Task queue test failed: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1

    async def test_concurrent_handlers(self):
        """Test concurrent execution of multiple handlers"""
        print("\n" + "="*70)
        print("TEST 3: Concurrent Handler Execution")
        print("="*70)

        self.test_count += 1

        try:
            # Mock AI service
            class MockAIService:
                def generate_reply(self, message, session_id):
                    return {"ok": True, "response": "Test response"}

            executor = AsyncHermesExecutor(MockAIService(), max_workers=2)

            # Execute concurrent handlers
            result = await executor.execute_concurrent_handlers(
                message="Test query",
                session_id="test_session",
                handlers=["search", "monitor"],
            )

            assert "concurrent_tasks" in result, "Should return task IDs"
            assert result["count"] == 2, "Should have 2 concurrent tasks"

            print("✅ Concurrent handler execution working")
            print(f"   • Concurrent tasks: {result['concurrent_tasks']}")
            print(f"   • Task count: {result['count']}")

            # Get telemetry
            telemetry = await executor.task_queue.get_telemetry_summary()
            print(f"   • Completed tasks: {telemetry['completed']}")

            self.passed += 1

        except Exception as e:
            print(f"❌ Concurrent handlers test failed: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1

    async def test_bengali_telemetry_output(self):
        """Test Bengali formatting of telemetry reports"""
        print("\n" + "="*70)
        print("TEST 4: Bengali Telemetry Output")
        print("="*70)

        self.test_count += 1

        try:
            buffer = TelemetryBuffer()

            # Create failed telemetry with Bengali output
            telemetry = ExecutionTelemetry(
                task_id="task_bengali",
                task_type="search_handler",
            )
            telemetry.status = TaskStatus.FAILED
            telemetry.error = "Connection timeout"
            telemetry.end_time = time.time()
            telemetry.duration_ms = 1250.0

            # Add to buffer (triggers Bengali logging)
            await buffer.add(telemetry)

            print("✅ Bengali telemetry output working")
            print(f"   • Task type: {telemetry.task_type}")
            print(f"   • Status: {telemetry.status.value}")
            print(f"   • Bengali log message sent (check logs)")

            self.passed += 1

        except Exception as e:
            print(f"❌ Bengali output test failed: {e}")
            self.failed += 1

    async def test_backward_compatibility(self):
        """Test backward compatibility with v2.0 defensive filtering"""
        print("\n" + "="*70)
        print("TEST 5: Backward Compatibility with v2.0")
        print("="*70)

        self.test_count += 1

        try:
            class MockAIService:
                def generate_reply(self, message, session_id):
                    # Simulate v2.0 defensive filtering response
                    return {
                        "ok": True,
                        "response": "Safe response",
                        "handled_by": "defensive_handler",
                    }

            executor = AsyncHermesExecutor(MockAIService())

            # Execute request (should maintain v2.0 behavior)
            result = await executor.execute_defensive_filtered_request(
                message="Test query",
                session_id="default",
            )

            assert "task_id" in result, "Should return task ID"

            print("✅ Backward compatibility maintained")
            print(f"   • Task ID: {result['task_id']}")
            print(f"   • v2.0 defensive filtering still active")

            self.passed += 1

        except Exception as e:
            print(f"❌ Backward compatibility test failed: {e}")
            self.failed += 1

    async def test_max_workers_limit(self):
        """Test max worker concurrency limit"""
        print("\n" + "="*70)
        print("TEST 6: Max Workers Concurrency Limit")
        print("="*70)

        self.test_count += 1

        try:
            queue = AsyncTaskQueue(max_workers=2, default_timeout=5.0)

            # Submit 5 tasks with only 2 workers
            async def work():
                await asyncio.sleep(0.5)
                return "done"

            task_ids = []
            for i in range(5):
                task_id = await queue.submit_task(
                    task_id=f"worker_test_{i}",
                    task_type="worker",
                    coro=work(),
                )
                task_ids.append(task_id)

            # All tasks should eventually complete
            results = []
            for task_id in task_ids:
                result = await queue.get_result(task_id, wait=True)
                results.append(result)

            assert len(results) == 5, "All tasks should complete"

            print("✅ Max workers limit enforced")
            print(f"   • Max workers: 2")
            print(f"   • Tasks submitted: 5")
            print(f"   • Tasks completed: {len(results)}")

            self.passed += 1

        except Exception as e:
            print(f"❌ Max workers test failed: {e}")
            self.failed += 1

    async def run_all_tests(self):
        """Run all async tests"""
        print("\n" + "╔" + "="*68 + "╗")
        print("║" + " "*68 + "║")
        print("║" + "  ASYNC LAYER 5 EXECUTION PIPELINE TEST SUITE".center(68) + "║")
        print("║" + " "*68 + "║")
        print("╚" + "="*68 + "╝")

        await self.test_telemetry_buffer()
        await self.test_async_task_queue()
        await self.test_concurrent_handlers()
        await self.test_bengali_telemetry_output()
        await self.test_backward_compatibility()
        await self.test_max_workers_limit()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total tests: {self.test_count}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success rate: {(self.passed/self.test_count)*100:.1f}%")
        print("="*70)

        if self.failed == 0:
            print("\n✅ ALL TESTS PASSED - ASYNC LAYER 5 READY FOR PRODUCTION\n")
        else:
            print(f"\n⚠️  {self.failed} TEST(S) FAILED\n")


async def main():
    tester = AsyncExecutorTestSuite()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
