"""
PM-specific MCP tools for Slack-Based AI PM system.

This module extends TrendRadar's MCP server with project management tools:
- Task CRUD operations
- Boss report generation
- Slack message formatting and pushing

Usage:
    Mount this module into TrendRadar container or run as standalone MCP server.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import requests


class TaskStatus(str, Enum):
    DEFINED = "defined"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PMTask:
    """Task data model matching spec.md schema."""
    id: str
    title: str
    description: str
    status: TaskStatus
    slack_channel: str
    slack_thread_ts: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: list[str] = None
    created_at: str = None
    updated_at: str = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at


class PMDatabase:
    """SQLite database operations for PM tasks."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv("PM_DATABASE_PATH", "data/pm/tasks.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema from spec.md."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
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
                );

                CREATE TABLE IF NOT EXISTS progress_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT REFERENCES tasks(id),
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sentiment_score REAL,
                    agent_analysis TEXT
                );

                CREATE TABLE IF NOT EXISTS verifications (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(id),
                    verified_by TEXT NOT NULL,
                    verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    method TEXT NOT NULL,
                    evidence TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
                CREATE INDEX IF NOT EXISTS idx_progress_task_id ON progress_updates(task_id);
            """)

    def _row_to_task(self, row: tuple, columns: list[str]) -> PMTask:
        """Convert database row to PMTask object."""
        data = dict(zip(columns, row))
        data["tags"] = json.loads(data.get("tags") or "[]")
        data["status"] = TaskStatus(data["status"])
        data["priority"] = TaskPriority(data["priority"])
        return PMTask(**{k: v for k, v in data.items() if k in PMTask.__dataclass_fields__})

    def create_task(self, task: PMTask) -> PMTask:
        """Create a new task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO tasks
                   (id, title, description, status, slack_channel, slack_thread_ts,
                    assignee, due_date, priority, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task.id, task.title, task.description, task.status.value,
                 task.slack_channel, task.slack_thread_ts, task.assignee,
                 task.due_date, task.priority.value, json.dumps(task.tags),
                 task.created_at, task.updated_at)
            )
        return task

    def get_task(self, task_id: str) -> Optional[PMTask]:
        """Get task by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return self._row_to_task(tuple(row), row.keys())
        return None

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        verification: dict = None
    ) -> Optional[PMTask]:
        """Update task status and optionally add verification record."""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.utcnow().isoformat()
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, task_id)
            )
            if verification:
                conn.execute(
                    """INSERT OR REPLACE INTO verifications
                       (task_id, verified_by, verified_at, method, evidence)
                       VALUES (?, ?, ?, ?, ?)""",
                    (task_id, verification.get("verified_by", "agent"),
                     verification.get("verified_at", now),
                     verification.get("method", "automated"),
                     json.dumps(verification.get("evidence", [])))
                )
        return self.get_task(task_id)

    def add_progress_update(
        self,
        task_id: str,
        content: str,
        source: str = "agent",
        sentiment_score: float = None,
        agent_analysis: str = None
    ) -> dict:
        """Add progress update to a task."""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                """INSERT INTO progress_updates
                   (task_id, timestamp, source, content, sentiment_score, agent_analysis)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, now, source, content, sentiment_score, agent_analysis)
            )
            conn.execute(
                "UPDATE tasks SET updated_at = ? WHERE id = ?",
                (now, task_id)
            )
            return {
                "id": cursor.lastrowid,
                "task_id": task_id,
                "timestamp": now,
                "source": source,
                "content": content
            }

    def get_task_progress(self, task_id: str) -> list[dict]:
        """Get all progress updates for a task."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM progress_updates
                   WHERE task_id = ? ORDER BY timestamp DESC""",
                (task_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def list_tasks(
        self,
        status: list[TaskStatus] = None,
        due_before: str = None,
        updated_since: str = None,
        limit: int = 50
    ) -> list[PMTask]:
        """List tasks with optional filters."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            placeholders = ",".join("?" * len(status))
            query += f" AND status IN ({placeholders})"
            params.extend([s.value for s in status])

        if due_before:
            query += " AND due_date <= ?"
            params.append(due_before)

        if updated_since:
            query += " AND updated_at >= ?"
            params.append(updated_since)

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(tuple(row), row.keys()) for row in rows]

    def get_task_counts_by_status(self) -> dict[str, int]:
        """Get count of tasks by status."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM tasks GROUP BY status"
            ).fetchall()
            return {row[0]: row[1] for row in rows}


