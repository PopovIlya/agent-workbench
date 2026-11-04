"""Ticket scope (optional gates `claims` + `impact_map`): the modules a ticket claimed, mapped to file globs through the impact map.

Off unless AGENT_CONSOLE_CLAIMS_REPO names a project checkout that uses both gates. Sources (read-only, in that checkout): the
claim `qa/claims/<TICKET>.yaml` on the git data branch `qa-claims` (written by the project's claims tool), and
`qa/impact-map/*.yaml` (`module`, `code_paths.globs`). A ticket with no claim has no scope: the check is skipped and the
page says "no claim".
Also here: rel_path(), the repo-relative form of a path from a log (relative to the git checkout that holds it).
"""

from __future__ import annotations

import fnmatch
import re
import os
import subprocess  # nosec B404 - fixed argv, no shell
import time
from functools import lru_cache
from pathlib import Path

import yaml

@lru_cache(maxsize=4096)
def _checkout_of(d: str) -> str | None:
    """The nearest folder at or above `d` that holds `.git` (a directory, or a worktree's file), or None."""
    p = Path(d)
    for x in [p, *p.parents]:
        try:
            if (x / ".git").exists():
                return str(x)
        except OSError:
            return None
    return None


def rel_path(p: str) -> str | None:
    """Repo-relative form of an absolute path from a log; None if it is outside any git checkout (or the checkout is gone)."""
    if not p:
        return None
    if not p.startswith("/"):
        return p.lstrip("./")
    top = _checkout_of(str(Path(p).parent))
    if top and p.startswith(top.rstrip("/") + "/"):
        return p[len(top.rstrip("/")) + 1:]
    m = re.search(r"/worktrees/[^/]+/(.*)$", p)   # a worktree folder that was removed since
    if m:
        return m.group(1)
    return None


def matches(path: str, globs: list[str]) -> bool:
    for g in globs:
        g = g.rstrip("/")
        if fnmatch.fnmatch(path, g) or path.startswith(g + "/"):
            return True
    return False


class ScopeProvider:
    def __init__(self, repo: Path, claim_loader=None):
        self.repo = repo
        self._claim_loader = claim_loader or self._git_claim
        self._globs: dict[str, list[str]] | None = None

    def module_globs(self) -> dict[str, list[str]]:
        if self._globs is None:
            out: dict[str, list[str]] = {}
            for f in sorted((self.repo / "qa" / "impact-map").glob("*.yaml")):
                try:
                    d = yaml.safe_load(f.read_text()) or {}
                except (OSError, yaml.YAMLError):
                    continue
                if isinstance(d, dict) and d.get("module"):
                    out[str(d["module"])] = list(((d.get("code_paths") or {}).get("globs")) or [])
            self._globs = out
        return self._globs

    def _git_claim(self, ticket: str) -> list[str] | None:
        if not re.fullmatch(r"[A-Z]+-\d{3,6}", ticket):  # only ever a key matched by the log parser; refuse anything else
            return None
        for ref in ("origin/qa-claims", "qa-claims"):
            try:
                r = subprocess.run(["git",  # nosec B603 B607 - fixed argv, no shell, ticket validated above
                                   "-C", str(self.repo), "show", f"{ref}:qa/claims/{ticket}.yaml"],
                                   capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.SubprocessError):
                return None
            if r.returncode == 0:
                try:
                    mods = (yaml.safe_load(r.stdout) or {}).get("modules")
                except yaml.YAMLError:
                    return None
                return [str(m) for m in mods] if isinstance(mods, list) else None
        return None

    @lru_cache(maxsize=512)
    def _claim(self, ticket: str) -> tuple[str, ...] | None:
        mods = self._claim_loader(ticket)
        return tuple(mods) if mods else None

    def allowed_globs(self, ticket: str) -> list[str] | None:
        """Globs the ticket may touch, or None when there is no claim (no scope to check)."""
        mods = self._claim(ticket)
        if mods is None:
            return None
        known = self.module_globs()
        globs = [g for m in mods for g in known.get(m, [])]
        globs += [f"**/changes/{ticket}.md", f"docs/agents/work/{ticket}/*", f"**/{ticket}*", "qa/claims/*", "qa/impact-map/*"]
        return globs


_last_fetch = 0.0
FETCH_EVERY_S = 600


def refresh_claims(repo: Path) -> bool:
    """Read-only `git fetch` of the claims data branch so claims can be read locally.

    Never pushes, never writes to the branch (the project's claims tool is the only writer). The branch may not
    exist on the remote yet; that is not an error. Set AGENT_CONSOLE_NO_FETCH=1 to skip (tests).
    """
    global _last_fetch
    if os.environ.get("AGENT_CONSOLE_NO_FETCH") or time.time() - _last_fetch < FETCH_EVERY_S:
        return False
    _last_fetch = time.time()
    try:
        r = subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin",  # nosec B603 B607 - fixed argv, fetch only
                            "+refs/heads/qa-claims:refs/remotes/origin/qa-claims"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0
