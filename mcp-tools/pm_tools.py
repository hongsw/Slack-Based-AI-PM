"""
PM MCP Tools - Project Management tools for TrendRadar MCP server extension.

This module provides PM-specific MCP tools that can be mounted into TrendRadar
or run as a standalone MCP server. Tools handle task CRUD, status updates,
boss reports, and Slack message formatting.

Usage:
    # As TrendRadar extension (mount volume):
    volumes:
      - ./mcp-tools:/app/extensions/pm_tools

    # As standalone server:
    python pm_tools.py --port 3334
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import logging

import requests

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Database path - configurable via env
PM_DATABASE_PATH = Path(os.getenv("PM_DATABASE_PATH", "/app/output/pm/tasks.db"))


def get_db_connection() -> sqlite3.Connection:
    """Get SQLite database connection with row factory."""
    PM_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(PM_DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the PM database schema if not exists."""
    conn = get_db_connection()
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            due_date TEXT,
            priority TEXT DEFAULT 'medium',
            assignee TEXT,
            tags TEXT,
            metadata TEXT
        )
    """)

    # Progress updates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT REFERENCES tasks(id),
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
            task_id TEXT PRIMARY KEY REFERENCES tasks(id),
            verified_by TEXT NOT NULL,
            verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
            method TEXT NOT NULL,
            evidence TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {PM_DATABASE_PATH}")


# =============================================================================
# MCP Tool Definitions
# =============================================================================

def create_task(
    title: str,
    description: str,
    slack_channel: str,
    priority: str = "medium",
    due_date: Optional[str] = None,
    assignee: Optional[str] = None,
    tags: Optional[list[str]] = None,
    slack_thread_ts: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create a new PM task.

    Args:
        title: Task title (required)
        description: Detailed task description (required)
        slack_channel: Slack channel for updates (required)
        priority: Task priority - low, medium, high, critical (default: medium)
        due_date: Due date in YYYY-MM-DD format (optional)
        assignee: Assigned team member (optional)
        tags: List of tags for categorization (optional)
        slack_thread_ts: Slack thread timestamp for replies (optional)

    Returns:
        Created task object with generated ID
    """
    import uuid

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat() + "Z"

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tasks (id, title, description, slack_channel, priority,
                          due_date, assignee, tags, slack_thread_ts, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id, title, description, slack_channel, priority,
        due_date, assignee, json.dumps(tags or []), slack_thread_ts, now, now
    ))

    conn.commit()
    conn.close()

    logger.info(f"Created task: {task_id} - {title}")

    return {
        "id": task_id,
        "title": title,
        "description": description,
        "status": "defined",
        "slack_channel": slack_channel,
        "slack_thread_ts": slack_thread_ts,
        "priority": priority,
        "due_date": due_date,
        "assignee": assignee,
        "tags": tags or [],
        "created_at": now,
        "updated_at": now,
    }


def update_task_status(
    task_id: str,
    status: str,
    verification: Optional[dict] = None,
    progress_note: Optional[str] = None,
) -> dict[str, Any]:
    """
    Update task status and optionally add verification record.

    Args:
        task_id: Task identifier (required)
        status: New status - defined, in_progress, review, completed, blocked (required)
        verification: Verification record with verified_by, method, evidence (optional)
        progress_note: Progress note to add (optional)

    Returns:
        Updated task object
    """
    valid_statuses = ["defined", "in_progress", "review", "completed", "blocked"]
    if status not in valid_statuses:
        raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

    now = datetime.utcnow().isoformat() + "Z"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update task status
    cursor.execute("""
        UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?
    """, (status, now, task_id))

    if cursor.rowcount == 0:
        conn.close()
        raise ValueError(f"Task not found: {task_id}")

    # Add verification record if provided
    if verification:
        cursor.execute("""
            INSERT OR REPLACE INTO verifications (task_id, verified_by, verified_at, method, evidence)
            VALUES (?, ?, ?, ?, ?)
        """, (
            task_id,
            verification.get("verified_by", "agent"),
            verification.get("verified_at", now),
            verification.get("method", "automated"),
            json.dumps(verification.get("evidence", [])),
        ))

    # Add progress note if provided
    if progress_note:
        cursor.execute("""
            INSERT INTO progress_updates (task_id, timestamp, source, content)
            VALUES (?, ?, ?, ?)
        """, (task_id, now, "agent", progress_note))

    # Fetch updated task
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()

    conn.commit()
    conn.close()

    logger.info(f"Updated task {task_id} status to: {status}")

    return dict(task_row)


