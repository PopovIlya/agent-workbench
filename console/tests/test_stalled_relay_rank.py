"""Stalled runs, relay share, and the pieces the pages rely on: rank within the role, the handoff rule, the session-mode threshold, filters."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from agent_console import config, ctq, server
from agent_console.ctq_pages import rank_within_role
from agent_console.pricing import Pricing
from agent_console.store import Store
from ctq_fixtures import A, P, R, TU, add_sub, main_file, q


# ---------------- stalled ----------------
def sub_run(env, records, spawn=None):
    spawn = spawn or TU("sp", "Agent", subagent_type="builder", description="[PROJ-5] x", prompt="p")
    main_file(env, [P(0, "human"), A("m1", 5, [spawn], stop="tool_use")])
    add_sub(env.root, "S1", "a1", "builder", records, spawn["id"])
    s = Store()
    s.ingest()
    return s


def stalled_flag(s):
    return q(s, "SELECT * FROM flags WHERE run_id='S1:a1' AND flag='stalled'")


def test_stalled_threshold_is_1200_seconds(env):
    assert config.STALLED_AFTER_S == 1200
    for gap, expect in ((1199, False), (1201, True)):
        (env.home / "index.sqlite").unlink(missing_ok=True)
        s = sub_run(env, [A("s1", 10, agent="a1"), A("s2", 10 + gap, agent="a1")])       # silence before an answer
        assert bool(stalled_flag(s)) is expect, gap
        r = q(s, "SELECT stalled_s, model_s FROM runs WHERE run_id='S1:a1'")[0]
        assert (round(r["stalled_s"]), round(r["model_s"])) == ((gap, 0) if expect else (0, gap))   # a stall is not model time


def test_a_stalled_tool_call_is_flagged_but_not_counted_twice(env):
    s = sub_run(env, [A("s1", 10, [TU("t1", "Bash", command="ls")], agent="a1", stop="tool_use"), R("t1", 10 + 1500), A("s2", 10 + 1501, agent="a1")])
    e = json.loads(stalled_flag(s)[0]["evidence"])
    assert e["count"] == 1 and e["longest_s"] == 1500 and e["items"][0]["ended_by"] == "result"
    r = q(s, "SELECT stalled_s, blocked_s FROM runs WHERE run_id='S1:a1'")[0]
    assert r["stalled_s"] == 0 and round(r["blocked_s"]) == 1500       # the time stays in "blocked"; only the flag is new


def test_a_long_test_call_is_not_a_stall(env):
    s = sub_run(env, [A("s1", 10, [TU("t1", "Bash", command="poetry run pytest -q")], agent="a1", stop="tool_use"), R("t1", 10 + 3000), A("s2", 10 + 3001, agent="a1")])
    assert not stalled_flag(s)


def test_background_waits_and_child_runs_are_not_stalls(env):
    bg = [A("s1", 10, [TU("t1", "Bash", command="sleep 5", run_in_background=True)], agent="a1", stop="tool_use"), R("t1", 11), P(3011, "task-notification"), A("s2", 3012, agent="a1")]
    assert not stalled_flag(sub_run(env, bg))
    (env.home / "index.sqlite").unlink()
    child = [A("s1", 10, [TU("t2", "Agent", subagent_type="x", description="d", prompt="p")], agent="a1", stop="tool_use"), R("t2", 10 + 3000), A("s2", 10 + 3001, agent="a1")]
    assert not stalled_flag(sub_run(env, child))


def test_only_sub_agent_runs_can_stall(env):
    main_file(env, [P(0, "human"), A("m1", 5), A("m2", 5 + 5000)])
    s = Store()
    s.ingest()
    assert q(s, "SELECT * FROM flags WHERE flag='stalled'") == []


def test_stalled_is_listed_for_a_person_and_explained(env):
    s = sub_run(env, [A("s1", 10, agent="a1"), A("s2", 5000, agent="a1")])
    api = TestClient(server.create_app(store=s, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")
    n = api.get("/api/ctq/overview").json()["needs_person"]
    assert [x["flag"] for x in n["items"]] == ["stalled"] and n["items"][0]["evidence"]["longest_s"] == 4990
    d = api.get("/api/runs/S1:a1").json()
    assert d["stalled_s"] == pytest.approx(4990, abs=1) and any("silent" in f for f in d["findings"])


# ---------------- relay share: lengths only ----------------
def test_relay_share_is_built_from_lengths_and_no_text_is_stored(env):
    brief, report, typed = "BRIEF-" + "x" * 94, "REPORT-" + "y" * 193, "TYPED-" + "z" * 44
    spawn = TU("sp", "Agent", subagent_type="builder", description="[PROJ-5] d", prompt=brief)
    main_file(env, [P(0, "human", text=typed), A("m1", 5, [spawn, TU("rd", "Read", file_path="/r/a.py")], stop="tool_use"), R("sp", 60, text=report), R("rd", 61, text="q" * 100)])
    s = Store()
    s.ingest()
    r = q(s, "SELECT relay_chars, total_chars, prompt_chars FROM runs WHERE run_id='S1'")[0]
    relay_in = q(s, "SELECT in_chars FROM tool_calls WHERE id='sp'")[0]["in_chars"]
    assert relay_in > len(brief) and r["relay_chars"] == relay_in + len(report) and r["prompt_chars"] == len(typed)
    other = q(s, "SELECT in_chars + out_chars t FROM tool_calls WHERE id='rd'")[0]["t"]
    assert r["total_chars"] == r["relay_chars"] + other + len(typed) + q(s, "SELECT sum(text_chars) t FROM messages")[0]["t"] and 0 < r["relay_chars"] < r["total_chars"]
    db = sqlite3.connect(s.db_path)
    db.execute("PRAGMA wal_checkpoint(FULL)")
    raw = s.db_path.read_bytes() + (s.db_path.with_name(s.db_path.name + "-wal").read_bytes() if s.db_path.with_name(s.db_path.name + "-wal").exists() else b"")
    for needle in (b"BRIEF-", b"REPORT-", b"TYPED-", b"xxxxxxxx", b"yyyyyyyy"):
        assert needle not in raw, needle
    api = TestClient(server.create_app(store=s, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")
    row = api.get("/api/ctq/sessions").json()["rows"][0]
    assert row["relay_share"] == pytest.approx(r["relay_chars"] / r["total_chars"]) and row["relay_chars"] == r["relay_chars"]
    assert row["handback_chars"] == len(report) and row["handback_share"] == pytest.approx(len(report) / r["total_chars"])      # hand-backs only: the report that came back


# ---------------- rank within the role ----------------
def test_rank_within_role_ties_count_half():
    runs = [{"run_id": f"a{i}", "role": "builder", "S": v} for i, v in enumerate([0.2, 0.4, 0.4, 0.8])] + [{"run_id": "z", "role": "lone", "S": 0.1}]
    rk = rank_within_role(runs)
    assert rk["a0"] == 0.0 and rk["a3"] == 1.0                              # lowest / highest of the role
    assert rk["a1"] == rk["a2"] == pytest.approx((1 + 0.5) / 3)             # one run lower, one tie counted half, of the 3 others
    assert rk["z"] == 0.5                                                  # a role with one run: nobody to compare with
    two = rank_within_role([{"run_id": "p", "role": "r", "S": 0.5}, {"run_id": "q", "role": "r", "S": 0.5}])
    assert two == {"p": 0.5, "q": 0.5}                                      # all equal: a usual run


# ---------------- handoff rule ----------------
def run(rid, role, a, b, rework=False):
    return {"run_id": rid, "role": role, "start_e": a, "end_e": b, "start_ts": "t", "rework": rework, "S": None, "kind": "sub"}


def test_handoff_predecessor_is_the_latest_run_that_ended_no_later_than_one_second_after_the_start():
    runs = [run("a", "business-analyst", 0, 10), run("b", "system-analyst", 0, 30), run("c", "qa-analyst", 31, 40), run("d", "qa-analyst", 40.9, 50)]
    h = {x["run_id"]: x for x in ctq.handoffs(runs)}
    assert h["a"]["from_role"] is None and h["a"]["parallel"] and h["b"]["parallel"]
    assert h["c"]["from_role"] == "system-analyst"                  # b ended last (30), a ended at 10
    assert h["d"]["from_role"] == "qa-analyst" and h["d"]["how"] == "same role again"    # c ended at 40, within 1 s of d's start (40.9)
    assert ctq.handoffs([run("x", "a", 0, 10), run("y", "b", 8.9, 20)])[1]["pred_index"] == -1         # x ended 1.1 s after y started: not a predecessor
    assert ctq.handoffs([run("x", "a", 0, 10), run("y", "b", 9.5, 20)])[1]["pred_index"] == 0          # 0.5 s after: still a predecessor


def test_sent_back_needs_a_gate_predecessor_and_a_rework_run():
    base = [run("w", "builder", 0, 10), run("g", "reviewer", 11, 20), run("r", "builder", 21, 30, rework=True)]
    assert ctq.handoffs(base)[2]["sent_back"] is True and ctq.handoffs(base)[2]["how"] == "sent back by the gate"
    not_rework = [base[0], base[1], run("r", "builder", 21, 30)]
    assert ctq.handoffs(not_rework)[2]["sent_back"] is False
    not_gate = [base[0], run("g", "test-designer", 11, 20), run("r", "builder", 21, 30, rework=True)]
    assert ctq.handoffs(not_gate)[2]["sent_back"] is False


# ---------------- session mode ----------------
def test_session_mode_threshold_is_three_different_roles():
    assert config.SHARED_SESSION_ROLES == 3
    def runs(roles, session="S1"):
        return [{"run_id": f"{session}:{i}", "kind": "sub", "role": r, "session_id": session} for i, r in enumerate(roles)] + [{"run_id": session, "kind": "main", "role": "main", "session_id": session}]
    two = ctq.session_modes(runs(["builder", "reviewer", "builder"]))
    three = ctq.session_modes(runs(["builder", "reviewer", "lead-qa"]))
    assert set(two.values()) == {"own"} and {v for k, v in three.items() if ":" in k} == {"shared"} and three["S1"] == "own"      # the main session itself is never "shared"


# ---------------- filters, on the server, for every page ----------------
M = 1_000_000


@pytest.fixture
def two_tickets(env):
    spawns = [TU(f"sp{i}", "Agent", subagent_type="builder", description="[OPS1-PILOT] s", prompt="p") for i in range(2)]
    main_file(env, [P(0, "human"), A("m1", 100, spawns, stop="tool_use", inp=M)])
    for i in range(2):
        add_sub(env.root, "S1", f"a{i}", "builder", [A(f"s{i}", 200 + i, agent=f"a{i}", inp=M)], f"sp{i}")
    main_file(env, [P(500, "human", session="S2", text="[PROJ-77] work"), A("n1", 510, session="S2", inp=M)], session="S2")
    st = Store()
    st.ingest()
    return TestClient(server.create_app(store=st, pricing=Pricing({"regional_multiplier": 1.0, "models": {"sonnet-5-5": {"input": 1.0, "output": 1.0, "cache_read": 1.0, "cache_write_5m": 1.0, "cache_write_1h": 1.0}}}), port=8790),
                      base_url="http://127.0.0.1:8790")


def test_project_and_ticket_filters_apply_to_every_endpoint(two_tickets):
    api = two_tickets
    base = api.get("/api/ctq/overview").json()["kpis"]
    assert base["tickets"] == 2 and base["runs"] == 4
    for params, tickets, runs in (({"proj": "PROJ"}, 1, 1), ({"proj": "OPS1"}, 1, 3), ({"q": "pilot"}, 1, 3), ({"q": "77"}, 1, 1), ({"proj": "PROJ", "q": "pilot"}, 0, 0)):
        k = api.get("/api/ctq/overview", params=params).json()["kpis"]
        assert (k["tickets"], k["runs"]) == (tickets, runs), params
        assert api.get("/api/ctq/tickets", params=params).json()["total"] == tickets
        assert sum(r["runs"] for r in api.get("/api/ctq/roles", params=params).json()["rows"]) == runs
        assert len(api.get("/api/ctq/sessions", params=params).json()["rows"]) == tickets          # one main session per ticket here
    assert api.get("/api/ctq/roles/builder", params={"proj": "PROJ"}).json().get("empty") is True


def test_filter_lists_carry_counts_and_the_server_limits_the_keys(two_tickets):
    f = two_tickets.get("/api/ctq/filters").json()
    assert {p["name"]: p["runs"] for p in f["projects"]} == {"OPS1": 3, "PROJ": 1}
    assert two_tickets.get("/api/ctq/filters", params={"proj": "PROJ"}).json()["keys"] == ["PROJ-77"]
