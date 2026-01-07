"""
Slack webhook client for PM notifications.
Implements retry logic from spec.md Section 9.2.
"""

import os
import time
import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)


class SlackClient:
    """Slack webhook client with retry and formatting support."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        default_channel: Optional[str] = None,
        max_retries: int = 3,
    ):
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self.default_channel = default_channel or os.environ.get(
            "SLACK_CHANNEL", "#pm-updates"
        )
        self.max_retries = max_retries

        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not configured")

    def push_message(
        self,
        message: dict,
        channel: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ) -> dict:
        """
        Push a message to Slack with retry logic.

        Args:
            message: Slack message payload (text or blocks)
            channel: Target channel (uses default if not specified)
            thread_ts: Thread timestamp for replies

        Returns:
            dict with success status and details
        """
        if not self.webhook_url:
            return {
                "success": False,
                "error": "SLACK_WEBHOOK_URL not configured",
            }

        payload = message.copy()

        # Add channel if specified
        if channel:
            payload["channel"] = channel
        elif self.default_channel and "channel" not in payload:
            payload["channel"] = self.default_channel

        # Add thread_ts for replies
        if thread_ts:
            payload["thread_ts"] = thread_ts

        # Retry loop with exponential backoff (spec.md Section 9.2)
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )

                if response.status_code == 200:
                    return {"success": True, "attempt": attempt + 1}

                last_error = f"HTTP {response.status_code}: {response.text}"
                logger.warning(
                    f"Slack push attempt {attempt + 1} failed: {last_error}"
                )

            except requests.RequestException as e:
                last_error = str(e)
                logger.warning(
                    f"Slack push attempt {attempt + 1} error: {last_error}"
                )

            # Exponential backoff
            if attempt < self.max_retries - 1:
                time.sleep(2**attempt)

        return {
            "success": False,
            "error": last_error,
            "attempts": self.max_retries,
        }

    def format_task_alert(
        self,
        task_title: str,
        priority: str,
        assignee: Optional[str],
        due_date: Optional[str],
        description: str,
    ) -> dict:
        """Format a task definition alert (spec.md Section 11.1)."""
        priority_emoji = {
            "critical": ":rotating_light:",
            "high": ":red_circle:",
            "medium": ":large_yellow_circle:",
            "low": ":white_circle:",
        }.get(priority, ":white_circle:")

        fields = [
            f"*Priority:* {priority_emoji} {priority.capitalize()}",
        ]
        if assignee:
            fields.append(f"*Assigned:* {assignee}")
        if due_date:
            fields.append(f"*Due:* {due_date}")

        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":clipboard: New Task Defined",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{task_title}*",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": field} for field in fields
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"> {description}" if description else "_No description_",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "_React with :white_check_mark: to acknowledge_",
                        }
                    ],
                },
            ]
        }

    def format_progress_update(
        self,
        task_title: str,
        status: str,
        sentiment_score: Optional[float],
        content: str,
        dashboard_link: Optional[str] = None,
    ) -> dict:
        """Format a progress update message (spec.md Section 11.1)."""
        sentiment_emoji = ":neutral_face:"
        if sentiment_score is not None:
            if sentiment_score > 0.5:
                sentiment_emoji = ":grinning:"
            elif sentiment_score < -0.5:
                sentiment_emoji = ":worried:"
            elif sentiment_score > 0:
                sentiment_emoji = ":slightly_smiling_face:"
            elif sentiment_score < 0:
                sentiment_emoji = ":confused:"

        status_emoji = {
            "defined": ":clipboard:",
            "in_progress": ":construction:",
            "review": ":mag:",
            "completed": ":white_check_mark:",
            "blocked": ":no_entry:",
        }.get(status, ":clipboard:")

        text = f":arrows_counterclockwise: *Task Update: {task_title}*\n"
        text += f"*Status:* {status_emoji} {status.replace('_', ' ').title()}\n"

        if sentiment_score is not None:
            text += f"*Sentiment:* {sentiment_emoji} ({sentiment_score:.2f})\n"

        text += f"\n{content}"

        if dashboard_link:
            text += f"\n\n:bar_chart: <{dashboard_link}|View Dashboard>"

        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                },
            ]
        }

    def format_boss_report(
        self,
        date: str,
        completed_count: int,
        in_progress_count: int,
        blocked_count: int,
        highlights: list[str],
        risks: list[str],
    ) -> dict:
        """Format the daily boss report (spec.md Section 11.1)."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":bar_chart: Daily PM Report - {date}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Completed:* :white_check_mark: {completed_count}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*In Progress:* :construction: {in_progress_count}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Blocked:* :no_entry: {blocked_count}",
                    },
                ],
            },
        ]

        if highlights:
            highlight_text = "*Highlights:*\n" + "\n".join(
                f":sparkles: {h}" for h in highlights
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": highlight_text},
                }
            )

        if risks:
            risk_text = "*Risks:*\n" + "\n".join(f":warning: {r}" for r in risks)
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": risk_text},
                }
            )

        return {"blocks": blocks}

    def format_verification_result(
        self,
        task_title: str,
        verification_status: str,
        confidence_score: float,
        summary: str,
        timestamp: str,
    ) -> dict:
        """Format a verification result notification."""
        emoji = {
            "VERIFIED": ":white_check_mark:",
            "NEEDS_WORK": ":warning:",
            "MANUAL_REVIEW": ":question:",
        }.get(verification_status, ":question:")

        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"{emoji} *Task Verification: {task_title}*\n\n"
                            f"*Status:* {verification_status}\n"
                            f"*Confidence:* {confidence_score:.0%}\n\n"
                            f"{summary}"
                        ),
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Verified by AI Agent | {timestamp}",
                        }
                    ],
                },
            ]
        }


# Singleton instance
_client: Optional[SlackClient] = None


def get_slack_client() -> SlackClient:
    """Get or create singleton Slack client."""
    global _client
    if _client is None:
        _client = SlackClient()
    return _client
