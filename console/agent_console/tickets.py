"""Ticket key derivation. Every key carries the source it came from, shown in the UI.

Main goal: name the ticket a run belongs to without editing agent files.
Sources, strongest first (the first one that yields a key wins):
  worklog      only when AGENT_CONSOLE_WORKLOGS names worklog folders: the `ticket` of the request line covering the run's start time
  spawn_lead   spawn description starting with the key, e.g. "[PROJ-123] build ..." or "[PILOT-A] ..."
  prompt_lead  the run's first prompt starting with the key
               A leading `[KEY]` is authoritative whatever the key's format (letters, digits, hyphens, 2-40 chars,
               at least one hyphen; config.key_patterns()). `[WIP]` / `[TODO]` have no hyphen and are never keys.
               Every other source below keeps the Jira pattern only.
  change_file  an Edit/Write path `.../changes/<KEY>.md` or `.../work/<KEY>/...`
  git_command  a key in a git command (checkout/switch/branch/push/commit/worktree ...)
  worktree_dir the key in a directory name of the run's cwd (worktrees/app-PROJ-123-x; with prefixes also /tmp/proj123-verify)
  worktree_branch the branch checked out in the linked worktree the run started in
  branch       the `gitBranch` field of the log (usually "HEAD", so rarely useful)
  path         any other edited path that contains a key
  spawn_text   a key anywhere in the spawn description or prompt
  prompt       a key anywhere in the first prompt
  parent       the spawning run's ticket
"""

from __future__ import annotations

import re
import subprocess  # nosec B404 - read-only `git worktree list`, fixed argv, no shell
import sys
from collections import Counter
from pathlib import Path

from . import config

# Ticket keys. AGENT_CONSOLE_KEY_PREFIXES (space-separated, e.g. "PROJ OPS") limits keys to those prefixes; without it any
# `ABC-123` counts, except common non-ticket tokens (UTF-8, ISO-8601, SHA-256, ...). Read once at import: restart after a change.
NOT_KEYS = ("UTF", "ISO", "SHA", "AES", "RFC", "PEP", "CVE", "HTTP", "TLS", "SSL", "RSA", "GPT", "CWE", "OWASP", "ASVS", "IEC", "ECMA", "WCAG")


def configure(prefixes: list[str]) -> None:
    """(Re)build the key patterns for these prefixes (empty: any `ABC-123`). Called once at import from config.key_prefixes()."""
    global _PFX, KEY_RE, LEAD_RE, DIR_KEY_RE, CHANGE_FILE_RE
    _PFX = ("(?:" + "|".join(re.escape(x) for x in prefixes) + ")") if prefixes else "(?!(?:" + "|".join(NOT_KEYS) + ")-)[A-Z][A-Z0-9]{1,9}"
    KEY_RE = re.compile(rf"(?<![A-Za-z0-9-]){_PFX}-\d{{1,6}}\b")          # never the tail of `AB-CD-12`
    LEAD_RE = re.compile(rf"^\W{{0,4}}({_PFX}-\d{{1,6}})\b")
    # a key in a directory name: `app-PROJ-123-fix`; with prefixes also case-insensitive and without the hyphen: `proj123-verify`
    DIR_KEY_RE = (re.compile(r"(?i)(?<![a-z])(" + "|".join(re.escape(x) for x in prefixes) + r")[-_]?(\d{1,6})(?!\d)") if prefixes
                  else re.compile(rf"(?<![A-Za-z0-9])({_PFX})-(\d{{1,6}})(?!\d)"))
    CHANGE_FILE_RE = re.compile(rf"/(?:changes|work)/({_PFX}-\d{{1,6}})(?:\.md$|/)")   # `changes/<KEY>.md` or a kit work folder `work/<KEY>/`


configure(config.key_prefixes())
BRACKET_RE = re.compile(r"^[^\w\[]{0,4}\[([A-Za-z0-9-]{2,40})\]")  # a leading [KEY]; the content is then checked
_compiled: dict[tuple[str, ...], list[re.Pattern]] = {}
ORDER = ("worklog", "spawn_lead", "prompt_lead", "change_file", "git_command", "worktree_dir",
         "worktree_branch", "branch", "path", "spawn_text", "prompt", "parent")


