"""
SQLite database operations for PM tasks.
Implements schema from spec.md Section 8.2.
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from .models import (
    PMTask,
    TaskStatus,
    TaskPriority,
    ProgressUpdate,
    UpdateSource,
    VerificationRecord,
    VerificationMethod,
)

# Default database path - can be overridden via environment
DEFAULT_DB_PATH = os.environ.get("PM_DATABASE_PATH", "/app/output/pm/tasks.db")


def get_db_path() -> str:
    """Get database path, creating directory if needed."""
    db_path = os.environ.get("PM_DATABASE_PATH", DEFAULT_DB_PATH)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


@contextmanager
def get_connection(db_path: Optional[str] = None):
    """Context manager for database connections."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: Optional[str] = None) -> None:
    """Initialize database with PM schema from spec.md Section 8.2."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'defined',
                slack_channel TEXT NOT NULL,
                slack_thread_ts TEXT,
                assignee TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                due_date TEXT,
                priority TEXT DEFAULT 'medium',
                tags TEXT,
                metadata TEXT
            )
        """)

        # Progress updates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                sentiment_score REAL,
                agent_analysis TEXT
            )
        """)

        # Verifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verifications (
                task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
                verified_by TEXT NOT NULL,
                verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                method TEXT NOT NULL,
                evidence TEXT
            )
        """)

        # Indexes for common queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_channel ON tasks(slack_channel)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_progress_task ON progress_updates(task_id)"
        )


def create_task_record(task: PMTask, db_path: Optional[str] = None) -> PMTask:
    """Insert a new task into the database."""
    init_database(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO tasks (
                id, title, description, status, slack_channel,
                slack_thread_ts, assignee, created_at, updated_at,
                due_date, priority, tags, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.title,
                task.description,
                task.status.value,
                task.slack_channel,
                task.slack_thread_ts,
                task.assignee,
                task.created_at,
                task.updated_at,
                task.due_date,
                task.priority.value,
                json.dumps(task.tags),
                json.dumps(task.metadata),
            ),
        )

    return task


def get_task_by_id(task_id: str, db_path: Optional[str] = None) -> Optional[PMTask]:
    """Retrieve a task by ID with all related data."""
    init_database(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get task
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Get progress updates
        cursor.execute(
            "SELECT * FROM progress_updates WHERE task_id = ? ORDER BY timestamp",
            (task_id,),
        )
        updates = cursor.fetchall()

        # Get verification
        cursor.execute(
            "SELECT * FROM verifications WHERE task_id = ?", (task_id,)
        )
        verification_row = cursor.fetchone()

        # Build task object
        task_data = dict(row)
        task_data["tags"] = json.loads(task_data.get("tags") or "[]")
        task_data["metadata"] = json.loads(task_data.get("metadata") or "{}")

        task_data["progress_updates"] = [
            {
                "timestamp": u["timestamp"],
                "source": u["source"],
                "content": u["content"],
                "sentiment_score": u["sentiment_score"],
                "agent_analysis": u["agent_analysis"],
            }
            for u in updates
        ]

        if verification_row:
            task_data["verification"] = {
                "verified_by": verification_row["verified_by"],
                "verified_at": verification_row["verified_at"],
                "method": verification_row["method"],
                "evidence": json.loads(verification_row.get("evidence") or "[]"),
            }

        return PMTask.from_dict(task_data)


def update_task_record(
    task_id: str,
    status: Optional[TaskStatus] = None,
    assignee: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: Optional[TaskPriority] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
    db_path: Optional[str] = None,
) -> Optional[PMTask]:
    """Update task fields. Returns updated task or None if not found."""
    init_database(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Build update query dynamically
        updates = []
        params = []

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if assignee is not None:
            updates.append("assignee = ?")
            params.append(assignee)
        if due_date is not None:
            updates.append("due_date = ?")
            params.append(due_date)
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority.value)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return get_task_by_id(task_id, db_path)

        updates.append("updated_at = ?")
        params.append(datetime.utcnow().isoformat())
        params.append(task_id)

        cursor.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
            params,
        )

    return get_task_by_id(task_id, db_path)


def add_progress_update(
    task_id: str,
    content: str,
    source: UpdateSource = UpdateSource.AGENT,
    sentiment_score: Optional[float] = None,
    agent_analysis: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[ProgressUpdate]:
    """Add a progress update to a task."""
    init_database(db_path)

    timestamp = datetime.utcnow().isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Verify task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return None

        cursor.execute(
            """
            INSERT INTO progress_updates (
                task_id, timestamp, source, content, sentiment_score, agent_analysis
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, timestamp, source.value, content, sentiment_score, agent_analysis),
        )

        # Update task's updated_at
        cursor.execute(
            "UPDATE tasks SET updated_at = ? WHERE id = ?",
            (timestamp, task_id),
        )

    return ProgressUpdate(
        timestamp=timestamp,
        source=source,
        content=content,
        sentiment_score=sentiment_score,
        agent_analysis=agent_analysis,
    )


def set_verification(
    task_id: str,
    verified_by: str,
    method: VerificationMethod,
    evidence: list[str],
    db_path: Optional[str] = None,
) -> Optional[VerificationRecord]:
    """Set or update verification record for a task."""
    init_database(db_path)

    timestamp = datetime.utcnow().isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Verify task exists
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return None

        cursor.execute(
            """
            INSERT OR REPLACE INTO verifications (
                task_id, verified_by, verified_at, method, evidence
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, verified_by, timestamp, method.value, json.dumps(evidence)),
        )

        # Update task status to completed if not already
        cursor.execute(
            "UPDATE tasks SET status = 'completed', updated_at = ? WHERE id = ?",
            (timestamp, task_id),
        )

    return VerificationRecord(
        verified_by=verified_by,
        verified_at=timestamp,
        method=method,
        evidence=evidence,
    )


def get_tasks_by_status_query(
    statuses: list[TaskStatus],
    slack_channel: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[PMTask]:
    """Query tasks by status with optional channel filter."""
    init_database(db_path)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(statuses))
        query = f"SELECT * FROM tasks WHERE status IN ({placeholders})"
        params: list = [s.value for s in statuses]

        if slack_channel:
            query += " AND slack_channel = ?"
            params.append(slack_channel)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task_id = row["id"]
            task = get_task_by_id(task_id, db_path)
            if task:
                tasks.append(task)

        return tasks


def get_tasks_due_soon(
    days: int = 3,
    slack_channel: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[PMTask]:
    """Get tasks with due dates within specified days."""
    init_database(db_path)

    from datetime import timedelta

    cutoff = (datetime.utcnow() + timedelta(days=days)).isoformat()

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        query = """
            SELECT * FROM tasks
            WHERE due_date IS NOT NULL
            AND due_date <= ?
            AND status NOT IN ('completed')
        """
        params: list = [cutoff]

        if slack_channel:
            query += " AND slack_channel = ?"
            params.append(slack_channel)

        query += " ORDER BY due_date ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task = get_task_by_id(row["id"], db_path)
            if task:
                tasks.append(task)

        return tasks
