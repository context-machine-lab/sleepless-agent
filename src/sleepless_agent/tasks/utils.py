"""Shared helpers for task creation and metadata handling."""

from __future__ import annotations

import re
from typing import Optional, Tuple


def slugify_project(identifier: str) -> str:
    """Convert project name/id to Kebab-case slug used as project_id."""
    return re.sub(r"[^a-z0-9-]", "-", identifier.lower()).strip("-")


def parse_task_description(description: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Normalize task description, extracting optional project flag and notes.

    Returns:
        tuple of (clean_description, project_name, note)
    """
    note: Optional[str] = None
    working = description.strip()
    project_name: Optional[str] = None

    # Extract project flag in various formats:
    # -p value, -p=value, --project value, --project=value
    project_patterns = [
        r"--project[=\s]+(\S+)",  # --project=xxx or --project xxx
        r"-p[=\s]+(\S+)",          # -p=xxx or -p xxx
    ]

    for pattern in project_patterns:
        project_match = re.search(pattern, working)
        if project_match:
            project_name = project_match.group(1)
            working = working.replace(project_match.group(0), "").strip()
            break

    # Handle legacy flags
    if "--serious" in working:
        working = working.replace("--serious", "").strip()
        note = "ℹ️ `--serious` flag no longer needed; `/task` and CLI tasks are serious by default."

    if "--random" in working:
        working = working.replace("--random", "").strip()
        warning = (
            "ℹ️ Thoughts belong in `/think`. Treating this as a serious task."
        )
        note = f"{note}\n{warning}" if note else warning

    return working, project_name, note


def prepare_task_creation(
    description: str,
    project_override: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Normalize task input and derive project metadata.

    Args:
        description: Raw task description (may include flags).
        project_override: Project name provided via CLI flag or Slack command.

    Returns:
        tuple of (
            cleaned_description,
            final_project_name,
            project_id,
            note,
        )
    """
    cleaned, parsed_project, note = parse_task_description(description)
    final_project = project_override or parsed_project
    project_id = slugify_project(final_project) if final_project else None
    return cleaned, final_project, project_id, note
