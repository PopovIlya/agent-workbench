"""Fixtures: synthetic Claude Code logs with the real field names (no real log text)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROJECT = "-work-app"
REAL_GITLEAKS = Path(__file__).resolve().parents[2] / ".gitleaks.toml"   # the workbench's own config


def usage(inp=10, out=20, cr=0, cw=0, w5=None, w1=0):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw,
            "cache_creation": {"ephemeral_5m_input_tokens": cw if w5 is None else w5, "ephemeral_1h_input_tokens": w1}}


def ts(n: int, day: str = "2026-10-20") -> str:
    return f"{day}T10:{n // 60:02d}:{n % 60:02d}.000Z"


def assistant(msg_id, model="claude-sonnet-5-5", u=None, blocks=None, t=0, session="S1", agent=None, requested=None, day="2026-10-20", rid=None, cwd="/work/app", **extra):
    o = {"parentUuid": None, "isSidechain": agent is not None, "type": "assistant", "uuid": f"u-{msg_id}-{len(blocks or [])}",
         "timestamp": ts(t, day) if "T" not in str(day) else day, "cwd": cwd, "gitBranch": extra.pop("branch", "HEAD"), "sessionId": session,
         "message": {"id": msg_id, "model": model, "usage": u or usage(), "content": blocks or [{"type": "text", "text": "ok"}]}}
    if agent:
        o["agentId"] = agent
    if requested:
        o["requestedModel"] = requested
    if rid:
        o["requestId"] = rid
    o.update(extra)
    return o


def user_prompt(text, t=0, session="S1", agent=None, cwd="/work/app", day="2026-10-20"):
    return {"parentUuid": None, "isSidechain": agent is not None, "type": "user", "uuid": f"up-{t}-{session}", "timestamp": ts(t, day), "sessionId": session,
            "cwd": cwd, "gitBranch": "HEAD", "message": {"role": "user", "content": text}}


def tool_use(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def tool_result(tid, err=False, t=0, session="S1"):
    return {"parentUuid": None, "type": "user", "uuid": f"tr-{tid}", "timestamp": ts(t), "sessionId": session, "toolUseResult": {"x": 1},
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": err, "content": "x"}]}}


def api_error(t=0, session="S1", status=403, message="403 {\"Message\":\"User: arn:aws:sts::000000000000:assumed-role/x is not authorized\"}"):
    return {"type": "system", "subtype": "api_error", "timestamp": ts(t), "sessionId": session, "error": {"message": message, "status": status}}


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def add_sub(root: Path, session: str, agent: str, role: str, records: list[dict], tool_use_id: str, model: str | None = None) -> Path:
    base = root / PROJECT / session / "subagents"
    p = base / f"agent-{agent}.jsonl"
    write_jsonl(p, records)
    meta = {"agentType": role, "toolUseId": tool_use_id, "spawnDepth": 1, "description": "x"}
    if model:
        meta["model"] = model
    (base / f"agent-{agent}.meta.json").write_text(json.dumps(meta))
    return p


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated log root, state dir and workbench (role files, criteria, gitleaks)."""
    root, home, repo = tmp_path / "projects", tmp_path / "home", tmp_path / "repo"
    (repo / "roles-22" / "agents").mkdir(parents=True)
    (repo / "roles-22" / "criteria").mkdir(parents=True)
    (repo / "qa" / "impact-map").mkdir(parents=True)
    (repo / "worklogs").mkdir()
    shutil.copy(REAL_GITLEAKS, repo / ".gitleaks.toml")
    monkeypatch.setenv("AGENT_CONSOLE_LOG_ROOT", str(root))
    monkeypatch.setenv("AGENT_CONSOLE_HOME", str(home))
    monkeypatch.setenv("AGENT_CONSOLE_REPO", str(repo))
    monkeypatch.setenv("AGENT_CONSOLE_DEFAULT_PROJECT", str(repo))   # the fixture runs' cwds do not exist: judge them against the fake repo
    from agent_scoring import project as _project
    _project.clear_caches()
    monkeypatch.setenv("AGENT_CONSOLE_NO_FETCH", "1")
    monkeypatch.setenv("AGENT_CONSOLE_USER_AGENTS", str(tmp_path / "user-agents"))   # never the real ~/.claude/agents
    monkeypatch.setenv("AGENT_CONSOLE_TREE_ROOTS", "/work/app")
    monkeypatch.setenv("AGENT_CONSOLE_WORKTREE_ROOTS", "/work/worktrees")
    for v in ("AGENT_CONSOLE_ROLE_DIRS", "AGENT_CONSOLE_CRITERIA_DIRS", "AGENT_CONSOLE_CLAIMS_REPO", "AGENT_CONSOLE_ROLES_REF", "AGENT_CONSOLE_KEY_PREFIXES"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("AGENT_CONSOLE_PROJECT_REMOTE", "example-app")   # a checkout whose origin names it is a project session
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "Europe/Madrid")
    monkeypatch.setenv("AGENT_CONSOLE_WORKLOGS", str(repo / "worklogs"))
    monkeypatch.setenv("AGENT_CONSOLE_SCORES", str(home / "scores.jsonl"))
    monkeypatch.setenv("AGENT_CONSOLE_PRICING", str(tmp_path / "pricing.yaml"))
    (tmp_path / "pricing.yaml").write_text("models: {}\n")
    return type("Env", (), {"root": root, "home": home, "repo": repo, "tmp": tmp_path})


def role_file(repo: Path, name: str, tools: str = "Read, Grep", model: str = "sonnet", output: str | None = None) -> None:
    body = f"---\nname: {name}\ndescription: d\ntools: {tools}\nmodel: {model}\n---\n\nYou are {name}.\n"
    if output is not None:
        body += f"\n## Output\n{output}\n\n## Does\n- x\n"
    (repo / "roles-22" / "agents" / f"{name}.md").write_text(body)


def flat_routes(app):
    """All endpoints of a FastAPI app, descending into included routers (newer FastAPI nests them)."""
    out = []
    for r in app.routes:
        sub = getattr(r, "original_router", None)
        if sub is not None:
            out += [x for x in sub.routes if hasattr(x, "methods")]
        elif hasattr(r, "methods"):
            out.append(r)
    return out

