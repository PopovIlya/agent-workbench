"""Role facts read from the workbench role files (roles-22/agents, kit/agents) and the user-level ~/.claude/agents (never a hand-kept list)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

PATH_TOKEN = re.compile(r"`([^`\s]*[/.][^`\s]*)`")


@dataclass
class Role:
    name: str
    tools: list[str] = field(default_factory=list)
    model_tier: str | None = None
    output_paths: list[str] = field(default_factory=list)  # path-like tokens in the `## Output` section
    has_output_section: bool = False


def parse_role(text: str, fallback_name: str) -> Role:
    role = Role(name=fallback_name)
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if k == "name":
                role.name = v
            elif k == "model":
                role.model_tier = v
            elif k == "tools":
                role.tools = [t.strip() for t in re.split(r",\s*(?![^()]*\))", v) if t.strip()]
    sec = re.search(r"^## Output\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if sec:
        role.has_output_section = True
        role.output_paths = [p for p in PATH_TOKEN.findall(sec.group(1)) if "/" in p]
    return role


def role_files(repo: Path, user_dir: Path | None = None) -> dict[str, Path]:
    """name -> role file. The workbench's role folders first (agent_scoring.layout), then the user-level directory (symlinks
    resolved) for names the workbench does not define. A broken symlink or an unreadable entry is skipped."""
    from agent_scoring import layout
    found: dict[str, Path] = {}
    user = config.user_agents_dir() if user_dir is None else user_dir
    for d in (*layout.role_dirs(repo), user):
        try:
            files = sorted(d.glob("*.md"))
        except OSError:
            continue
        for f in files:
            try:
                real = f.resolve(strict=True)
            except OSError:
                continue
            if real.is_file():
                found.setdefault(f.stem, real)
    return found


def load_roles(repo: Path, user_dir: Path | None = None) -> dict[str, Role]:
    out: dict[str, Role] = {}
    for stem, f in role_files(repo, user_dir).items():
        r = parse_role(f.read_text(errors="replace"), stem)
        out[r.name] = r
    return out


def tier_of(model_id: str | None) -> str | None:
    mid = (model_id or "").lower()
    for t in ("opus", "sonnet", "haiku"):
        if t in mid:
            return t
    return None
