"""
PM Tools - MCP extension module for Slack-Based AI PM system.

This module extends TrendRadar's MCP server with PM-specific tools:
- create_task: Create a new PM task
- update_task_status: Update task status and metadata
- get_task_progress: Get task progress and updates
- generate_boss_report: Generate formatted status reports
- push_to_slack: Send formatted Slack messages
"""

from .tools import (
    create_task,
    update_task_status,
    get_task_progress,
    generate_boss_report,
    push_to_slack,
    get_tasks_by_status,
    verify_task_completion,
)

__version__ = "0.1.0"
__all__ = [
    "create_task",
    "update_task_status",
    "get_task_progress",
    "generate_boss_report",
    "push_to_slack",
    "get_tasks_by_status",
    "verify_task_completion",
]
