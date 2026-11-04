"""Where the workbench keeps its role files and criteria files.

Main goal: one place that knows the layout, so the console and the scorer never hard-code it.
Does: role files under roles-22/agents and kit/agents, criteria under roles-22/criteria and kit/criteria, all relative to
the workbench checkout. AGENT_CONSOLE_ROLE_DIRS / AGENT_CONSOLE_CRITERIA_DIRS (os.pathsep-separated) replace the defaults.
Does not: read the user-level ~/.claude/agents (callers fall back to it themselves).
Example: role_path(repo, "reviewer") -> <repo>/roles-22/agents/reviewer.md
"""

from __future__ import annotations

import os
from pathlib import Path

ROLE_DIRS = ("roles-22/agents", "kit/agents")
CRITERIA_DIRS = ("roles-22/criteria", "kit/criteria")


def _dirs(repo: Path, env: str, default: tuple[str, ...]) -> list[Path]:
    raw = os.environ.get(env)
    if raw:
        return [Path(p).expanduser() for p in raw.split(os.pathsep) if p]
    return [repo / d for d in default]


def role_dirs(repo: Path) -> list[Path]:
    return _dirs(repo, "AGENT_CONSOLE_ROLE_DIRS", ROLE_DIRS)


def criteria_dirs(repo: Path) -> list[Path]:
    return _dirs(repo, "AGENT_CONSOLE_CRITERIA_DIRS", CRITERIA_DIRS)


def criteria_files(repo: Path) -> list[Path]:
    """One criteria file per role name; on a clash the first directory wins."""
    seen: dict[str, Path] = {}
    for d in criteria_dirs(repo):
        for c in sorted(d.glob("*.md")) if d.is_dir() else []:
            seen.setdefault(c.stem, c)
    return [seen[k] for k in sorted(seen)]


def criteria_path(repo: Path, role: str) -> Path | None:
    return next((c for c in criteria_files(repo) if c.stem == role), None)


def role_path(repo: Path, role: str) -> Path | None:
    for d in role_dirs(repo):
        f = d / f"{role}.md"
        if f.is_file():
            return f
    return None


def role_rel(repo: Path, role: str) -> str | None:
    """Repo-relative path of the role file (for `git show <ref>:<rel>`), or None when it is not inside the repo."""
    f = role_path(repo, role)
    if f is None:
        return None
    try:
        return f.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return None
