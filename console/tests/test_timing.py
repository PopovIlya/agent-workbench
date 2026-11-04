"""Schema v9: tool-call end times and classes, waits, the per-run time split, main-session ticket attribution. Hand-written fixtures only."""

import sqlite3

import pytest

from agent_console import config, tickets
from agent_console.parser import classify_command
from agent_console.store import Store
from ctq_fixtures import A, P, R, TU, add_sub, at, main_file, one_call, q

from conftest import PROJECT, tool_use, write_jsonl  # noqa: F401


def kinds(waits):
    return [(w["kind"], round(w["dur_s"])) for w in waits]


# ---------- A1: tool results and classes ----------
def test_tool_result_matching_end_ts_and_duration(env):
    _, tc, _ = one_call(env, "Read", 12.5, file_path="/r/a.py")
    assert tc["end_ts"] == at(17.5) and tc["dur_s"] == pytest.approx(12.5)


def test_call_without_result_has_no_end(env):
    main_file(env, [P(0, "human"), A("m1", 5, [TU("t1", "Read", file_path="/r/a.py")])])
    s = Store()
    s.ingest()
    tc = q(s, "SELECT * FROM tool_calls WHERE id='t1'")[0]
    assert tc["end_ts"] is None and tc["dur_s"] is None


@pytest.mark.parametrize("cmd,cls", [
    ("cd x && poetry run pytest -q tests", "pytest"), ("python3 -m pytest a -x", "pytest"), ("\"$PY\" -m pytest a", "pytest"),
    ("ruff check . && ruff format --check .", "ruff"), ("FOO=1 .venv/bin/mypy src", "mypy"),
    ("cd ui && npx vitest run", "frontend_test"), ("npm run test:unit", "frontend_test"), ("make -C tools test", "make_test"),
    ("git status && git diff | head", "git"), ("ls -la | grep foo", "other"),
    ("ruff check . ; pytest -q", "ruff"),                 # a chained command takes its first test segment's class
    ("git commit -m \"ran pytest; ruff ok\"", "git"),      # words inside a quoted message never classify
    ("cat <<'EOF'\npytest nothing\nEOF", "other"),         # nor words inside a here-document
    ("git log | grep pytest", "git"), ("echo mypy", "other"),
])
def test_command_classes(cmd, cls):
    assert classify_command(cmd) == cls


def test_class_stored_command_never(env):
    secret, token = "AKI" + "A" + "FAKE" * 3 + "1234", "tok_" + "fake_do_not_store_9f8e7d"   # assembled: no key-shaped literal in the file
    cmd = f"AWS_SECRET_ACCESS_KEY={secret} pytest -q --token {token} tests/test_x.py && git push https://u:{token}@host/x.git"
    main_file(env, [P(0, "human", text=f"use {token}"), A("m1", 5, [TU("t1", "Bash", command=cmd, description=f"run {token}")]), R("t1", 9), A("m2", 10)])
    s = Store()
    s.ingest()
    assert q(s, "SELECT cmd_class FROM tool_calls WHERE id='t1'")[0]["cmd_class"] == "pytest"
    db = sqlite3.connect(s.db_path)
    db.execute("PRAGMA wal_checkpoint(FULL)")
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for row in db.execute(f'SELECT * FROM "{table}"'):  # nosec B608 - table names come from sqlite_master
            for v in row:
                assert not (isinstance(v, str) and (secret in v or token in v or "pytest -q" in v)), (table, v)
    raw = (s.db_path).read_bytes() + (s.db_path.with_name(s.db_path.name + "-wal").read_bytes() if s.db_path.with_name(s.db_path.name + "-wal").exists() else b"")
    assert secret.encode() not in raw and token.encode() not in raw


def test_background_flag_for_bash_and_background_test_not_timed(env):
    s, tc, _ = one_call(env, "Bash", 3, command="pytest -q", run_in_background=True)
    assert tc["background"] == 1 and tc["dur_s"] is None and tc["timed_out"] == 0
    r = q(s, "SELECT test_n, test_bg_n, test_s FROM runs WHERE run_id='S1'")[0]
    assert (r["test_n"], r["test_bg_n"], r["test_s"]) == (0, 1, 0)


