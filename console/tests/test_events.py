"""Role-history events: a new ticket, a served-model change, and git commits on the role file, skills, shared rules, lessons and the scorer."""

import os
import subprocess
from datetime import datetime, timezone

from agent_console import events
from agent_console.ctq import Period


def hist(*rows):
    return [{"start": s, "ticket": t, "models": m} for s, t, m in rows]


def test_new_ticket_and_model_change_events():
    h = hist(("2026-10-20T10:00:00Z", "PROJ-1", {"claude-sonnet-5": 3}), ("2026-10-20T11:00:00Z", "PROJ-1", {"claude-sonnet-5-5": 2}), ("2026-10-20T12:00:00Z", "PROJ-2", {"claude-sonnet-5-5": 2}))
    ctx = events.EventCtx("builder", Period(0, 9e9), h)
    assert [(e["kind"], e["label"]) for e in events.new_ticket(ctx)] == [("ticket", "PROJ-2")]
    m = events.model_change(ctx)
    assert len(m) == 1 and m[0]["ts"] == "2026-10-20T11:00:00Z" and "claude-sonnet-5 → claude-sonnet-5-5" in m[0]["detail"]


def git(repo, *args, when="2026-10-20T10:00:00+00:00"):
    env = dict(os.environ, GIT_COMMITTER_DATE=when, GIT_AUTHOR_DATE=when, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.test", *args], check=True, capture_output=True, env=env)


def test_git_sources_for_role_file_shared_rules_and_the_scorer(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    files = {"roles-22/agents/builder.md": "a", "roles-22/agents/other.md": "a", "roles-22/SHARED-RULES.md": "a",
             "console/agent_scoring/agent_score.py": "a"}
    for i, (path, body) in enumerate(files.items()):
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", f"change {path}", when=f"2026-10-2{i}T10:00:00+00:00")
    monkeypatch.setenv("AGENT_CONSOLE_REPO", str(repo))
    monkeypatch.setenv("AGENT_CONSOLE_ROLES_REF", "HEAD")
    events._cache.clear()
    per = Period(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp(), datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp())
    got = events.role_events("builder", per, [])
    kinds = {e["kind"]: e["detail"] for e in got}
    assert set(kinds) == {"role file", "shared rules", "scorer"}
    assert "change roles-22/agents/builder.md" in kinds["role file"] and "other.md" not in " ".join(e["detail"] for e in got)   # another role's file is not this role's event
    assert [e["ts"] for e in got] == sorted(e["ts"] for e in got)


def test_a_broken_source_does_not_hide_the_others(monkeypatch):
    def boom(ctx):
        raise RuntimeError("x")
    monkeypatch.setattr(events, "SOURCES", [boom, events.new_ticket])
    h = hist(("2026-10-20T10:00:00Z", "PROJ-1", {}), ("2026-10-20T11:00:00Z", "PROJ-2", {}))
    assert [e["label"] for e in events.role_events("builder", Period(0, 9e9), h)] == ["PROJ-2"]
