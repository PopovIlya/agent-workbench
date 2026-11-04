"""The scored project: its git checkout and the settings its profile declares.

Main goal: the scorer judges a run against the project the run worked in, never against the workbench.
Does: finds the git top level of a run's cwd, reads `docs/agents/PROJECT.md` there (section "Optional gates", lines
`- <gate>: <value>` (the gate name may be in backticks), and "Trunk branch" under "Repo"), and gives the defaults of the kit layout for anything not
declared. Collects the rule ids of the requirement map in three formats: `### ID` headings, `| ID |` table rows and
`- **ID**` bullets.
Does not: run any project command, or write anything.
Example: for_cwd("/work/app/src").requirement_globs -> ["docs/requirements/*.md"] unless the profile names others.
"""

from __future__ import annotations

import os
import re
import subprocess  # nosec B404 - read-only git calls, fixed argv, no shell
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROFILE = "docs/agents/PROJECT.md"
DEFAULT_REQUIREMENTS = ("docs/requirements/*.md",)
DEFAULT_CHANGE_FILES = ("docs/agents/work/*/*.md", "docs/requirements/changes/*.md")
DEFAULT_TESTS = ("**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*")
OFF = {"", "none", "off", "no", "n/a", "-"}
GATE_LINE = re.compile(r"^\s*[-*]\s+`?([a-z_]+)`?\s*:\s*(.*?)\s*$")
TRUNK_LINE = re.compile(r"(?i)^\s*[-*]\s+trunk branch\s*:\s*`?([\w./-]+)`?")
ID = r"[A-Z][A-Z0-9]{1,7}(?:-[A-Z0-9]{1,10}){1,3}"
ID_LINES = (re.compile(rf"^#{{2,4}}\s+\**({ID})\**\b"), re.compile(rf"^\|\s*\**({ID})\**\s*\|"), re.compile(rf"^\s*[-*]\s+\*\*({ID})\*\*"))


@dataclass(frozen=True)
class Project:
    top: Path | None
    trunk: str = "HEAD"
    gates: dict[str, str] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)      # every `- `key`: value` line of the profile, any section

    def gate(self, name: str) -> str | None:
        v = self.gates.get(name, "")
        return None if v.strip().strip("`").lower() in OFF else v

    def _globs(self, name: str, default: tuple[str, ...]) -> list[str]:
        v = self.gate(name)
        if v is None:
            return list(default)
        return [g.strip().strip("`") for g in re.split(r"[,;]", v.split("·")[0]) if g.strip().strip("`")]

    @property
    def requirement_globs(self) -> list[str]:
        return self._globs("requirements_master", DEFAULT_REQUIREMENTS)

    @property
    def case_globs(self) -> list[str]:
        return self._globs("test_case_files", ()) if self.gate("test_case_files") else []

    @property
    def change_globs(self) -> list[str]:
        return self._globs("change_files", DEFAULT_CHANGE_FILES)

    @property
    def test_globs(self) -> list[str]:
        return list(DEFAULT_TESTS)

    def _path_glob(self, key: str, default: str) -> str:
        """A profile path with `<KEY>` / `<id>` placeholders as a glob: `docs/agents/work/<KEY>/` -> `docs/agents/work/*/**`."""
        v = (self.fields.get(key) or "").strip().strip("`")
        if not v or v.lower() in OFF or v.startswith("<"):
            v = default
        v = re.sub(r"<[^>]+>", "*", v)
        return v.rstrip("/") + "/**" if v.endswith("/") else v

    def placeholder(self, name: str) -> list[str]:
        """Globs for a `{name}` in a criteria file. An undeclared gate gives [] (the output cannot be checked here)."""
        if name == "requirements":
            return self.requirement_globs
        if name == "work":
            return [self._path_glob("work_dir", "docs/agents/work/<KEY>/")]
        if name == "change":
            return [self._path_glob("change_file", "docs/agents/work/<KEY>/change.md"), *self._globs("change_files", ())]
        if name == "release":
            return [self._path_glob("release_dir", "docs/agents/work/releases/<id>/")]
        if name == "cases":
            return self.case_globs
        if name in ("suites", "impact_map"):
            v = self.gate(name)
            return [re.sub(r"<[^>]+>", "*", v.split("·")[0].strip().strip("`"))] if v else []
        if name == "tests":
            return self.test_globs
        if name == "code":
            return ["**"]
        return []


