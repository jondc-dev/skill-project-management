"""Project model for project management skill."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from .task import Task
from .job_types import Schedule, RunHistory


class ProjectStatus(str, Enum):
    """High-level lifecycle status of a project."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    OVERDUE = "overdue"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectPhase(str, Enum):
    """PMBOK-inspired phase of the project lifecycle."""

    INITIATION = "initiation"
    PLANNING = "planning"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    CLOSURE = "closure"


class Risk(BaseModel):
    """A potential threat or opportunity that may affect the project.

    Attributes:
        id: Unique identifier (UUID string).
        description: What could go wrong.
        probability: Likelihood of occurrence (1–5).
        impact: Effect magnitude if it occurs (1–5).
        risk_score: Computed as probability × impact.
        mitigation: Planned response strategy.
        status: Current state: open / mitigated / closed.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    probability: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    risk_score: int = Field(default=0)
    mitigation: str = ""
    status: str = "open"

    @model_validator(mode="after")
    def compute_risk_score(self) -> "Risk":
        """Auto-compute risk_score = probability × impact."""
        self.risk_score = self.probability * self.impact
        return self


class AuditEntry(BaseModel):
    """Immutable log entry recording a change event.

    Attributes:
        timestamp: When the event occurred (timezone-aware).
        action: Short label for the event type.
        details: Longer description of what changed.
        actor: Who/what triggered the event.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    details: str = ""
    actor: str = "system"


class Project(BaseModel):
    """Top-level container for all project data.

    Attributes:
        id: Unique identifier (UUID string).
        name: Human-readable project name.
        description: Project purpose and scope.
        status: Current lifecycle status.
        phase: Current PMBOK phase.
        tasks: Ordered list of tasks belonging to this project.
        risks: Identified risks for this project.
        audit_log: Ordered list of audit events.
        created_at: Timezone-aware creation timestamp.
        deadline: Optional hard deadline (timezone-aware).
        overall_progress_percent: 0–100 float, auto-updated.
        job_type: one_time / recurring / continuous.
        schedule: Recurrence schedule (recurring jobs only).
        run_history: Past run records.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    phase: ProjectPhase = ProjectPhase.INITIATION
    tasks: list[Task] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    audit_log: list[AuditEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: datetime | None = None
    overall_progress_percent: float = 0.0
    job_type: str = "one_time"
    schedule: Schedule | None = None
    run_history: list[RunHistory] = Field(default_factory=list)

    def update_progress(self) -> None:
        """Recalculate overall_progress_percent from task statuses."""
        if not self.tasks:
            self.overall_progress_percent = 0.0
            return
        done_count = sum(1 for t in self.tasks if t.status.value == "done")
        self.overall_progress_percent = round(done_count / len(self.tasks) * 100, 2)

    def add_audit(self, action: str, details: str = "", actor: str = "system") -> None:
        """Append an audit log entry."""
        self.audit_log.append(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                action=action,
                details=details,
                actor=actor,
            )
        )
