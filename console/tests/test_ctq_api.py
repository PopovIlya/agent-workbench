"""/api/ctq/*: shapes, main-session attribution, period clipping, bucket rule, and that the KPIs are the sums of the table rows."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from agent_console import server
from agent_console.pricing import Pricing
from agent_console.store import Store
from ctq_fixtures import A, P, TU, add_sub, at, main_file

M = 1_000_000          # 1M input tokens = $1 with the test price table below
PRICES = Pricing({"regional_multiplier": 1.0, "models": {"sonnet-5-5": {"input": 1.0, "output": 1.0, "cache_read": 1.0, "cache_write_5m": 1.0, "cache_write_1h": 1.0}}})


def money(x):
    return pytest.approx(x, abs=0.01)      # each fixture message also carries a few output / cache tokens


def iso(sec):
    return at(sec)


@pytest.fixture
def api(env):
    """S1: a main session with no key of its own that spawns three builders for OPS1-PILOT. S2: a keyed main session ([PROJ-77])."""
    spawns = [TU(f"sp{i}", "Agent", subagent_type="builder", description=f"[OPS1-PILOT] step {i}", prompt="p") for i in range(3)]
    main_file(env, [P(0, "human"), A("m1", 100, spawns, stop="tool_use", inp=M), P(3650, "human"), A("m2", 3700, inp=M), A("m3", 7300, inp=M)])
    for i in range(3):
        add_sub(env.root, "S1", f"a{i}", "builder", [A(f"s{i}a", 200 + i, agent=f"a{i}", inp=M), A(f"s{i}b", 260 + i, agent=f"a{i}", inp=M)], f"sp{i}")
    main_file(env, [P(500, "human", session="S2", text="[PROJ-77] work on it"), A("n1", 510, session="S2", inp=M), A("n2", 600, session="S2", inp=M)], session="S2")
    store = Store()
    store.ingest()
    return TestClient(server.create_app(store=store, pricing=PRICES, port=8790), base_url="http://127.0.0.1:8790")


def get(api, path, **p):
    r = api.get(path, params=p)
    assert r.status_code == 200, r.text
    return r.json()


FROM, TO = iso(0), iso(20000)


def test_shapes(api):
    o = get(api, "/api/ctq/overview", **{"from": FROM, "to": TO})
    assert {"period", "kpis", "needs_person", "cost_by_ticket", "time_by_ticket", "series", "cost_by_token_type", "top_sessions", "findings"} <= set(o)
    assert {"spend", "main_share", "working_s", "waiting_s", "parked_s", "test_s", "test_n", "test_fail", "test_timeouts", "S", "n_S", "delivered", "n_evaluated", "n_too_little"} <= set(o["kpis"])
    assert {"unit", "buckets"} == set(o["series"]) and {"start", "label", "cost_main", "cost_sub", "working_s", "waiting_s", "parked_s", "S", "n_S"} <= set(o["series"]["buckets"][0])
    t = get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO})
    assert {"total", "rows", "findings", "period"} <= set(t)
    assert {"ticket", "cost", "cost_main", "cost_sub", "first", "last", "calendar_s", "working_s", "waiting_s", "parked_s", "blocked_s", "test_s", "test_n", "test_fail",
            "test_timeouts", "runs", "roles", "S", "n_S", "flags", "badges"} <= set(t["rows"][0])
    d = get(api, "/api/ctq/tickets/OPS1-PILOT", **{"from": FROM, "to": TO})
    assert {"row", "handoffs", "agents_by_role", "runs", "waits", "tests", "by_role", "findings"} <= set(d)
    assert {"n", "run_id", "from_role", "to_role", "pred_index", "parallel", "sent_back"} <= set(d["handoffs"][0])
    assert {"role", "agents", "sessions", "shared", "rework", "max_parallel", "cost", "run_time_s", "S"} <= set(d["agents_by_role"][0])
    r = get(api, "/api/ctq/roles", **{"from": FROM, "to": TO})
    assert {"rows", "history", "session_mode", "stages", "findings"} <= set(r)
    assert {"role", "runs", "tickets", "cost", "median_cost_per_run", "median_run_time_s", "test_s", "test_n", "S", "n_S", "pass", "flags_per_run", "pipeline_role"} <= set(r["rows"][0])
    rd = get(api, "/api/ctq/roles/builder", **{"from": FROM, "to": TO})
    assert {"row", "history", "series", "events", "findings"} <= set(rd)
    s = get(api, "/api/ctq/sessions", **{"from": FROM, "to": TO})
    assert {"ticket", "own_ticket", "start", "length_s", "calls", "cost", "cost_per_call", "context_per_call", "waiting_s", "parked_s", "blocked_s", "sub_agents"} <= set(s["rows"][0])


def test_ticket_eff_moves_the_right_session(api):
    rows = {r["ticket"]: r for r in get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO})["rows"]}
    assert set(rows) == {"OPS1-PILOT", "PROJ-77"}                       # no "(no ticket)" row: S1 moved to OPS1-PILOT
    p = rows["OPS1-PILOT"]
    assert p["cost_main"] == money(3.0) and p["cost_sub"] == money(6.0) and p["cost"] == money(9.0) and p["runs"] == 4
    assert p["badges"]["moved_main"] == [{"run_id": "S1", "own_key": "(no ticket)", "children": 3, "share_n": 3}]
    assert rows["PROJ-77"]["cost"] == money(2.0) and not rows["PROJ-77"]["badges"]["moved_main"]


def test_period_clips_cost_time_and_counts_runs_by_start(api):
    lo, hi = iso(3000), iso(8000)
    rows = {r["ticket"]: r for r in get(api, "/api/ctq/tickets", **{"from": lo, "to": hi})["rows"]}
    assert set(rows) == {"OPS1-PILOT"}                               # PROJ-77 and the builders ended before the period
    p = rows["OPS1-PILOT"]
    assert p["runs"] == 1 and p["cost"] == money(2.0)         # only m2 (3700) and m3 (7300) fall inside
    # the main session is open 3000..7300; the human wait 100..3650 is clipped to 3000..3650
    assert p["waiting_s"] == pytest.approx(650, abs=1) and p["working_s"] == pytest.approx(4300 - 650, abs=1) and p["calendar_s"] == pytest.approx(4300, abs=1)


def test_a_run_that_crosses_the_boundary_counts_its_inside_messages_only(api):
    # S1 started at 0 (before the period), so it contributes no S / flags there, but its messages in the period are paid for
    o = get(api, "/api/ctq/overview", **{"from": iso(3000), "to": iso(8000)})
    assert o["kpis"]["spend"] == money(2.0) and o["kpis"]["n_S"] == 0


def span_buckets(api, secs, unit):
    lo = datetime(2026, 10, 20, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    o = get(api, "/api/ctq/overview", **{"from": lo.isoformat(), "to": (lo + timedelta(seconds=secs)).isoformat()})
    assert o["series"]["unit"] == unit
    return o["series"]["buckets"]


def test_bucket_rule_and_empty_buckets_are_returned(api):
    b = span_buckets(api, 2 * 86400, "hour")
    assert len(b) == 48 and all(x["cost_main"] >= 0 for x in b)
    assert sum(x["cost_main"] + x["cost_sub"] for x in b) == money(11.0)    # every dollar lands in exactly one bucket (S1 3 + subs 6 + S2 2)
    assert sum(1 for x in b if x["cost_main"] + x["cost_sub"] == 0) >= 40            # the empty hours are there
    assert len(span_buckets(api, 2 * 86400 + 1, "day")) == 3
    assert len(span_buckets(api, 62 * 86400, "day")) == 62
    assert len(span_buckets(api, 63 * 86400, "week")) == 10


def test_kpis_equal_the_sum_of_the_rows(api):
    o = get(api, "/api/ctq/overview", **{"from": FROM, "to": TO})
    rows = get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO})["rows"]
    k = o["kpis"]
    for kpi, col in (("spend", "cost"), ("working_s", "working_s"), ("waiting_s", "waiting_s"), ("parked_s", "parked_s"), ("test_n", "test_n")):
        assert k[kpi] == pytest.approx(sum(r[col] for r in rows)), kpi
    assert sum(b["cost_main"] + b["cost_sub"] for b in o["series"]["buckets"]) == pytest.approx(k["spend"])
    assert sum(o["cost_by_token_type"].values()) == pytest.approx(k["spend"])
    assert k["main_share"] == pytest.approx(sum(r["cost_main"] for r in rows) / k["spend"])


def test_filters_project_and_ticket_text(api):
    t = get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO, "proj": "PROJ"})
    assert [r["ticket"] for r in t["rows"]] == ["PROJ-77"]
    t = get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO, "q": "pilot"})
    assert [r["ticket"] for r in t["rows"]] == ["OPS1-PILOT"]
    f = get(api, "/api/ctq/filters", **{"from": FROM, "to": TO})
    assert {p["name"]: p["runs"] for p in f["projects"]} == {"OPS1": 4, "PROJ": 1} and set(f["keys"]) == {"OPS1-PILOT", "PROJ-77"}


def test_limit_and_sort_on_the_server(api):
    t = get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO, "limit": 1, "sort": "cost", "desc": "true"})
    assert t["total"] == 2 and [r["ticket"] for r in t["rows"]] == ["OPS1-PILOT"]
    t = get(api, "/api/ctq/tickets", **{"from": FROM, "to": TO, "limit": 1, "sort": "cost", "desc": "false"})
    assert [r["ticket"] for r in t["rows"]] == ["PROJ-77"]


def test_bad_period_and_scope_are_refused(api):
    assert api.get("/api/ctq/overview", params={"from": "nonsense"}).status_code == 422
    assert api.get("/api/ctq/overview", params={"scope": "x"}).status_code == 422


def test_handoffs_order_and_parallel(api):
    h = get(api, "/api/ctq/tickets/OPS1-PILOT", **{"from": FROM, "to": TO})["handoffs"]
    assert [x["n"] for x in h] == [1, 2, 3] and all(x["parallel"] for x in h) and h[0]["from_role"] is None     # the three builders ran at once