def get_task_progress(
    task_id: Optional[str] = None,
    status_filter: Optional[list[str]] = None,
    include_updates: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Get task progress and updates.

    Args:
        task_id: Specific task ID to fetch (optional - if not provided, fetches all)
        status_filter: Filter by status list, e.g., ["in_progress", "blocked"] (optional)
        include_updates: Include progress updates in response (default: true)
        limit: Maximum number of tasks to return (default: 50)

    Returns:
        Task(s) with progress updates and summary statistics
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if task_id:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        tasks = [dict(cursor.fetchone())] if cursor.fetchone() else []
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        tasks = [dict(row)] if row else []
    else:
        query = "SELECT * FROM tasks"
        params = []
        if status_filter:
            placeholders = ",".join("?" * len(status_filter))
            query += f" WHERE status IN ({placeholders})"
            params = status_filter
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        tasks = [dict(row) for row in cursor.fetchall()]

    # Include progress updates if requested
    if include_updates:
        for task in tasks:
            cursor.execute("""
                SELECT * FROM progress_updates
                WHERE task_id = ?
                ORDER BY timestamp DESC LIMIT 10
            """, (task["id"],))
            task["progress_updates"] = [dict(row) for row in cursor.fetchall()]

            # Parse tags JSON
            if task.get("tags"):
                task["tags"] = json.loads(task["tags"])

    # Generate summary statistics
    cursor.execute("""
        SELECT status, COUNT(*) as count FROM tasks GROUP BY status
    """)
    status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

    conn.close()

    return {
        "tasks": tasks,
        "total_count": len(tasks),
        "summary": {
            "by_status": status_counts,
            "total": sum(status_counts.values()),
        },
    }


def generate_boss_report(
    report_type: str = "daily",
    date_range: Optional[str] = None,
    include_metrics: bool = True,
) -> dict[str, Any]:
    """
    Generate a formatted boss report.

    Args:
        report_type: Report type - daily, weekly, custom (default: daily)
        date_range: Custom date range in "YYYY-MM-DD:YYYY-MM-DD" format (optional)
        include_metrics: Include detailed metrics (default: true)

    Returns:
        Formatted report with summary, highlights, risks, and metrics
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Determine date filter
    now = datetime.utcnow()
    if report_type == "daily":
        start_date = (now - timedelta(days=1)).isoformat()
    elif report_type == "weekly":
        start_date = (now - timedelta(days=7)).isoformat()
    elif date_range:
        start_date, end_date = date_range.split(":")
        start_date = start_date + "T00:00:00Z"
    else:
        start_date = (now - timedelta(days=1)).isoformat()

    # Get task statistics
    cursor.execute("SELECT status, COUNT(*) as count FROM tasks GROUP BY status")
    status_summary = {row["status"]: row["count"] for row in cursor.fetchall()}

    # Get recently completed tasks
    cursor.execute("""
        SELECT id, title, assignee, updated_at
        FROM tasks
        WHERE status = 'completed' AND updated_at >= ?
        ORDER BY updated_at DESC LIMIT 10
    """, (start_date,))
    completed_tasks = [dict(row) for row in cursor.fetchall()]

    # Get blocked tasks (risks)
    cursor.execute("""
        SELECT id, title, assignee, slack_channel
        FROM tasks
        WHERE status = 'blocked'
    """)
    blocked_tasks = [dict(row) for row in cursor.fetchall()]

    # Get tasks with approaching deadlines
    deadline_threshold = (now + timedelta(days=3)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT id, title, due_date, assignee, status
        FROM tasks
        WHERE due_date IS NOT NULL
          AND due_date <= ?
          AND status NOT IN ('completed', 'blocked')
        ORDER BY due_date ASC
    """, (deadline_threshold,))
    approaching_deadlines = [dict(row) for row in cursor.fetchall()]

    # Get recent progress updates for highlights
    cursor.execute("""
        SELECT t.title, p.content, p.sentiment_score, p.timestamp
        FROM progress_updates p
        JOIN tasks t ON p.task_id = t.id
        WHERE p.timestamp >= ?
        ORDER BY p.timestamp DESC LIMIT 5
    """, (start_date,))
    recent_updates = [dict(row) for row in cursor.fetchall()]

    conn.close()

    # Generate highlights
    highlights = []
    for task in completed_tasks[:3]:
        highlights.append(f"Completed: {task['title']}")
    for update in recent_updates[:2]:
        if update.get("sentiment_score", 0) > 0.5:
            highlights.append(f"Progress on: {update['title']}")

    # Generate risks
    risks = []
    for task in blocked_tasks:
        risks.append(f"BLOCKED: {task['title']} (in #{task['slack_channel']})")
    for task in approaching_deadlines:
        risks.append(f"Deadline approaching: {task['title']} (due {task['due_date']})")

    report = {
        "report_type": report_type,
        "generated_at": now.isoformat() + "Z",
        "date_range": {
            "start": start_date,
            "end": now.isoformat() + "Z",
        },
        "summary": {
            "completed": status_summary.get("completed", 0),
            "in_progress": status_summary.get("in_progress", 0),
            "blocked": status_summary.get("blocked", 0),
            "defined": status_summary.get("defined", 0),
            "review": status_summary.get("review", 0),
            "total": sum(status_summary.values()),
        },
        "highlights": highlights or ["No major highlights this period"],
        "risks": risks or ["No critical risks identified"],
        "details": {
            "completed_tasks": completed_tasks,
            "blocked_tasks": blocked_tasks,
            "approaching_deadlines": approaching_deadlines,
        } if include_metrics else {},
    }

    logger.info(f"Generated {report_type} boss report")
    return report