# ---------- A1: timeout boundary ----------
def test_test_timeout_boundary(env):
    assert config.TEST_TIMEOUT_S == 590
    s, tc, _ = one_call(env, "Bash", 589, command="pytest -q")
    assert tc["timed_out"] == 0
    r = q(s, "SELECT test_s, test_n, test_timeouts FROM runs WHERE run_id='S1'")[0]
    assert (round(r["test_s"]), r["test_n"], r["test_timeouts"]) == (589, 1, 0)


def test_test_timeout_at_590(env):
    s, tc, _ = one_call(env, "Bash", 590, command="pytest -q")
    assert tc["timed_out"] == 1
    r = q(s, "SELECT test_s, test_n, test_timeouts, tool_s FROM runs WHERE run_id='S1'")[0]
    assert (r["test_s"], r["test_n"], r["test_timeouts"]) == (0, 1, 1) and round(r["tool_s"]) == 590   # not test time, still tool time


# ---------- A2: waits ----------
def test_human_wait(env):
    main_file(env, [P(0, "human"), A("m1", 10), P(110, "human"), A("m2", 112)])
    s = Store()
    s.ingest()
    assert kinds(q(s, "SELECT * FROM waits")) == [("human", 100)]
    r = q(s, "SELECT human_wait_s, model_s FROM runs WHERE run_id='S1'")[0]
    assert round(r["human_wait_s"]) == 100 and round(r["model_s"]) == 12


def test_meta_and_tool_result_records_are_not_waits(env):
    main_file(env, [P(0, "human"), A("m1", 10, [TU("t1", "Read", file_path="/r/a")]), R("t1", 500), P(600, "human", meta=True), A("m2", 601)])
    s = Store()
    s.ingest()
    assert q(s, "SELECT * FROM waits") == []


def test_notification_wait(env):
    main_file(env, [P(0, "human"), A("m1", 10), P(400, "task-notification"), A("m2", 401)])
    s = Store()
    s.ingest()
    assert kinds(q(s, "SELECT * FROM waits")) == [("notification", 390)]
    assert round(q(s, "SELECT notif_wait_s, human_wait_s FROM runs")[0]["notif_wait_s"]) == 390


def test_ask_wait_is_not_tool_time(env):
    main_file(env, [P(0, "human"), A("m1", 5, [TU("q1", "AskUserQuestion", questions=[])]), R("q1", 305), A("m2", 306)])
    s = Store()
    s.ingest()
    assert kinds(q(s, "SELECT * FROM waits")) == [("ask", 300)]
    r = q(s, "SELECT human_wait_s, tool_s FROM runs")[0]
    assert round(r["human_wait_s"]) == 300 and r["tool_s"] == 0


def test_parked_boundary_human(env):
    assert config.PARKED_AFTER_S == 7200
    for dur, kind in ((7199, "human"), (7201, "parked")):
        main_file(env, [P(0, "human"), A("m1", 10), P(10 + dur, "human"), A("m2", 12 + dur)])
        (env.home / "index.sqlite").unlink(missing_ok=True)
        s = Store()
        s.ingest()
        assert kinds(q(s, "SELECT * FROM waits")) == [(kind, dur)]
        r = q(s, "SELECT human_wait_s, parked_s FROM runs")[0]
        assert (round(r["human_wait_s"]), round(r["parked_s"])) == ((dur, 0) if kind == "human" else (0, dur))


def test_parked_boundary_ask(env):
    for dur, kind in ((7199, "ask"), (7201, "parked")):
        main_file(env, [P(0, "human"), A("m1", 5, [TU("q1", "AskUserQuestion", questions=[])]), R("q1", 5 + dur), A("m2", 6 + dur)])
        (env.home / "index.sqlite").unlink(missing_ok=True)
        s = Store()
        s.ingest()
        assert kinds(q(s, "SELECT * FROM waits")) == [(kind, dur)]


def test_blocked_boundary(env):
    assert config.BLOCKED_AFTER_S == 600
    s, tc, waits = one_call(env, "Bash", 600, command="ls")
    assert tc["blocked"] == 0 and waits == []
    r = q(s, "SELECT tool_s, blocked_s FROM runs")[0]
    assert round(r["tool_s"]) == 600 and r["blocked_s"] == 0
    (env.home / "index.sqlite").unlink()
    s, tc, waits = one_call(env, "Bash", 601, command="ls")
    assert tc["blocked"] == 1 and kinds(waits) == [("blocked", 601)]
    r = q(s, "SELECT tool_s, blocked_s FROM runs")[0]
    assert r["tool_s"] == 0 and round(r["blocked_s"]) == 601


