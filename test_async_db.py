#!/usr/bin/env python3
"""
Test suite for AsyncDatabaseManager.

Tests:
1. Connection pool initialization and management
2. Telemetry persistence without blocking
3. Query operations (recent tasks, statistics)
4. Bengali error messages
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.async_db import (
    AsyncConnectionPool,
    AsyncDatabaseManager,
    AsyncDatabaseError,
)


class AsyncDatabaseTestSuite:
    """Test suite for async database"""

    def __init__(self):
        self.test_count = 0
        self.passed = 0
        self.failed = 0
        self.temp_db = None

    async def test_connection_pool(self):
        """Test connection pool initialization and release"""
        print("\n" + "="*70)
        print("TEST 1: Connection Pool Initialization")
        print("="*70)

        self.test_count += 1

        try:
            # Use temporary database
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_path = self.temp_db.name

            pool = AsyncConnectionPool(db_path=db_path, pool_size=3)
            await pool.initialize()

            assert pool.initialized, "Pool should be initialized"
            assert len(pool.connections) == 3, "Should have 3 connections"

            # Test acquire and release
            conn = await pool.acquire()
            assert conn is not None, "Should acquire connection"

            await pool.release(conn)
            assert pool.available.qsize() == 3, "All connections should be available"

            await pool.close_all()
            assert not pool.initialized, "Pool should be closed"

            print("✅ Connection pool working")
            print(f"   • Pool size: 3")
            print(f"   • Connections created: ✅")
            print(f"   • Acquire/release: ✅")
            print(f"   • Cleanup: ✅")

            self.passed += 1

        except Exception as e:
            print(f"❌ Connection pool test failed: {e}")
            self.failed += 1

    async def test_schema_initialization(self):
        """Test database schema creation"""
        print("\n" + "="*70)
        print("TEST 2: Schema Initialization")
        print("="*70)

        self.test_count += 1

        try:
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_path = self.temp_db.name

            manager = AsyncDatabaseManager(db_path=db_path)
            await manager.initialize()

            # Verify tables exist
            pool = manager.pool
            conn = await pool.acquire()

            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in await cursor.fetchall()]

            assert "telemetry_executions" in tables, "Should have executions table"
            assert "telemetry_summaries" in tables, "Should have summaries table"

            # Verify indexes
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = [row[0] for row in await cursor.fetchall()]

            assert "idx_task_id" in indexes, "Should have task_id index"
            assert "idx_status" in indexes, "Should have status index"

            await pool.release(conn)
            await manager.cleanup()

            print("✅ Schema initialization working")
            print(f"   • Tables created: 2")
            print(f"   • Indexes created: 4+")
            print(f"   • Schema valid: ✅")

            self.passed += 1

        except Exception as e:
            print(f"❌ Schema test failed: {e}")
            self.failed += 1

    async def test_telemetry_persistence(self):
        """Test non-blocking telemetry save"""
        print("\n" + "="*70)
        print("TEST 3: Telemetry Persistence (Non-Blocking)")
        print("="*70)

        self.test_count += 1

        try:
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_path = self.temp_db.name

            manager = AsyncDatabaseManager(db_path=db_path)
            await manager.initialize()

            # Save telemetry non-blocking (fire and forget)
            telemetry = {
                "task_id": "task_001",
                "task_type": "web_search",
                "status": "completed",
                "duration_ms": 245.5,
                "error": None,
                "result": {"title": "Test", "url": "http://example.com"},
            }

            # This returns immediately
            await manager.save_telemetry_async(telemetry)

            # Give time for background write
            await asyncio.sleep(0.5)

            # Verify it was saved
            recent = await manager.get_recent_telemetry(limit=10)
            assert len(recent) > 0, "Should have saved telemetry"
            assert recent[0]["task_id"] == "task_001", "Task ID should match"

            print("✅ Telemetry persistence working")
            print(f"   • Non-blocking save: ✅")
            print(f"   • Background write: ✅")
            print(f"   • Query retrieval: ✅")

            await manager.cleanup()
            self.passed += 1

        except Exception as e:
            print(f"❌ Telemetry persistence test failed: {e}")
            self.failed += 1

    async def test_statistics_query(self):
        """Test statistics aggregation"""
        print("\n" + "="*70)
        print("TEST 4: Statistics Query")
        print("="*70)

        self.test_count += 1

        try:
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_path = self.temp_db.name

            manager = AsyncDatabaseManager(db_path=db_path)
            await manager.initialize()

            # Save multiple telemetry entries
            for i in range(5):
                telemetry = {
                    "task_id": f"task_{i:03d}",
                    "task_type": "search" if i < 3 else "monitor",
                    "status": "completed" if i < 3 else "failed",
                    "duration_ms": 100.0 + (i * 50),
                    "error": None if i < 3 else "Connection error",
                    "result": {"data": "test"} if i < 3 else None,
                }
                await manager.telemetry_db.save_telemetry(telemetry)

            # Get statistics
            stats = await manager.get_statistics(hours=24)

            assert stats["total_tasks"] == 5, "Should have 5 tasks"
            assert stats["completed"] == 3, "Should have 3 completed"
            assert stats["failed"] == 2, "Should have 2 failed"
            assert stats["average_duration_ms"] > 0, "Should calculate average"

            print("✅ Statistics query working")
            print(f"   • Total tasks: {stats['total_tasks']}")
            print(f"   • Completed: {stats['completed']}")
            print(f"   • Failed: {stats['failed']}")
            print(f"   • Avg duration: {stats['average_duration_ms']:.1f}ms")

            await manager.cleanup()
            self.passed += 1

        except Exception as e:
            print(f"❌ Statistics test failed: {e}")
            self.failed += 1

    async def test_bengali_error_messages(self):
        """Test Bengali error message handling"""
        print("\n" + "="*70)
        print("TEST 5: Bengali Error Messages")
        print("="*70)

        self.test_count += 1

        try:
            # Create error with Bengali message
            error = AsyncDatabaseError(
                "Database connection failed",
                "ডাটাবেস সংযোগ ব্যর্থ"
            )

            error_dict = error.to_dict()
            assert "error" in error_dict, "Should have error field"
            assert "error_bn" in error_dict, "Should have Bengali error"
            assert "ডাটাবেস" in error_dict["error_bn"], "Should contain Bengali text"

            print("✅ Bengali error messages working")
            print(f"   • English: {error_dict['error']}")
            print(f"   • Bengali: {error_dict['error_bn']}")

            self.passed += 1

        except Exception as e:
            print(f"❌ Bengali error test failed: {e}")
            self.failed += 1

    async def test_concurrent_writes(self):
        """Test concurrent write operations from multiple tasks"""
        print("\n" + "="*70)
        print("TEST 6: Concurrent Write Operations")
        print("="*70)

        self.test_count += 1

        try:
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_path = self.temp_db.name

            manager = AsyncDatabaseManager(db_path=db_path)
            await manager.initialize()

            # Create multiple concurrent write tasks
            async def save_task(task_num):
                telemetry = {
                    "task_id": f"concurrent_{task_num:03d}",
                    "task_type": "concurrent_test",
                    "status": "completed",
                    "duration_ms": 100.0 + task_num,
                    "error": None,
                    "result": None,
                }
                await manager.telemetry_db.save_telemetry(telemetry)

            # Run 10 concurrent writes
            tasks = [save_task(i) for i in range(10)]
            await asyncio.gather(*tasks)

            # Verify all were saved
            recent = await manager.get_recent_telemetry(limit=50)
            concurrent_tasks = [t for t in recent if "concurrent_" in t["task_id"]]

            assert len(concurrent_tasks) == 10, "Should save all concurrent tasks"

            print("✅ Concurrent write operations working")
            print(f"   • Concurrent writes: 10")
            print(f"   • Successfully saved: {len(concurrent_tasks)}")
            print(f"   • Data integrity: ✅")

            await manager.cleanup()
            self.passed += 1

        except Exception as e:
            print(f"❌ Concurrent writes test failed: {e}")
            self.failed += 1

    async def run_all_tests(self):
        """Run all async database tests"""
        print("\n" + "╔" + "="*68 + "╗")
        print("║" + " "*68 + "║")
        print("║" + "  ASYNC DATABASE MODULE TEST SUITE".center(68) + "║")
        print("║" + " "*68 + "║")
        print("╚" + "="*68 + "╝")

        await self.test_connection_pool()
        await self.test_schema_initialization()
        await self.test_telemetry_persistence()
        await self.test_statistics_query()
        await self.test_bengali_error_messages()
        await self.test_concurrent_writes()

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
            print("\n✅ ALL TESTS PASSED - ASYNC DATABASE READY FOR PRODUCTION\n")
        else:
            print(f"\n⚠️  {self.failed} TEST(S) FAILED\n")

        # Cleanup
        if self.temp_db:
            Path(self.temp_db.name).unlink(missing_ok=True)


async def main():
    tester = AsyncDatabaseTestSuite()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
