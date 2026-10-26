#!/usr/bin/env python3
"""
Asynchronous Database Module for Telemetry Persistence

Provides:
1. Async connection pooling with concurrent read/write operations
2. Non-blocking telemetry persistence from AsyncHermesExecutor
3. Bengali error messages for all database exceptions
4. Safe indexing and schema management
"""

import aiosqlite
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import asdict

logger = logging.getLogger(__name__)


class AsyncDatabaseError(Exception):
    """Base exception for async database operations"""

    def __init__(self, message: str, bengali_message: str):
        self.message = message
        self.bengali_message = bengali_message
        super().__init__(message)

    def to_dict(self) -> Dict[str, str]:
        return {
            "error": self.message,
            "error_bn": self.bengali_message,
        }


class AsyncConnectionPool:
    """
    Asynchronous connection pool for concurrent database access.

    Manages multiple connections with configurable pool size to handle
    concurrent read/write operations from async workers.
    """

    def __init__(
        self,
        db_path: str = "hermes_telemetry.db",
        pool_size: int = 5,
    ):
        self.db_path = Path(db_path).resolve()
        self.pool_size = pool_size
        self.connections: List[aiosqlite.Connection] = []
        self.available: asyncio.Queue = asyncio.Queue()
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize connection pool"""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create connections
            for _ in range(self.pool_size):
                conn = await aiosqlite.connect(str(self.db_path))
                await conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
                await conn.execute("PRAGMA synchronous=NORMAL")  # Balanced safety/speed
                self.connections.append(conn)
                await self.available.put(conn)

            self.initialized = True
            logger.info(f"✅ Database pool initialized: {self.pool_size} connections")
        except Exception as e:
            raise AsyncDatabaseError(
                f"Database initialization failed: {e}",
                f"ডাটাবেস সংযোগ ব্যর্থ: {e}"
            )

    async def acquire(self) -> aiosqlite.Connection:
        """Acquire connection from pool"""
        if not self.initialized:
            raise AsyncDatabaseError(
                "Connection pool not initialized",
                "সংযোগ পুল আরম্ভিত নয়"
            )
        return await self.available.get()

    async def release(self, conn: aiosqlite.Connection) -> None:
        """Release connection back to pool"""
        await self.available.put(conn)

    async def close_all(self) -> None:
        """Close all connections"""
        for conn in self.connections:
            await conn.close()
        self.initialized = False
        logger.info("✅ All database connections closed")


class AsyncTelemetryDatabase:
    """
    Non-blocking telemetry database for storing async task execution metrics.

    Persists telemetry data without blocking the main execution loop.
    """

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def initialize_schema(self) -> None:
        """Create database schema for telemetry storage"""
        conn = await self.pool.acquire()
        try:
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS telemetry_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error TEXT,
                    result_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_task_id ON telemetry_executions(task_id);
                CREATE INDEX IF NOT EXISTS idx_task_type ON telemetry_executions(task_type);
                CREATE INDEX IF NOT EXISTS idx_status ON telemetry_executions(status);
                CREATE INDEX IF NOT EXISTS idx_created_at ON telemetry_executions(created_at);

                CREATE TABLE IF NOT EXISTS telemetry_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary_type TEXT NOT NULL,
                    total_tasks INTEGER NOT NULL,
                    completed INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    timeout INTEGER NOT NULL,
                    average_duration_ms REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_summary_type ON telemetry_summaries(summary_type);
                CREATE INDEX IF NOT EXISTS idx_summary_date ON telemetry_summaries(created_at);
            """)

            await conn.commit()
            logger.info("✅ Telemetry schema initialized")
        except Exception as e:
            raise AsyncDatabaseError(
                f"Schema initialization failed: {e}",
                f"স্কিমা তৈরি ব্যর্থ: {e}"
            )
        finally:
            await self.pool.release(conn)

    async def save_telemetry(self, telemetry: Dict[str, Any]) -> bool:
        """
        Save telemetry execution record to database.

        Non-blocking: Returns immediately after queuing write.

        Args:
            telemetry: Telemetry data from ExecutionTelemetry.to_dict()

        Returns:
            True if saved successfully
        """
        conn = await self.pool.acquire()
        try:
            await conn.execute(
                """
                INSERT INTO telemetry_executions
                (task_id, task_type, status, duration_ms, error, result_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    telemetry.get("task_id"),
                    telemetry.get("task_type"),
                    telemetry.get("status"),
                    telemetry.get("duration_ms", 0.0),
                    telemetry.get("error"),
                    json.dumps(telemetry.get("result")) if telemetry.get("result") else None,
                ),
            )
            await conn.commit()
            return True
        except Exception as e:
            logger.error(f"Telemetry save failed: {e}")
            return False
        finally:
            await self.pool.release(conn)

    async def save_summary(self, summary: Dict[str, Any]) -> bool:
        """
        Save telemetry summary to database.

        Args:
            summary: Summary dict from TelemetryBuffer.get_summary()

        Returns:
            True if saved successfully
        """
        conn = await self.pool.acquire()
        try:
            await conn.execute(
                """
                INSERT INTO telemetry_summaries
                (summary_type, total_tasks, completed, failed, timeout, average_duration_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "periodic",
                    summary.get("total_tasks", 0),
                    summary.get("completed", 0),
                    summary.get("failed", 0),
                    summary.get("timeout", 0),
                    summary.get("average_duration_ms", 0.0),
                ),
            )
            await conn.commit()
            return True
        except Exception as e:
            logger.error(f"Summary save failed: {e}")
            return False
        finally:
            await self.pool.release(conn)

    async def get_recent_tasks(
        self,
        limit: int = 100,
        task_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent telemetry records.

        Args:
            limit: Max records to return
            task_type: Filter by task type (optional)

        Returns:
            List of telemetry records
        """
        conn = await self.pool.acquire()
        try:
            if task_type:
                query = """
                    SELECT task_id, task_type, status, duration_ms, error, created_at
                    FROM telemetry_executions
                    WHERE task_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = await conn.execute(query, (task_type, limit))
            else:
                query = """
                    SELECT task_id, task_type, status, duration_ms, error, created_at
                    FROM telemetry_executions
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = await conn.execute(query, (limit,))

            rows = await cursor.fetchall()
            return [
                {
                    "task_id": row[0],
                    "task_type": row[1],
                    "status": row[2],
                    "duration_ms": row[3],
                    "error": row[4],
                    "created_at": row[5],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
        finally:
            await self.pool.release(conn)

    async def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get execution statistics for recent period.

        Args:
            hours: Time window in hours

        Returns:
            Statistics dict
        """
        conn = await self.pool.acquire()
        try:
            query = """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeout,
                    AVG(duration_ms) as avg_duration,
                    MIN(duration_ms) as min_duration,
                    MAX(duration_ms) as max_duration
                FROM telemetry_executions
                WHERE created_at > datetime('now', '-' || ? || ' hours')
            """
            cursor = await conn.execute(query, (hours,))
            row = await cursor.fetchone()

            return {
                "total_tasks": row[0] or 0,
                "completed": row[1] or 0,
                "failed": row[2] or 0,
                "timeout": row[3] or 0,
                "average_duration_ms": float(row[4]) if row[4] else 0.0,
                "min_duration_ms": float(row[5]) if row[5] else 0.0,
                "max_duration_ms": float(row[6]) if row[6] else 0.0,
                "period_hours": hours,
            }
        except Exception as e:
            logger.error(f"Statistics query failed: {e}")
            return {}
        finally:
            await self.pool.release(conn)


class AsyncDatabaseManager:
    """
    Centralized manager for async database operations.

    Handles initialization, telemetry persistence, and cleanup.
    """

    def __init__(self, db_path: str = "hermes_telemetry.db"):
        self.pool = AsyncConnectionPool(db_path=db_path, pool_size=5)
        self.telemetry_db = AsyncTelemetryDatabase(self.pool)
        self.background_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize database manager"""
        try:
            await self.pool.initialize()
            await self.telemetry_db.initialize_schema()
            logger.info("✅ Async database manager initialized")
        except AsyncDatabaseError as e:
            logger.error(f"❌ {e.bengali_message}")
            raise

    async def save_telemetry_async(self, telemetry: Dict[str, Any]) -> None:
        """
        Non-blocking telemetry save (fire and forget).

        This method returns immediately without waiting for database write.
        """
        # Create background task for non-blocking save
        asyncio.create_task(self.telemetry_db.save_telemetry(telemetry))

    async def save_summary_async(self, summary: Dict[str, Any]) -> None:
        """
        Non-blocking summary save (fire and forget).
        """
        asyncio.create_task(self.telemetry_db.save_summary(summary))

    async def get_recent_telemetry(
        self,
        limit: int = 100,
        task_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent telemetry records"""
        return await self.telemetry_db.get_recent_tasks(limit=limit, task_type=task_type)

    async def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get execution statistics"""
        return await self.telemetry_db.get_statistics(hours=hours)

    async def cleanup(self) -> None:
        """Cleanup database connections"""
        await self.pool.close_all()
        logger.info("✅ Database cleanup complete")


# Global database manager instance
_database_manager: Optional[AsyncDatabaseManager] = None


async def initialize_database(db_path: str = "hermes_telemetry.db") -> AsyncDatabaseManager:
    """Initialize global database manager"""
    global _database_manager
    _database_manager = AsyncDatabaseManager(db_path=db_path)
    await _database_manager.initialize()
    return _database_manager


def get_database() -> AsyncDatabaseManager:
    """Get global database manager instance"""
    if _database_manager is None:
        raise AsyncDatabaseError(
            "Database manager not initialized",
            "ডাটাবেস ম্যানেজার আরম্ভিত নয়"
        )
    return _database_manager