def push_to_slack(
    message: dict[str, Any],
    channel: Optional[str] = None,
    thread_ts: Optional[str] = None,
) -> dict[str, Any]:
    """
    Push a formatted message to Slack via webhook.

    Args:
        message: Slack Block Kit message payload (required)
        channel: Override channel (optional - uses webhook default if not specified)
        thread_ts: Thread timestamp for threaded replies (optional)

    Returns:
        Push result with success status
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL environment variable not set")

    payload = message.copy()
    if channel:
        payload["channel"] = channel
    if thread_ts:
        payload["thread_ts"] = thread_ts

    # Retry with exponential backoff
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info(f"Slack message sent successfully to {channel or 'default channel'}")
                return {
                    "success": True,
                    "channel": channel,
                    "thread_ts": thread_ts,
                }
            else:
                logger.warning(f"Slack push failed (attempt {attempt + 1}): {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"Slack push error (attempt {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            import time
            time.sleep(2 ** attempt)

    logger.error("Slack push failed after all retries")
    return {
        "success": False,
        "error": "Failed after maximum retries",
        "channel": channel,
    }


def get_task_by_id(task_id: str) -> dict[str, Any]:
    """
    Get a single task by ID with all details.

    Args:
        task_id: Task identifier (required)

    Returns:
        Task object with progress updates and verification status
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Task not found: {task_id}")

    task = dict(row)

    # Get progress updates
    cursor.execute("""
        SELECT * FROM progress_updates
        WHERE task_id = ?
        ORDER BY timestamp DESC
    """, (task_id,))
    task["progress_updates"] = [dict(r) for r in cursor.fetchall()]

    # Get verification if exists
    cursor.execute("SELECT * FROM verifications WHERE task_id = ?", (task_id,))
    verification_row = cursor.fetchone()
    task["verification"] = dict(verification_row) if verification_row else None

    # Parse JSON fields
    if task.get("tags"):
        task["tags"] = json.loads(task["tags"])
    if task.get("metadata"):
        task["metadata"] = json.loads(task["metadata"])

    conn.close()
    return task


