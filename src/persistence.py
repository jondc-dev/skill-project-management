"""JSON-based persistence for project state."""

from __future__ import annotations

import json
from pathlib import Path

from .models.project import Project


def save_checkpoint(project: Project, path: str) -> None:
    """Serialise the project to a JSON file.

    Creates intermediate directories if they do not exist.

    Args:
        project: The project to persist.
        path: Filesystem path for the JSON file.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(project.model_dump_json(indent=2), encoding="utf-8")


def load_checkpoint(path: str) -> Project:
    """Deserialise a project from a JSON file.

    Args:
        path: Filesystem path of the JSON file.

    Returns:
        The reconstructed Project instance.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    data = json.loads(src.read_text(encoding="utf-8"))
    return Project.model_validate(data)
