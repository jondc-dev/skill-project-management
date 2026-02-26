"""JSON-based project state persistence."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from src.models.project import Project

logger = logging.getLogger(__name__)


def _project_file_path(persistence_dir: str, project_id: str) -> Path:
    return Path(persistence_dir) / f"project_{project_id}.json"


def save_project(project: Project, persistence_dir: str = "./checkpoints") -> Path:
    """
    Persist the full project state to a JSON file.

    Parameters
    ----------
    project : Project
    persistence_dir : str
        Directory where the JSON file will be saved.

    Returns
    -------
    Path
        The file path written to.
    """
    os.makedirs(persistence_dir, exist_ok=True)
    path = _project_file_path(persistence_dir, project.id)
    data = project.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.debug(f"Project saved to {path}")
    return path


def load_project(project_id: str, persistence_dir: str = "./checkpoints") -> Optional[Project]:
    """
    Load a project from its JSON file.

    Parameters
    ----------
    project_id : str
    persistence_dir : str

    Returns
    -------
    Project or None if not found.
    """
    path = _project_file_path(persistence_dir, project_id)
    if not path.exists():
        logger.warning(f"No saved project found at {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Project.model_validate(data)


def list_saved_projects(persistence_dir: str = "./checkpoints") -> list[str]:
    """Return list of project IDs found in persistence_dir."""
    p = Path(persistence_dir)
    if not p.exists():
        return []
    return [
        f.stem.removeprefix("project_")
        for f in p.glob("project_*.json")
    ]


def delete_project(project_id: str, persistence_dir: str = "./checkpoints") -> bool:
    """Delete a saved project file. Returns True if deleted."""
    path = _project_file_path(persistence_dir, project_id)
    if path.exists():
        path.unlink()
        return True
    return False
