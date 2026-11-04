"""The claims branch is only ever fetched, never pushed."""

import subprocess

from agent_console import scope


def test_refresh_claims_is_a_fetch_and_nothing_else(monkeypatch, tmp_path):
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "fatal: couldn't find remote ref qa-claims")

    monkeypatch.delenv("AGENT_CONSOLE_NO_FETCH", raising=False)
    monkeypatch.setattr(scope.subprocess, "run", fake_run)
    monkeypatch.setattr(scope, "_last_fetch", 0.0)
    assert scope.refresh_claims(tmp_path) is False  # branch missing on the remote: not an error, just False
    assert len(calls) == 1 and "fetch" in calls[0] and not any(a in ("push", "commit", "update-ref") for a in calls[0])
    assert scope.refresh_claims(tmp_path) is False and len(calls) == 1  # throttled


def test_no_push_anywhere_in_the_package():
    from pathlib import Path
    src = "".join(p.read_text() for p in (Path(scope.__file__).parent).glob("*.py"))
    assert '"push"' not in src and "'push'" not in src
