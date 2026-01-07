"""
MCP Tool functions for PM workflow automation.

These tools are designed to be exposed via an MCP server and called from
cc-wf-studio workflows and oh-my-opencode agents.

Tools match the spec.md requirements:
- create_task: Create a new PM task
- update_task_status: Update task status and add progress notes
- get_task_progress: Get task with all progress updates
- generate_boss_report: Generate formatted daily report
- push_to_slack: Send formatted Slack messages
- get_tasks_by_status: Query tasks by status filter
"""

import uuid
from datetime import datetime
from typing import Optional

from .models import (
    PMTask,
    TaskStatus,
    TaskPriority,
    UpdateSource,
    VerificationMethod,
)
from .database import (
    create_task_record,
    get_task_by_id,
    update_task_record,
    add_progress_update,
    set_verification,
    get_tasks_by_status_query,
    get_tasks_due_soon,
)
from .slack_client import get_slack_client


def create_task(
    title: str,
    slack_channel: str,
    description: str = "",
    assignee: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: str = "medium",
    tags: Optional[list[str]] = None,
    notify_slack: bool = True,
) -> dict:
    """
    Create a new PM task.

    Args:
        title: Task title (required)
        slack_channel: Slack channel for notifications (required)
        description: Task description
        assignee: Assigned person/team
        due_date: Due date (ISO format string)
        priority: low/medium/high/critical
        tags: List of tags for categorization
        notify_slack: Whether to send Slack notification

    Returns:
        dict with task_id, success status, and task details
    """
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    try:
        task_priority = TaskPriority(priority.lower())
    except ValueError:
        task_priority = TaskPriority.MEDIUM

    task = PMTask(
        id=task_id,
        title=title,
        description=description,
        slack_channel=slack_channel,
        assignee=assignee,
        due_date=due_date,
        priority=task_priority,
        tags=tags or [],
    )

    created_task = create_task_record(task)

    result = {
        "success": True,
        "task_id": created_task.id,
        "task": created_task.to_dict(),
    }

    # Send Slack notification if enabled
    if notify_slack:
        client = get_slack_client()
        message = client.format_task_alert(
            task_title=title,
            priority=priority,
            assignee=assignee,
            due_date=due_date,
            description=description,
        )
        slack_result = client.push_message(message, channel=slack_channel)
        result["slack_notification"] = slack_result

    return result


def update_task_status(
    task_id: str,
    status: Optional[str] = None,
    progress_note: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    agent_analysis: Optional[str] = None,
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    notify_slack: bool = False,
) -> dict:
    """
    Update task status and optionally add a progress note.

    Args:
        task_id: Task ID to update
        status: New status (defined/in_progress/review/completed/blocked)
        progress_note: Optional progress update content
        sentiment_score: Optional sentiment score (-1 to 1)
        agent_analysis: Optional AI agent analysis text
        assignee: Update assignee
        priority: Update priority
        notify_slack: Send Slack notification of update

    Returns:
        dict with success status and updated task
    """
    # Validate task exists
    existing_task = get_task_by_id(task_id)
    if not existing_task:
        return {
            "success": False,
            "error": f"Task {task_id} not found",
        }

    # Parse status if provided
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status.lower())
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid status: {status}",
            }

    # Parse priority if provided
    task_priority = None
    if priority:
        try:
            task_priority = TaskPriority(priority.lower())
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid priority: {priority}",
            }

    # Update task record
    updated_task = update_task_record(
        task_id=task_id,
        status=task_status,
        assignee=assignee,
        priority=task_priority,
    )

    # Add progress update if provided
    if progress_note:
        add_progress_update(
            task_id=task_id,
            content=progress_note,
            source=UpdateSource.AGENT,
            sentiment_score=sentiment_score,
            agent_analysis=agent_analysis,
        )
        # Re-fetch to include progress update
        updated_task = get_task_by_id(task_id)

    result = {
        "success": True,
        "task_id": task_id,
        "task": updated_task.to_dict() if updated_task else None,
    }

    # Send Slack notification if enabled
    if notify_slack and updated_task:
        client = get_slack_client()
        message = client.format_progress_update(
            task_title=updated_task.title,
            status=updated_task.status.value,
            sentiment_score=sentiment_score,
            content=progress_note or f"Status updated to {updated_task.status.value}",
        )
        slack_result = client.push_message(
            message,
            channel=updated_task.slack_channel,
            thread_ts=updated_task.slack_thread_ts,
        )
        result["slack_notification"] = slack_result

    return result