def _bracket_patterns() -> list[re.Pattern]:
    pats = tuple(config.key_patterns())
    if pats not in _compiled:
        ok = []
        for p in pats:
            try:
                ok.append(re.compile(p))
            except re.error as e:  # a bad extra pattern must not take the console down; the rest still work
                print(f"agent-console: ignoring key pattern {p!r}: {e}", file=sys.stderr)
        _compiled[pats] = ok
    return _compiled[pats]


def bracket_key(text: str | None) -> str | None:
    """`[PILOT-A] build ...` -> PILOT-A. Needs a hyphen and a full match of one configured pattern."""
    m = BRACKET_RE.match(text or "")
    if not m or "-" not in m.group(1):
        return None
    return m.group(1) if any(p.fullmatch(m.group(1)) for p in _bracket_patterns()) else None


def lead_key(text: str | None) -> str | None:
    k = bracket_key(text)
    if k:
        return k
    m = LEAD_RE.match(text or "")
    return m.group(1) if m else None


def dir_key(cwd: str | None) -> str | None:
    """Key from a directory name of the cwd (`PROJ-123-x` -> PROJ-123; with prefixes, case-insensitive: `proj123-verify` -> PROJ-123)."""
    for seg in (cwd or "").split("/"):
        m = DIR_KEY_RE.search(seg)
        if m:
            return f"{m.group(1).upper()}-{m.group(2)}"
    return None


def most_common(keys: Counter | list[str]) -> str | None:
    """Highest count; a tie goes to the smaller key, so the answer never depends on iteration or file order."""
    c = keys if isinstance(keys, Counter) else Counter(keys)
    return min(c, key=lambda k: (-c[k], k)) if c else None


def latest_before(evidence: list[tuple[str, str, str]], ts: str | None) -> tuple[str, str] | None:
    """(key, source) of the newest evidence at or before `ts`; same timestamp -> smaller key. None if there is none."""
    ok = [e for e in evidence if ts is None or e[0] <= ts]
    if not ok:
        return None
    best = max(ok, key=lambda e: (e[0], [-ord(ch) for ch in e[1]]))
    return best[1], best[2]


def resolve(hits: dict[str, str | None]) -> tuple[str | None, str]:
    for src in ORDER:
        if hits.get(src):
            return hits[src], src
    return None, "unknown"


def worktree_branches(repo: Path) -> dict[str, str]:
    """{worktree path: branch} for LINKED worktrees only (the main checkout's branch changes over time)."""
    try:
        out = subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"],  # nosec B603 B607
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    res: dict[str, str] = {}
    first = True
    path = None
    for line in out.splitlines() + [""]:
        if line.startswith("worktree "):
            path = line[9:]
        elif line.startswith("branch ") and path and not first:
            res[path] = line[7:].removeprefix("refs/heads/")
        elif line == "":
            if path is not None:
                first = False
            path = None
    return res


def worktree_branch_key(cwd: str | None, wts: dict[str, str]) -> str | None:
    best = max((p for p in wts if (cwd or "").startswith(p.rstrip("/") + "/") or cwd == p), key=len, default=None)
    if not best:
        return None
    m = KEY_RE.search(wts[best])
    return m.group(0) if m else None


def effective_tickets(rows: dict[str, dict]) -> None:
    """Set ticket_eff / ticket_eff_via / eff_children / eff_share_n on every run row (in place).
    A sub-agent run keeps its own key (via "own"). A main session takes the key carried by at least CHILD_SHARE of its keyed sub-agent runs
    (via "children"), because a session's own key comes from its branch or its git commands and is often another ticket's.
    A session whose children disagree, or have no key, keeps its own key. One key per session: its cost is not split."""
    kids: dict[str, list[str]] = {}
    for r in rows.values():
        if r["kind"] == "sub" and r["ticket"]:
            kids.setdefault(r["session_id"], []).append(r["ticket"])
    for rid, r in rows.items():
        r.update(ticket_eff=r["ticket"], ticket_eff_via="own", eff_children=0, eff_share_n=0)
        if r["kind"] != "main":
            continue
        keys = kids.get(r["session_id"], [])
        r["eff_children"] = len(keys)
        if not keys:
            continue
        top, n = min(Counter(keys).items(), key=lambda kv: (-kv[1], kv[0]))
        r["eff_share_n"] = n
        if n / len(keys) >= config.CHILD_SHARE:
            r["ticket_eff"] = top
            r["ticket_eff_via"] = "children" if top != r["ticket"] else "own"
