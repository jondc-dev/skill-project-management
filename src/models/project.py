from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ProjectPhase(str, Enum):
    INITIATION = "initiation"
    PLANNING = "planning"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    CLOSURE = "closure"


class RiskStatus(str, Enum):
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    OCCURRED = "occurred"


class Risk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    probability: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    mitigation_strategy: str = ""
    status: RiskStatus = RiskStatus.IDENTIFIED

    @property
    def risk_score(self) -> int:
        return self.probability * self.impact


class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str
    description: str
    details: dict = Field(default_factory=dict)


class Checkpoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase: str
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    file_path: Optional[str] = None


from src.models.task import Task  # noqa: E402


class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    phase: ProjectPhase = ProjectPhase.INITIATION
    tasks: List[Task] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    audit_log: List[AuditEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: Optional[datetime] = None
    checkpoints: List[Checkpoint] = Field(default_factory=list)
    goal: str = ""
    success_criteria: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)

    @property
    def overall_progress_percent(self) -> float:
        if not self.tasks:
            return 0.0
        done = sum(1 for t in self.tasks if t.status.value == "done")
        return round(done / len(self.tasks) * 100, 1)

    def advance_phase(self) -> None:
        phases = list(ProjectPhase)
        current_idx = phases.index(self.phase)
        if current_idx < len(phases) - 1:
            self.phase = phases[current_idx + 1]

    def log_action(self, actor: str, description: str, details: dict = None) -> None:
        entry = AuditEntry(actor=actor, description=description, details=details or {})
        self.audit_log.append(entry)