def _git(top: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, timeout=20)  # nosec B603 B607
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


@lru_cache(maxsize=512)
def toplevel(cwd: str | None) -> Path | None:
    """The git checkout containing `cwd` (a worktree's own folder too), or None."""
    if not cwd:
        return None
    p = Path(cwd)
    for d in [p, *p.parents]:
        if (d / ".git").exists():
            return d
    return None


FIELD_LINE = re.compile(r"^\s*[-*]\s+`([a-z_]+)`\s*:\s*(.*?)\s*$")


def parse_fields(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for ln in text.splitlines() if (m := FIELD_LINE.match(ln))}


def parse_profile(text: str) -> tuple[dict[str, str], str | None]:
    gates: dict[str, str] = {}
    trunk = None
    section = ""
    for ln in text.splitlines():
        if ln.startswith("## "):
            section = ln[3:].strip().lower()
            continue
        if trunk is None and (m := TRUNK_LINE.match(ln)):
            trunk = m.group(1)
        if section.startswith("optional gates") and (m := GATE_LINE.match(ln)):
            gates[m.group(1)] = m.group(2)
    return gates, trunk


@lru_cache(maxsize=256)
def for_top(top: Path | None) -> Project:
    if top is None:
        return Project(None)
    gates: dict[str, str] = {}
    fields: dict[str, str] = {}
    trunk = None
    f = top / PROFILE
    if f.is_file():
        text = f.read_text(errors="replace")
        gates, trunk = parse_profile(text)
        fields = parse_fields(text)
    ref = "HEAD"
    if trunk and trunk.lower() not in OFF and not trunk.startswith("<"):
        for cand in (f"origin/{trunk}", trunk):
            if _git(top, "rev-parse", "--verify", "--quiet", cand):
                ref = cand
                break
    return Project(top, ref, gates, fields)


def default_project() -> Path | None:
    """AGENT_CONSOLE_DEFAULT_PROJECT: the checkout to judge a run against when its cwd is gone or is not inside a git checkout
    (a deleted /tmp copy, a removed worktree). Default: none (those runs get no project checks)."""
    v = os.environ.get("AGENT_CONSOLE_DEFAULT_PROJECT")
    return Path(v).expanduser() if v else None


def for_cwd(cwd: str | None) -> Project:
    return for_top(toplevel(cwd) or default_project())


@lru_cache(maxsize=256)
def _glob_rx(g: str) -> re.Pattern[str]:
    """Path glob: `*` and `?` stay inside one folder, `**/` is any number of folders."""
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif g.startswith("**", i):
            out, i = out + ".*", i + 2
        elif g[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif g[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(g[i]), i + 1
    return re.compile(out + r"\Z")


PLACEHOLDER = re.compile(r"^\{([a-z_]+)\}(.*)$")


def expand(globs: list[str], project: Project | None) -> list[str]:
    """Criteria globs with `{requirements}`, `{work}`, `{change}`, `{release}`, `{cases}`, `{suites}`, `{impact_map}`, `{tests}`,
    `{code}` replaced from the project's profile (a suffix is kept: `{work}/reviewer.md`). Plain globs pass through."""
    p = project or Project(None)
    out: list[str] = []
    for g in globs:
        m = PLACEHOLDER.match(g.strip())
        if not m:
            out.append(g.strip())
            continue
        for base in p.placeholder(m.group(1)):
            out.append(base[:-3] + "/" + m.group(2).lstrip("/") if m.group(2) and base.endswith("/**") else base + m.group(2))
    return [g for g in out if g]


def glob_any(path: str, globs: list[str]) -> bool:
    return any(_glob_rx(g).match(path) for g in globs)


def is_master(path: str, project: Project | None = None) -> bool:
    return glob_any(path, (project or Project(None)).requirement_globs)


def rule_ids(project: Project) -> set[str]:
    """Rule ids of the project's requirement map (the three formats above)."""
    ids: set[str] = set()
    if project.top is None:
        return ids
    for g in project.requirement_globs:
        for p in sorted(project.top.glob(g)):
            if not p.is_file():
                continue
            for ln in p.read_text(errors="replace").splitlines():
                for rx in ID_LINES:
                    m = rx.match(ln)
                    if m:
                        ids.add(m.group(1))
                        break
    return ids


def clear_caches() -> None:
    toplevel.cache_clear()
    for_top.cache_clear()