# =============================================================================
# MCP Server Schema Definitions (for integration)
# =============================================================================

MCP_TOOLS_SCHEMA = {
    "create_task": {
        "name": "create_task",
        "description": "Create a new PM task",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Task description"},
                "slack_channel": {"type": "string", "description": "Slack channel for updates"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "default": "medium",
                },
                "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD)"},
                "assignee": {"type": "string", "description": "Assigned team member"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization",
                },
            },
            "required": ["title", "description", "slack_channel"],
        },
    },
    "update_task_status": {
        "name": "update_task_status",
        "description": "Update task status and add verification",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task identifier"},
                "status": {
                    "type": "string",
                    "enum": ["defined", "in_progress", "review", "completed", "blocked"],
                },
                "verification": {
                    "type": "object",
                    "properties": {
                        "verified_by": {"type": "string"},
                        "method": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "progress_note": {"type": "string"},
            },
            "required": ["task_id", "status"],
        },
    },
    "get_task_progress": {
        "name": "get_task_progress",
        "description": "Get task progress and updates",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Specific task ID"},
                "status_filter": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by status",
                },
                "include_updates": {"type": "boolean", "default": True},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    "generate_boss_report": {
        "name": "generate_boss_report",
        "description": "Generate formatted boss report",
        "input_schema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["daily", "weekly", "custom"],
                    "default": "daily",
                },
                "date_range": {
                    "type": "string",
                    "description": "Custom range: YYYY-MM-DD:YYYY-MM-DD",
                },
                "include_metrics": {"type": "boolean", "default": True},
            },
        },
    },
    "push_to_slack": {
        "name": "push_to_slack",
        "description": "Send formatted message to Slack",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "object",
                    "description": "Slack Block Kit message payload",
                },
                "channel": {"type": "string", "description": "Override channel"},
                "thread_ts": {"type": "string", "description": "Thread for reply"},
            },
            "required": ["message"],
        },
    },
    "get_task_by_id": {
        "name": "get_task_by_id",
        "description": "Get single task with all details",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task identifier"},
            },
            "required": ["task_id"],
        },
    },
}


# Tool dispatcher for MCP integration
def handle_tool_call(tool_name: str, arguments: dict) -> dict:
    """Dispatch MCP tool calls to the appropriate function."""
    tools = {
        "create_task": create_task,
        "update_task_status": update_task_status,
        "get_task_progress": get_task_progress,
        "generate_boss_report": generate_boss_report,
        "push_to_slack": push_to_slack,
        "get_task_by_id": get_task_by_id,
    }

    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")

    return tools[tool_name](**arguments)


# =============================================================================
# Standalone Server Mode
# =============================================================================

if __name__ == "__main__":
    import argparse
    from http.server import HTTPServer, BaseHTTPRequestHandler

    parser = argparse.ArgumentParser(description="PM MCP Tools Server")
    parser.add_argument("--port", type=int, default=3334, help="Server port")
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    args = parser.parse_args()

    # Initialize database
    init_database()

    if args.init_db:
        print(f"Database initialized at {PM_DATABASE_PATH}")
        exit(0)

    class MCPHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request = json.loads(body)

            try:
                result = handle_tool_call(request["tool"], request.get("arguments", {}))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "healthy"}).encode())
            elif self.path == "/tools":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(MCP_TOOLS_SCHEMA).encode())
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("0.0.0.0", args.port), MCPHandler)
    print(f"PM MCP Tools server running on port {args.port}")
    print(f"Health: http://localhost:{args.port}/health")
    print(f"Tools: http://localhost:{args.port}/tools")
    server.serve_forever()