class SlackPusher:
    """Slack webhook integration for pushing messages."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL not configured")

    def push_message(
        self,
        channel: str,
        text: str = None,
        blocks: list[dict] = None,
        thread_ts: str = None,
        max_retries: int = 3
    ) -> dict:
        """Push message to Slack with retry logic (from spec.md)."""
        payload = {"channel": channel}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10
                )
                if response.status_code == 200:
                    return {"success": True, "attempt": attempt + 1}
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return {"success": False, "error": str(e), "attempts": max_retries}

        return {"success": False, "error": "Max retries exceeded", "attempts": max_retries}


class PMTools:
    """
    MCP tools for PM workflows.

    These tools are designed to be called from cc-wf-studio workflows
    and oh-my-opencode agents via the MCP protocol.
    """

    def __init__(self, db: PMDatabase = None, slack: SlackPusher = None):
        self.db = db or PMDatabase()
        try:
            self.slack = slack or SlackPusher()
        except ValueError:
            self.slack = None  # Slack not configured

    # -------------------------------------------------------------------------
    # MCP Tool: create_task
    # -------------------------------------------------------------------------
    def create_task(
        self,
        title: str,
        description: str,
        slack_channel: str,
        assignee: str = None,
        due_date: str = None,
        priority: str = "medium",
        tags: list[str] = None
    ) -> dict:
        """
        Create a new PM task.

        Parameters:
            title: Task title
            description: Detailed task description
            slack_channel: Slack channel for notifications
            assignee: Optional assignee
            due_date: Optional due date (ISO format)
            priority: low, medium, high, critical
            tags: Optional list of tags

        Returns:
            Created task object
        """
        import uuid
        task = PMTask(
            id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            status=TaskStatus.DEFINED,
            slack_channel=slack_channel,
            assignee=assignee,
            due_date=due_date,
            priority=TaskPriority(priority),
            tags=tags or []
        )
        created = self.db.create_task(task)
        return asdict(created)

    # -------------------------------------------------------------------------
    # MCP Tool: update_task_status
    # -------------------------------------------------------------------------
    def update_task_status(
        self,
        task_id: str,
        status: str,
        verification: dict = None
    ) -> dict:
        """
        Update task status (referenced by task-completion-verification workflow).

        Parameters:
            task_id: Task identifier
            status: New status (defined, in_progress, review, completed, blocked)
            verification: Optional verification record with:
                - verified_by: "user" or "agent"
                - verified_at: ISO timestamp
                - method: "manual", "automated", "hybrid"
                - evidence: List of evidence strings

        Returns:
            Updated task object or error
        """
        try:
            task_status = TaskStatus(status)
        except ValueError:
            return {"error": f"Invalid status: {status}"}

        updated = self.db.update_task_status(task_id, task_status, verification)
        if updated:
            return asdict(updated)
        return {"error": f"Task not found: {task_id}"}

    # -------------------------------------------------------------------------
    # MCP Tool: get_task_progress
    # -------------------------------------------------------------------------
    def get_task_progress(self, task_id: str) -> dict:
        """
        Get task details and progress updates.

        Parameters:
            task_id: Task identifier

        Returns:
            Task object with progress_updates array
        """
        task = self.db.get_task(task_id)
        if not task:
            return {"error": f"Task not found: {task_id}"}

        progress = self.db.get_task_progress(task_id)
        result = asdict(task)
        result["progress_updates"] = progress
        return result

    # -------------------------------------------------------------------------
    # MCP Tool: add_progress_update
    # -------------------------------------------------------------------------
    def add_progress_update(
        self,
        task_id: str,
        content: str,
        source: str = "agent",
        sentiment_score: float = None
    ) -> dict:
        """
        Add a progress update to a task.

        Parameters:
            task_id: Task identifier
            content: Update content/message
            source: Update source (slack, agent, manual)
            sentiment_score: Optional sentiment score (-1 to 1)

        Returns:
            Created progress update
        """
        task = self.db.get_task(task_id)
        if not task:
            return {"error": f"Task not found: {task_id}"}

        return self.db.add_progress_update(task_id, content, source, sentiment_score)

    # -------------------------------------------------------------------------
    # MCP Tool: generate_boss_report
    # -------------------------------------------------------------------------
    def generate_boss_report(
        self,
        date: str = None,
        include_highlights: bool = True,
        include_risks: bool = True
    ) -> dict:
        """
        Generate formatted boss report (matches spec.md format).

        Parameters:
            date: Report date (ISO format), defaults to today
            include_highlights: Include task highlights
            include_risks: Include risk items

        Returns:
            Formatted report with counts, highlights, and risks
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        # Get task counts
        counts = self.db.get_task_counts_by_status()

        # Get recently updated tasks for highlights
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        recent_tasks = self.db.list_tasks(updated_since=yesterday)

        highlights = []
        risks = []

        for task in recent_tasks:
            if task.status == TaskStatus.COMPLETED:
                highlights.append(f"Completed: {task.title}")
            elif task.status == TaskStatus.BLOCKED:
                risks.append(f"BLOCKED: {task.title} (assigned: {task.assignee or 'unassigned'})")
            elif task.due_date and task.due_date <= date:
                risks.append(f"OVERDUE: {task.title} (due: {task.due_date})")

        # Get tasks due within 3 days
        due_soon = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")
        upcoming = self.db.list_tasks(
            status=[TaskStatus.IN_PROGRESS, TaskStatus.DEFINED],
            due_before=due_soon
        )
        for task in upcoming:
            if task not in recent_tasks:
                risks.append(f"Due soon: {task.title} (due: {task.due_date})")

        return {
            "date": date,
            "completed_count": counts.get("completed", 0),
            "in_progress_count": counts.get("in_progress", 0),
            "blocked_count": counts.get("blocked", 0),
            "defined_count": counts.get("defined", 0),
            "review_count": counts.get("review", 0),
            "highlights": highlights if include_highlights else [],
            "risks": risks if include_risks else [],
            "formatted": self._format_boss_report(date, counts, highlights, risks)
        }

    def _format_boss_report(
        self,
        date: str,
        counts: dict,
        highlights: list[str],
        risks: list[str]
    ) -> str:
        """Format report as Slack mrkdwn (matches spec.md template)."""
        report = f"*Daily PM Report - {date}*\n\n"
        report += f"*Completed:* {counts.get('completed', 0)}\n"
        report += f"*In Progress:* {counts.get('in_progress', 0)}\n"
        report += f"*Blocked:* {counts.get('blocked', 0)}\n\n"

        if highlights:
            report += "*Highlights:*\n"
            for h in highlights[:5]:  # Limit to 5
                report += f"\u2022 {h}\n"
            report += "\n"

        if risks:
            report += "*Risks:*\n"
            for r in risks[:5]:  # Limit to 5
                report += f"\u26a0\ufe0f {r}\n"

        return report

    # -------------------------------------------------------------------------
    # MCP Tool: push_to_slack
    # -------------------------------------------------------------------------
    def push_to_slack(
        self,
        channel: str,
        message: dict = None,
        text: str = None,
        thread_ts: str = None
    ) -> dict:
        """
        Push message to Slack (wrapper for webhook).

        Parameters:
            channel: Target Slack channel
            message: Block Kit message (with 'blocks' key)
            text: Simple text message (alternative to blocks)
            thread_ts: Thread timestamp for replies

        Returns:
            Success status and attempt count
        """
        if not self.slack:
            return {"error": "Slack not configured (SLACK_WEBHOOK_URL missing)"}

        blocks = message.get("blocks") if message else None
        return self.slack.push_message(channel, text, blocks, thread_ts)

    # -------------------------------------------------------------------------
    # MCP Tool: list_tasks
    # -------------------------------------------------------------------------
    def list_tasks(
        self,
        status: list[str] = None,
        due_before: str = None,
        updated_since: str = None,
        limit: int = 50
    ) -> dict:
        """
        List tasks with optional filters.

        Parameters:
            status: Filter by status(es)
            due_before: Filter tasks due before date (ISO format)
            updated_since: Filter tasks updated since date (ISO format)
            limit: Max results (default 50)

        Returns:
            List of task objects
        """
        status_enums = None
        if status:
            try:
                status_enums = [TaskStatus(s) for s in status]
            except ValueError as e:
                return {"error": str(e)}

        tasks = self.db.list_tasks(status_enums, due_before, updated_since, limit)
        return {"tasks": [asdict(t) for t in tasks], "count": len(tasks)}