def test_agent_calls_and_background_and_tests_are_never_blocked(env):
    for name, inp in (("Agent", {"subagent_type": "x", "description": "d", "prompt": "p"}), ("Bash", {"command": "sleep 900", "run_in_background": True}),
                      ("Bash", {"command": "pytest -q"})):
        (env.home / "index.sqlite").unlink(missing_ok=True)
        _, tc, waits = one_call(env, name, 900, **inp)
        assert tc["blocked"] == 0 and not [w for w in waits if w["kind"] == "blocked"]


def test_agent_call_time_is_not_tool_time(env):
    s, _, _ = one_call(env, "Agent", 300, subagent_type="x", description="d", prompt="p")
    assert q(s, "SELECT tool_s FROM runs WHERE run_id='S1'")[0]["tool_s"] == 0


# ---------- A3: per-run split ----------
def test_split_adds_up_and_unattributed_is_the_rest(env):
    main_file(env, [P(0, "human"), A("m1", 5, [TU("t1", "Bash", command="pytest -q")]), R("t1", 15), A("m2", 17, [TU("t2", "Read", file_path="/r/a")]),
                    R("t2", 20), A("m3", 21), P(121, "human"), A("m4", 123)])
    s = Store()
    s.ingest()
    r = q(s, "SELECT * FROM runs WHERE run_id='S1'")[0]
    assert round(r["model_s"]) == 5 + 2 + 1 + 2 and round(r["test_s"]) == 10 and round(r["tool_s"]) == 3 and round(r["human_wait_s"]) == 100
    assert r["unattributed_s"] == pytest.approx(0, abs=0.01)          # 10 + 10 + 3 + 100 = the 123 s wall time


def test_unattributed_is_what_no_category_explains(env):
    main_file(env, [P(0, "human"), A("m1", 5, [TU("sp", "Agent", subagent_type="x", description="d", prompt="p")]), R("sp", 305), A("m2", 306)])
    s = Store()
    s.ingest()
    r = q(s, "SELECT model_s, unattributed_s FROM runs WHERE run_id='S1'")[0]
    assert round(r["unattributed_s"]) == 300 and round(r["model_s"]) == 6      # waiting for a sub-agent is neither model nor tool time


def test_parallel_tool_calls_use_the_union(env):
    blocks = [TU("a", "Bash", command="ls"), TU("b", "Bash", command="ls")]
    main_file(env, [P(0, "human"), A("m1", 10, [blocks[0]]), A("m1b", 15, [blocks[1]], stop="tool_use"), R("a", 20), R("b", 30), A("m2", 31)])
    s = Store()
    s.ingest()
    # a: 10-20, b: 15-30 -> union 10-30 = 20 s, not 10 + 15 = 25 s
    assert round(q(s, "SELECT tool_s FROM runs")[0]["tool_s"]) == 20


def test_unmarked_user_record_counts_as_a_typed_prompt(env):
    main_file(env, [P(0), A("m1", 10), P(70), A("m2", 71)])
    s = Store()
    s.ingest()
    assert kinds(q(s, "SELECT * FROM waits")) == [("human", 60)]


# ---------- incremental ingest keeps the carry-over ----------
def test_resume_in_the_middle_keeps_gap_and_model_time(env):
    path = env.root / PROJECT / "S1.jsonl"
    recs = [P(0, "human"), A("m1", 10), P(110, "human"), A("m2", 112)]
    write_jsonl(path, recs[:2])
    s = Store()
    s.ingest()
    write_jsonl(path, recs)       # the file grows (same first line): only the new lines are parsed
    s.ingest()
    assert kinds(q(s, "SELECT * FROM waits")) == [("human", 100)]
    assert round(q(s, "SELECT model_s FROM runs")[0]["model_s"]) == 12


# ---------- idempotent rebuild ----------
def test_full_rebuild_twice_gives_the_same_numbers(env):
    main_file(env, [P(0, "human"), A("m1", 5, [TU("t1", "Bash", command="pytest -q"), TU("sp", "Agent", subagent_type="builder", description="[PROJ-9] x", prompt="p")]),
                    R("t1", 15), P(200, "human"), A("m2", 202)])
    add_sub(env.root, "S1", "a1", "builder", [A("s1", 30, agent="a1"), A("s2", 40, agent="a1")], "sp")

    def snapshot():
        (env.home / "index.sqlite").unlink(missing_ok=True)
        s = Store()
        s.ingest()
        s.ingest()   # a second pass over an unchanged index changes nothing either
        return ([q(s, "SELECT * FROM runs ORDER BY run_id"), q(s, "SELECT * FROM waits ORDER BY run_id, start_ts, kind"),
                 q(s, "SELECT run_id, id, end_ts, dur_s, cmd_class, timed_out, blocked FROM tool_calls ORDER BY run_id, id")])
    assert snapshot() == snapshot()


