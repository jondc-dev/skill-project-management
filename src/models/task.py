"""Task model for project management skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class TaskStatus(str, Enum):
    """Possible states of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class Task(BaseModel):
    """Represents a unit of work within a project.

    Attributes:
        id: Unique identifier (UUID string).
        name: Short name of the task.
        description: Detailed description.
        status: Current lifecycle status.
        urgency: How time-sensitive the task is (1–5).
        impact: How significant the outcome is (1–5).
        priority_score: Computed as urgency × impact.
        dependencies: IDs of tasks that must complete first.
        retry_count: Number of retry attempts so far.
        max_retries: Maximum allowed retries.
        estimated_duration: Estimated time to complete in minutes.
        actual_duration: Actual time taken in minutes.
        definition_of_done: Acceptance criteria list.
        assigned_agent: Identifier of the agent responsible.
        alternative_strategies: Fallback approaches if primary fails.
        notes: Freeform notes.
        created_at: Timezone-aware creation timestamp.
        updated_at: Timezone-aware last-update timestamp.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    urgency: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    priority_score: int = Field(default=0)
    dependencies: list[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    estimated_duration: float | None = None
    actual_duration: float | None = None
    definition_of_done: list[str] = Field(default_factory=list)
    assigned_agent: str | None = None
    alternative_strategies: list[str] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def compute_priority_score(self) -> "Task":
        """Auto-compute priority_score = urgency × impact."""
        self.priority_score = self.urgency * self.impact
        return self