# =============================================================================
# MCP Server Registration (for integration with TrendRadar)
# =============================================================================

def get_tool_schemas() -> list[dict]:
    """
    Return MCP tool schemas for registration.

    These schemas define the tools available via MCP protocol,
    matching the format expected by cc-wf-studio and oh-my-opencode.
    """
    return [
        {
            "name": "create_task",
            "description": "Create a new PM task",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "slack_channel": {"type": "string", "description": "Slack channel"},
                    "assignee": {"type": "string", "description": "Assignee (optional)"},
                    "due_date": {"type": "string", "description": "Due date ISO format (optional)"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium"
                    },
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "description", "slack_channel"]
            }
        },
        {
            "name": "update_task_status",
            "description": "Update task status with optional verification record",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"},
                    "status": {
                        "type": "string",
                        "enum": ["defined", "in_progress", "review", "completed", "blocked"]
                    },
                    "verification": {
                        "type": "object",
                        "description": "Verification record (optional)",
                        "properties": {
                            "verified_by": {"type": "string", "enum": ["user", "agent"]},
                            "method": {"type": "string", "enum": ["manual", "automated", "hybrid"]},
                            "evidence": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "required": ["task_id", "status"]
            }
        },
        {
            "name": "get_task_progress",
            "description": "Get task details and progress updates",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"}
                },
                "required": ["task_id"]
            }
        },
        {
            "name": "add_progress_update",
            "description": "Add a progress update to a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID"},
                    "content": {"type": "string", "description": "Update content"},
                    "source": {
                        "type": "string",
                        "enum": ["slack", "agent", "manual"],
                        "default": "agent"
                    },
                    "sentiment_score": {
                        "type": "number",
                        "description": "Sentiment score -1 to 1 (optional)"
                    }
                },
                "required": ["task_id", "content"]
            }
        },
        {
            "name": "generate_boss_report",
            "description": "Generate formatted daily PM report",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Report date (ISO format)"},
                    "include_highlights": {"type": "boolean", "default": True},
                    "include_risks": {"type": "boolean", "default": True}
                }
            }
        },
        {
            "name": "push_to_slack",
            "description": "Push message to Slack channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Slack channel"},
                    "message": {
                        "type": "object",
                        "description": "Block Kit message",
                        "properties": {
                            "blocks": {"type": "array"}
                        }
                    },
                    "text": {"type": "string", "description": "Simple text message"},
                    "thread_ts": {"type": "string", "description": "Thread timestamp"}
                },
                "required": ["channel"]
            }
        },
        {
            "name": "list_tasks",
            "description": "List tasks with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["defined", "in_progress", "review", "completed", "blocked"]
                        }
                    },
                    "due_before": {"type": "string", "description": "Filter by due date"},
                    "updated_since": {"type": "string", "description": "Filter by update time"},
                    "limit": {"type": "integer", "default": 50}
                }
            }
        }
    ]


# =============================================================================
# CLI Entry Point (for testing)
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PM MCP Tools")
    parser.add_argument("--list-tools", action="store_true", help="List tool schemas")
    parser.add_argument("--test", action="store_true", help="Run basic tests")
    args = parser.parse_args()

    if args.list_tools:
        print(json.dumps(get_tool_schemas(), indent=2))
    elif args.test:
        # Basic test
        tools = PMTools()

        # Create a test task
        result = tools.create_task(
            title="Test Task",
            description="A test task for validation",
            slack_channel="#pm-updates",
            priority="high"
        )
        print(f"Created task: {result['id']}")

        # Add progress
        tools.add_progress_update(
            task_id=result["id"],
            content="Started working on this",
            source="agent"
        )

        # Update status
        tools.update_task_status(result["id"], "in_progress")

        # Get progress
        progress = tools.get_task_progress(result["id"])
        print(f"Task progress: {json.dumps(progress, indent=2)}")

        # Generate report
        report = tools.generate_boss_report()
        print(f"\nBoss Report:\n{report['formatted']}")
    else:
        parser.print_help()
