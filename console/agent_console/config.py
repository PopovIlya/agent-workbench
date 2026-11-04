"""Paths and settings. Everything can be overridden by env vars so tests never touch real data."""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

PORT = int(os.environ.get("AGENT_CONSOLE_PORT", "8790"))
HOST = "127.0.0.1"  # never 0.0.0.0 (checked again in server.main)


def home() -> Path:
    """State dir (index, pid file, audit, scores). Outside the repo, mode 0700."""
    p = Path(os.environ.get("AGENT_CONSOLE_HOME", "~/.agent-console")).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    try:
        p.chmod(0o700)
    except OSError:
        pass
    return p


def _system_tz() -> str:
    """The Mac's own zone name from /etc/localtime (…/zoneinfo/Area/City), else UTC."""
    try:
        target = os.readlink("/etc/localtime")
    except OSError:
        return "UTC"
    return target.split("zoneinfo/", 1)[1] if "zoneinfo/" in target else "UTC"


TZ_NAME = _system_tz()  # the day boundary for "today" and per-day totals; DST-aware (zoneinfo). AGENT_CONSOLE_TZ overrides it


def tz_name() -> str:
    return os.environ.get("AGENT_CONSOLE_TZ", TZ_NAME)


def tz() -> ZoneInfo:
    return ZoneInfo(tz_name())


def _roots(env: str, default: str) -> list[str]:
    raw = os.environ.get(env, default)
    return [str(Path(r).expanduser()).rstrip("/") for r in raw.split(":") if r]


def tree_roots() -> list[str]:
    """A session whose first cwd is under one of these is a project session, reason "tree". Default: the home directory
    (every session of this user); narrow it to your project folders with AGENT_CONSOLE_TREE_ROOTS (colon-separated)."""
    return _roots("AGENT_CONSOLE_TREE_ROOTS", "~")


def worktree_roots() -> list[str]:
    """Same for a folder that holds git worktrees, reason "worktree". Default: none."""
    return _roots("AGENT_CONSOLE_WORKTREE_ROOTS", "")


def project_remote() -> str:
    """A checkout anywhere whose `origin` URL contains this text is a project session, reason "repo remote". Default: off."""
    return os.environ.get("AGENT_CONSOLE_PROJECT_REMOTE", "").lower()


def key_prefixes() -> list[str]:
    """Ticket key prefixes (space-separated, e.g. "PROJ OPS"). Empty: any `ABC-123` is a key (see tickets.NOT_KEYS)."""
    return [x.strip().upper() for x in os.environ.get("AGENT_CONSOLE_KEY_PREFIXES", "").split() if x.strip()]


DEFAULT_KEY_PATTERN = r"[A-Z][A-Z0-9]+-[A-Z0-9]+"  # a leading [KEY] in a spawn description / first prompt, any project


def key_patterns() -> list[str]:
    """Patterns (full match) a leading `[KEY]` may have. The first is built in; AGENT_CONSOLE_KEY_PATTERNS adds more,
    separated by whitespace (e.g. `[A-Z]+-[A-Z]+-[0-9]+` for a key with two hyphens). Only the bracket source uses
    these: git commands, paths and prompt text keep the Jira pattern."""
    extra = [x for x in os.environ.get("AGENT_CONSOLE_KEY_PATTERNS", "").split() if x]
    return [DEFAULT_KEY_PATTERN, *extra]


def _under(cwd: str, roots: list[str]) -> bool:
    c = (cwd or "").rstrip("/")
    return any(c == r or c.startswith(r + "/") for r in roots)


def classify_path(cwd: str | None) -> tuple[str, str] | None:
    """('project', 'tree'|'worktree') from the path alone, or None when the path says nothing (see store for the remote)."""
    if _under(cwd or "", tree_roots()):
        return "project", "tree"
    if _under(cwd or "", worktree_roots()):
        return "project", "worktree"
    return None


def log_root() -> Path:
    return Path(os.environ.get("AGENT_CONSOLE_LOG_ROOT", "~/.claude/projects")).expanduser()


def project_prefix() -> str:
    """Only log folders under ~/.claude/projects whose name starts with this are read. Default: all of them."""
    return os.environ.get("AGENT_CONSOLE_PROJECT_PREFIX", "")


def repo_root() -> Path:
    env = os.environ.get("AGENT_CONSOLE_REPO")
    return Path(env) if env else Path(__file__).resolve().parents[2]   # the workbench checkout: roles-22/, kit/, console/


def user_agents_dir() -> Path:
    """User-level role files (~/.claude/agents). Symlinks there are resolved; the workbench's own role file wins on a name clash."""
    return Path(os.environ.get("AGENT_CONSOLE_USER_AGENTS", "~/.claude/agents")).expanduser()


def roles_ref() -> str:
    """Git ref of the workbench read for role-file change markers and role-file versions. Empty (the default): the working tree."""
    return os.environ.get("AGENT_CONSOLE_ROLES_REF", "")


def claims_repo() -> Path | None:
    """A project checkout that uses the optional `claims` + `impact_map` gates; the console then checks each ticket's edits against its
    claim. Default: none (no scope check, no git fetch)."""
    v = os.environ.get("AGENT_CONSOLE_CLAIMS_REPO")
    return Path(v).expanduser() if v else None


def worklog_dirs() -> list[Path]:
    """Optional worklog folders (worklogs/*.jsonl with request lines), only when AGENT_CONSOLE_WORKLOGS names them. Default: none;
    the console reads ~/.claude/projects."""
    extra = os.environ.get("AGENT_CONSOLE_WORKLOGS")
    return [Path(p) for p in extra.split(os.pathsep) if p] if extra else []


def pricing_path() -> Path:
    return Path(os.environ.get("AGENT_CONSOLE_PRICING", str(Path(__file__).resolve().parents[1] / "pricing.yaml")))


def scores_path() -> Path:
    return Path(os.environ.get("AGENT_CONSOLE_SCORES", str(home() / "scores.jsonl")))


# ---- cost / time / quality (schema v9). Every threshold the new pages rely on lives here, one name each. ----
TEST_TIMEOUT_S = 590       # a test-class Bash call this long was a timeout or a permission prompt, not test time
PARKED_AFTER_S = 7200      # a human / ask wait longer than this: the session was left open, I was not at the desk
BLOCKED_AFTER_S = 600      # a non-test, non-agent, non-background tool call longer than this: most likely a permission prompt
CHILD_SHARE = 0.8          # a main session belongs to the ticket that this share of its keyed sub-agent runs carry
SHARED_SESSION_ROLES = 3   # a run is "shared" when its parent session started this many different roles or more
CONTEXT_RED_TOKENS = 200_000   # context re-read per call above this is shown red
UMBRELLA_DAYS = 7          # a real ticket key spanning more days than this is probably an umbrella key
MIN_SCORED_FOR_VERDICT = 5     # fewer scored runs than this: too few to judge or compare
GAP_CUT_S = 20 * 60        # timeline: gaps with nothing running longer than this are cut out
STALLED_AFTER_S = 1200     # a sub-agent run silent for longer than this between two records (not a test call, not a background wait): stalled
IDLE_STORE_S = 600         # silent gaps shorter than this are not stored (they are never a stall); STALLED_AFTER_S can be raised or lowered above it