# ---------- A4: attribution ----------
def row(rid, kind, ticket, session="S1"):
    return {"run_id": rid, "kind": kind, "ticket": ticket, "session_id": session}


def eff(n_a, n_b, own="PROJ-1", extra=None):
    rows = {"S1": row("S1", "main", own)}
    for i in range(n_a):
        rows[f"a{i}"] = row(f"a{i}", "sub", "PROJ-2")
    for i in range(n_b):
        rows[f"b{i}"] = row(f"b{i}", "sub", "PROJ-3")
    for r in (extra or []):
        rows[r["run_id"]] = r
    tickets.effective_tickets(rows)
    return rows["S1"]


def test_attribution_80_percent_boundary():
    assert config.CHILD_SHARE == 0.8
    r = eff(20, 5)                       # exactly 80 %
    assert (r["ticket_eff"], r["ticket_eff_via"], r["eff_children"], r["eff_share_n"]) == ("PROJ-2", "children", 25, 20)
    r = eff(19, 5)                       # 79.2 %
    assert (r["ticket_eff"], r["ticket_eff_via"]) == ("PROJ-1", "own")


def test_attribution_no_keyed_children_keeps_own_key():
    assert eff(0, 0)["ticket_eff"] == "PROJ-1"
    r = eff(0, 0, extra=[row("u", "sub", None)])
    assert (r["ticket_eff"], r["ticket_eff_via"], r["eff_children"]) == ("PROJ-1", "own", 0)


def test_attribution_sub_runs_keep_their_key_and_other_sessions_are_not_counted():
    rows = {"S1": row("S1", "main", None), "x": row("x", "sub", "PROJ-5"), "S2": row("S2", "main", "PROJ-7", "S2"), "y": row("y", "sub", "PROJ-8", "S2")}
    tickets.effective_tickets(rows)
    assert rows["x"]["ticket_eff"] == "PROJ-5" and rows["x"]["ticket_eff_via"] == "own"
    assert rows["S1"]["ticket_eff"] == "PROJ-5" and rows["S1"]["ticket_eff_via"] == "children"      # a main session with no own key
    assert rows["S2"]["ticket_eff"] == "PROJ-8"


def test_attribution_end_to_end_moves_the_session(env):
    spawns = [TU(f"sp{i}", "Agent", subagent_type="builder", description=f"[OPS1-PILOT] step {i}", prompt="p") for i in range(3)]
    main_file(env, [P(0, "human"), A("m1", 5, spawns, stop="tool_use"), A("m2", 6)])
    for i in range(3):
        add_sub(env.root, "S1", f"a{i}", "builder", [A(f"s{i}", 10 + i, agent=f"a{i}")], f"sp{i}")
    s = Store()
    s.ingest()
    r = {x["run_id"]: x for x in q(s, "SELECT run_id, ticket, ticket_eff, ticket_eff_via, eff_children, eff_share_n FROM runs")}
    assert r["S1"]["ticket_eff"] == "OPS1-PILOT" and r["S1"]["ticket_eff_via"] == "children" and (r["S1"]["eff_children"], r["S1"]["eff_share_n"]) == (3, 3)
    assert r["S1:a0"]["ticket_eff"] == "OPS1-PILOT" and r["S1:a0"]["ticket_eff_via"] == "own"


def test_sub_agent_user_records_are_not_waits(env):
    main_file(env, [P(0, "human"), A("m1", 5, [TU("sp", "Agent", subagent_type="builder", description="d", prompt="p")], stop="tool_use")])
    add_sub(env.root, "S1", "a1", "builder", [P(10, session="S1"), A("s1", 20, agent="a1"), P(500, session="S1"), A("s2", 520, agent="a1")], "sp")
    s = Store()
    s.ingest()
    assert q(s, "SELECT * FROM waits") == [] and q(s, "SELECT * FROM gaps") == []
