from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, computed_field
from datetime import datetime, timezone
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class RetryStrategy(BaseModel):
    name: str
    description: str
    action: str  # string instruction (callable not serializable)


class EscalationMessage(BaseModel):
    task_id: str
    task_name: str
    description: str
    retries_attempted: int
    strategies_tried: List[str]
    recommended_action: str
    escalated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BlockerDecomposition(BaseModel):
    original_task_id: str
    reason: str
    suggested_subtasks: List[str]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    urgency: int = Field(default=3, ge=1, le=5)
    impact: int = Field(default=3, ge=1, le=5)
    dependencies: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    estimated_duration: Optional[str] = None  # e.g., "2h", "30m"
    actual_duration: Optional[str] = None
    definition_of_done: List[str] = Field(default_factory=list)
    assigned_agent: Optional[str] = None
    alternative_strategies: List[RetryStrategy] = Field(default_factory=list)
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def priority_score(self) -> int:
        return self.urgency * self.impact




def sort_tasks_by_priority(tasks: List[Task]) -> List[Task]:
    """Sort tasks by priority_score descending (highest first)."""
    return sorted(tasks, key=lambda t: t.priority_score, reverse=True)


def filter_tasks_by_status(tasks: List[Task], status: TaskStatus) -> List[Task]:
    """Filter tasks by status."""
    return [t for t in tasks if t.status == status]
