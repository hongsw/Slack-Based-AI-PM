"""
Data models for PM tools - matches spec.md Section 8.1 schema.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import json


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


class UpdateSource(str, Enum):
    SLACK = "slack"
    AGENT = "agent"
    MANUAL = "manual"


class VerificationMethod(str, Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
    HYBRID = "hybrid"


@dataclass
class ProgressUpdate:
    timestamp: str
    source: UpdateSource
    content: str
    sentiment_score: Optional[float] = None
    agent_analysis: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source.value,
            "content": self.content,
            "sentiment_score": self.sentiment_score,
            "agent_analysis": self.agent_analysis,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProgressUpdate":
        return cls(
            timestamp=data["timestamp"],
            source=UpdateSource(data["source"]),
            content=data["content"],
            sentiment_score=data.get("sentiment_score"),
            agent_analysis=data.get("agent_analysis"),
        )


@dataclass
class VerificationRecord:
    verified_by: str  # 'user' or 'agent'
    verified_at: str
    method: VerificationMethod
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "method": self.method.value,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VerificationRecord":
        return cls(
            verified_by=data["verified_by"],
            verified_at=data["verified_at"],
            method=VerificationMethod(data["method"]),
            evidence=data.get("evidence", []),
        )


@dataclass
class PMTask:
    id: str
    title: str
    slack_channel: str
    description: str = ""
    status: TaskStatus = TaskStatus.DEFINED
    assignee: Optional[str] = None
    slack_thread_ts: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    due_date: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: list[str] = field(default_factory=list)
    progress_updates: list[ProgressUpdate] = field(default_factory=list)
    verification: Optional[VerificationRecord] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assignee": self.assignee,
            "slack_channel": self.slack_channel,
            "slack_thread_ts": self.slack_thread_ts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "due_date": self.due_date,
            "priority": self.priority.value,
            "tags": self.tags,
            "progress_updates": [u.to_dict() for u in self.progress_updates],
            "verification": self.verification.to_dict() if self.verification else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PMTask":
        progress_updates = [
            ProgressUpdate.from_dict(u) for u in data.get("progress_updates", [])
        ]
        verification = None
        if data.get("verification"):
            verification = VerificationRecord.from_dict(data["verification"])

        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "defined")),
            assignee=data.get("assignee"),
            slack_channel=data["slack_channel"],
            slack_thread_ts=data.get("slack_thread_ts"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            due_date=data.get("due_date"),
            priority=TaskPriority(data.get("priority", "medium")),
            tags=data.get("tags", []),
            progress_updates=progress_updates,
            verification=verification,
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PMTask":
        return cls.from_dict(json.loads(json_str))