def get_task_progress(task_id: str) -> dict:
    """
    Get task details including all progress updates.

    Args:
        task_id: Task ID to retrieve

    Returns:
        dict with task details, progress history, and verification status
    """
    task = get_task_by_id(task_id)

    if not task:
        return {
            "success": False,
            "error": f"Task {task_id} not found",
        }

    return {
        "success": True,
        "task": task.to_dict(),
        "progress_count": len(task.progress_updates),
        "is_verified": task.verification is not None,
    }


def get_tasks_by_status(
    statuses: list[str],
    slack_channel: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    Query tasks by status with optional channel filter.

    Args:
        statuses: List of status values to filter by
        slack_channel: Optional channel filter
        limit: Maximum number of tasks to return

    Returns:
        dict with list of matching tasks
    """
    try:
        status_enums = [TaskStatus(s.lower()) for s in statuses]
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid status value: {e}",
        }

    tasks = get_tasks_by_status_query(
        statuses=status_enums,
        slack_channel=slack_channel,
        limit=limit,
    )

    return {
        "success": True,
        "count": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
    }


def generate_boss_report(
    slack_channel: Optional[str] = None,
    include_highlights: bool = True,
    include_risks: bool = True,
    days_for_due_soon: int = 3,
) -> dict:
    """
    Generate a formatted daily boss report.

    Args:
        slack_channel: Filter by channel (None for all channels)
        include_highlights: Include highlights section
        include_risks: Include risks section
        days_for_due_soon: Days ahead to check for due tasks

    Returns:
        dict with report data and formatted message
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Get task counts by status
    completed_tasks = get_tasks_by_status_query(
        statuses=[TaskStatus.COMPLETED],
        slack_channel=slack_channel,
    )
    in_progress_tasks = get_tasks_by_status_query(
        statuses=[TaskStatus.IN_PROGRESS, TaskStatus.REVIEW],
        slack_channel=slack_channel,
    )
    blocked_tasks = get_tasks_by_status_query(
        statuses=[TaskStatus.BLOCKED],
        slack_channel=slack_channel,
    )

    highlights = []
    risks = []

    if include_highlights:
        # Recent completions as highlights
        for task in completed_tasks[:3]:
            highlights.append(f"Completed: {task.title}")

    if include_risks:
        # Blocked tasks as risks
        for task in blocked_tasks[:3]:
            risks.append(f"BLOCKED: {task.title}")

        # Tasks due soon
        due_soon = get_tasks_due_soon(
            days=days_for_due_soon,
            slack_channel=slack_channel,
        )
        for task in due_soon[:2]:
            risks.append(f"Due soon: {task.title} (due: {task.due_date})")

    report_data = {
        "date": today,
        "completed_count": len(completed_tasks),
        "in_progress_count": len(in_progress_tasks),
        "blocked_count": len(blocked_tasks),
        "highlights": highlights,
        "risks": risks,
    }

    # Format Slack message
    client = get_slack_client()
    formatted_message = client.format_boss_report(
        date=today,
        completed_count=len(completed_tasks),
        in_progress_count=len(in_progress_tasks),
        blocked_count=len(blocked_tasks),
        highlights=highlights,
        risks=risks,
    )

    return {
        "success": True,
        "report": report_data,
        "slack_message": formatted_message,
    }


def push_to_slack(
    message: Optional[dict] = None,
    text: Optional[str] = None,
    channel: Optional[str] = None,
    thread_ts: Optional[str] = None,
    message_type: Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Send a formatted message to Slack.

    Args:
        message: Pre-formatted Slack message (blocks format)
        text: Simple text message (if message not provided)
        channel: Target channel (uses default if not specified)
        thread_ts: Thread timestamp for replies
        message_type: Type of message for auto-formatting:
            - 'task_alert': Use format_task_alert
            - 'progress_update': Use format_progress_update
            - 'boss_report': Use format_boss_report
            - 'verification': Use format_verification_result
        **kwargs: Additional parameters for message_type formatting

    Returns:
        dict with success status and delivery details
    """
    client = get_slack_client()

    # Auto-format based on message_type
    if message_type and not message:
        if message_type == "task_alert":
            message = client.format_task_alert(
                task_title=kwargs.get("task_title", "Untitled Task"),
                priority=kwargs.get("priority", "medium"),
                assignee=kwargs.get("assignee"),
                due_date=kwargs.get("due_date"),
                description=kwargs.get("description", ""),
            )
        elif message_type == "progress_update":
            message = client.format_progress_update(
                task_title=kwargs.get("task_title", "Untitled Task"),
                status=kwargs.get("status", "in_progress"),
                sentiment_score=kwargs.get("sentiment_score"),
                content=kwargs.get("content", ""),
                dashboard_link=kwargs.get("dashboard_link"),
            )
        elif message_type == "boss_report":
            message = client.format_boss_report(
                date=kwargs.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
                completed_count=kwargs.get("completed_count", 0),
                in_progress_count=kwargs.get("in_progress_count", 0),
                blocked_count=kwargs.get("blocked_count", 0),
                highlights=kwargs.get("highlights", []),
                risks=kwargs.get("risks", []),
            )
        elif message_type == "verification":
            message = client.format_verification_result(
                task_title=kwargs.get("task_title", "Untitled Task"),
                verification_status=kwargs.get("verification_status", "MANUAL_REVIEW"),
                confidence_score=kwargs.get("confidence_score", 0.0),
                summary=kwargs.get("summary", ""),
                timestamp=kwargs.get("timestamp", datetime.utcnow().isoformat()),
            )

    # Fall back to simple text message
    if not message and text:
        message = {"text": text}

    if not message:
        return {
            "success": False,
            "error": "No message content provided",
        }

    result = client.push_message(
        message=message,
        channel=channel,
        thread_ts=thread_ts,
    )

    return result


def verify_task_completion(
    task_id: str,
    verified_by: str = "agent",
    method: str = "automated",
    evidence: Optional[list[str]] = None,
    notify_slack: bool = True,
) -> dict:
    """
    Mark a task as verified/completed.

    Args:
        task_id: Task ID to verify
        verified_by: 'user' or 'agent'
        method: 'manual', 'automated', or 'hybrid'
        evidence: List of evidence strings supporting verification
        notify_slack: Send Slack notification

    Returns:
        dict with verification result
    """
    # Validate task exists
    existing_task = get_task_by_id(task_id)
    if not existing_task:
        return {
            "success": False,
            "error": f"Task {task_id} not found",
        }

    try:
        verification_method = VerificationMethod(method.lower())
    except ValueError:
        verification_method = VerificationMethod.HYBRID

    verification = set_verification(
        task_id=task_id,
        verified_by=verified_by,
        method=verification_method,
        evidence=evidence or [],
    )

    if not verification:
        return {
            "success": False,
            "error": "Failed to create verification record",
        }

    # Re-fetch task to get updated state
    updated_task = get_task_by_id(task_id)

    result = {
        "success": True,
        "task_id": task_id,
        "verification": verification.to_dict(),
        "task": updated_task.to_dict() if updated_task else None,
    }

    # Send Slack notification
    if notify_slack and updated_task:
        client = get_slack_client()
        message = client.format_verification_result(
            task_title=updated_task.title,
            verification_status="VERIFIED",
            confidence_score=1.0,
            summary=f"Task verified by {verified_by} using {method} method.",
            timestamp=verification.verified_at,
        )
        slack_result = client.push_message(
            message,
            channel=updated_task.slack_channel,
            thread_ts=updated_task.slack_thread_ts,
        )
        result["slack_notification"] = slack_result

    return result
