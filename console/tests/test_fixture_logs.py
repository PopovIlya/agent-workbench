"""The hand-written JSONL fixtures in tests/fixtures/logs (no real log line): a main session that spawns kit-analyst for PROJ-123."""

import shutil
from pathlib import Path

from agent_console.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "logs"


def test_the_fixture_session_is_read_with_its_ticket_role_tokens_and_reply(env, monkeypatch):
    shutil.copytree(FIXTURES, env.root)
    monkeypatch.setenv("AGENT_CONSOLE_TREE_ROOTS", "/work/shop")
    s = Store()
    s.ingest()
    db = s.reader()
    rows = {r["run_id"]: dict(r) for r in db.execute("SELECT run_id, kind, role, ticket, ticket_src, scope FROM runs")}
    sub = rows["S-fixture-1:fx1"]
    assert (sub["kind"], sub["role"], sub["ticket"], sub["ticket_src"], sub["scope"]) == ("sub", "kit-analyst", "PROJ-123", "spawn_lead", "project")
    assert rows["S-fixture-1"]["ticket"] == "PROJ-123" and rows["S-fixture-1"]["kind"] == "main"
    out = db.execute("SELECT sum(output) FROM usage WHERE run_id='S-fixture-1:fx1'").fetchone()[0]
    assert out == 200 + 900 + 20
    writes = [r["path"] for r in db.execute("SELECT path FROM tool_calls WHERE run_id='S-fixture-1:fx1' AND name='Write'")]
    assert writes == ["/work/shop/docs/agents/work/PROJ-123/analyst-as-is.md"]
