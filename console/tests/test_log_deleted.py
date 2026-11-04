"""A run whose log file is gone stays in the index, marked "log deleted": after a plain rescan and across a schema rebuild."""

import sqlite3

from fastapi.testclient import TestClient

from agent_console import queries, server
from agent_console.store import SCHEMA_VERSION, Store
from conftest import PROJECT, add_sub, assistant, tool_use, usage, user_prompt, write_jsonl


def make_logs(env):
    spawn = [tool_use("toolu_a1", "Agent", subagent_type="builder", description="[PROJ-700] build", prompt="p")]
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("[PROJ-700] go", t=1), assistant("m1", blocks=spawn, t=2)])
    return add_sub(env.root, "S1", "a1", "builder", [assistant("a1m", agent="a1", t=5, u=usage(100, 7))], "toolu_a1")


def run_row(s, rid):
    db = s.reader()
    try:
        r = db.execute("SELECT run_id, ticket, output FROM runs WHERE run_id=?", (rid,)).fetchone()
        return tuple(r) if r else None
    finally:
        db.close()


def test_a_deleted_log_survives_a_rescan_and_is_marked(env):
    sub = make_logs(env)
    s = Store()
    s.ingest()
    before = run_row(s, "S1:a1")
    assert before == ("S1:a1", "PROJ-700", 7)
    sub.unlink()
    s.ingest()
    assert run_row(s, "S1:a1") == before
    d = queries.run_detail(s, server.Pricing.load(env.tmp / "pricing.yaml"), "S1:a1")
    assert d["log_deleted"] is True and any(f.startswith("Log deleted") for f in queries.run_findings(d))
    t = queries.show_text(s, "S1:a1", "final")
    assert t["text"] == "" and t["note"].startswith("log deleted")


def test_a_deleted_log_survives_a_schema_rebuild(env):
    sub = make_logs(env)
    s = Store()
    s.ingest()
    before = run_row(s, "S1:a1")
    s.db.close()
    sub.unlink()
    db = sqlite3.connect(env.home / "index.sqlite")
    db.execute(f"PRAGMA user_version={SCHEMA_VERSION - 1}")      # what an older console left behind
    db.execute("ALTER TABLE messages DROP COLUMN verdict")        # and an older raw table shape
    db.commit()
    db.close()
    s2 = Store()                                                   # schema bump: everything is rebuilt from the logs
    s2.ingest()
    assert run_row(s2, "S1:a1") == before                          # the run whose log is gone is still there, same numbers
    assert run_row(s2, "S1") is not None                           # the main session (log still on disk) was re-read
    with TestClient(server.create_app(store=s2)) as c:
        runs = c.get("/api/ctq/tickets/PROJ-700", params={"scope": "all", "from": "2026-10-01", "to": "2026-10-31"}).json()["runs"]
        mine = [r for r in runs if r["run_id"] == "S1:a1"]
        assert mine and mine[0]["log_deleted"] is True
        assert [r["log_deleted"] for r in runs if r["run_id"] == "S1"] == [False]
    assert s2.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
