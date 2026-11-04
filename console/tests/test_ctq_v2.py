"""The console side of agent score v2: the role-page controls, "too few runs to call a change", the verdict panel, the markers, verdict / defect on the ticket page."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from agent_console import ctq_pages as pages
from agent_console import events, gold, server
from agent_console.ctq import Period
from agent_console.pricing import Pricing
from agent_console.store import Store
from ctq_fixtures import A, P, TU, add_sub, main_file


def line(tid, role, ticket, rnd, s, **kw):
    base = {"scorer_version": 2, "task_id": tid, "rev": 5, "role": role, "ticket_eff": ticket, "ticket": ticket, "S": s, "S_partial": s, "scored": s is not None, "round": rnd, "step": f"step {rnd}",
            "input_tokens": 1000 * rnd, "model": "claude-sonnet-5-5", "role_file_sha": "abc1234", "coverage": 0.65, "too_little_evidence": s is None, "gate": {"delivered": True},
            "criteria": {"first_pass": {"c": 1.0 if rnd == 1 else 0.5, "w": 0.25}, "follows": {"c": 1.0, "w": 0.1}}, "flags": [], "hard_limit": None}
    base.update(kw)
    return base


@pytest.fixture
def api(env):
    # two tickets; builder runs: PROJ-1 round 1, PROJ-1 round 2 (rework), PROJ-2 round 1
    spawns = [TU("sp1", "Agent", subagent_type="builder", description="[PROJ-1] build", prompt="p"), TU("sp2", "Agent", subagent_type="builder", description="[PROJ-1] fix", prompt="p"),
              TU("sp3", "Agent", subagent_type="builder", description="[PROJ-2] build", prompt="p")]
    main_file(env, [P(0, "human"), A("m1", 5, spawns, stop="tool_use")])
    for i, sp in enumerate(("sp1", "sp2", "sp3")):
        add_sub(env.root, "S1", f"a{i}", "builder", [A(f"s{i}", 100 + 100 * i, agent=f"a{i}")], sp)
    st = Store()
    st.ingest()
    env.home.mkdir(parents=True, exist_ok=True)
    rows = [line("S1:a0", "builder", "PROJ-1", 1, 0.9), line("S1:a1", "builder", "PROJ-1", 2, 0.5), line("S1:a2", "builder", "PROJ-2", 1, None, S_partial=0.7)]
    (env.home / "scores.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    return TestClient(server.create_app(store=st, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")


def test_first_passes_only_and_same_ticket_controls(api):
    full = api.get("/api/ctq/roles/builder").json()
    assert [h["round"] for h in full["history"]] == [1, 2, 1] and full["row"]["n_S"] == 2 and full["row"]["n_eval"] == 3 and full["row"]["n_too_little"] == 1
    first = api.get("/api/ctq/roles/builder", params={"first_only": "true"}).json()
    assert [h["round"] for h in first["history"]] == [1, 1] and first["controls"]["n_all"] == 3 and first["controls"]["n_shown"] == 2
    same = api.get("/api/ctq/roles/builder", params={"ticket": "PROJ-1"}).json()
    assert {h["ticket"] for h in same["history"]} == {"PROJ-1"} and len(same["history"]) == 2 and same["controls"]["tickets"] == ["PROJ-1", "PROJ-2"]
    both = api.get("/api/ctq/roles/builder", params={"ticket": "PROJ-1", "first_only": "true"}).json()
    assert [h["step"] for h in both["history"]] == ["step 1"]


def test_a_too_little_evidence_run_stays_in_the_history_as_a_point_without_s(api):
    h = api.get("/api/ctq/roles/builder").json()["history"]
    tl = [x for x in h if x["too_little"]]
    assert len(h) == 3 and len(tl) == 1 and tl[0]["S"] is None and tl[0]["S_partial"] == 0.7 and tl[0]["rank"] is None and tl[0]["coverage"] == 0.65
    assert all(x["rank"] is not None and not x["too_little"] for x in h if x["S"] is not None)
    assert api.get("/api/ctq/roles").json()["history"][-1]["too_little"] is True


def test_skipped_runs_are_visible_on_the_role_page_with_the_reason_and_counted_per_role(api, env):
    skip = {"scorer_version": 2, "task_id": "S1:a2", "rev": 6, "role": "builder", "ticket_eff": "PROJ-2", "ticket": "PROJ-2", "S": None, "scored": False, "skipped": "probe run: a setup test, not the role's work",
            "skip_kind": "probe", "criteria": {}, "checks": {}, "flags": [], "coverage": 0.0}
    with open(env.home / "scores.jsonl", "a") as fh:
        fh.write(json.dumps(skip) + "\n")
    d = api.get("/api/ctq/roles/builder").json()
    assert d["row"]["n_skipped"] == 1 and d["row"]["skipped"] == {"probe": 1}
    assert [(x["ticket"], x["kind"], x["label"]) for x in d["skipped_runs"]] == [("PROJ-2", "probe", "probe")] and "setup test" in d["skipped_runs"][0]["reason"]
    assert [r for r in api.get("/api/ctq/roles").json()["rows"] if r["role"] == "builder"][0]["n_skipped"] == 1
    assert all(h["run_id"] != "S1:a2" for h in d["history"])          # a skipped run has no check data, so it is not a history point
    run = api.get("/api/runs/" + d["skipped_runs"][0]["run_id"]).json()
    assert run["scores"][-1]["skip_kind"] == "probe"
    api_err = dict(skip, rev=7, skip_kind="api_error", skipped="run ended on an API error (environment, not the role)")
    with open(env.home / "scores.jsonl", "a") as fh:
        fh.write(json.dumps(api_err) + "\n")
    d = api.get("/api/ctq/roles/builder").json()
    assert d["row"]["skipped"] == {"api_error": 1} and d["skipped_runs"][0]["label"] == "ended by API error"


def test_each_dot_carries_step_round_and_input_tokens(api):
    h = api.get("/api/ctq/roles/builder").json()["history"][1]
    assert (h["step"], h["round"], h["input_tokens"], h["model"], h["role_file_sha"], h["scorer_version"]) == ("step 2", 2, 2000, "claude-sonnet-5-5", "abc1234", 2)


def test_a_run_with_too_little_evidence_has_no_s_but_still_counts_as_evaluated(api):
    row = [r for r in api.get("/api/ctq/roles").json()["rows"] if r["role"] == "builder"][0]
    assert row["n_S"] == 2 and row["n_eval"] == 3 and row["delivered"] == [3, 3] and row["pass"]["first_pass"] == [2, 3] and row["pass"]["follows"] == [3, 3]
    assert row["mean"]["first_pass"] == pytest.approx((1 + 0.5 + 1) / 3) and row["empty_share"]["judge"] == 1.0 and row["distinct_S"] == 2


# ---------------- what stands out: a change is a change only with 10 runs on each side
def hist(n, s_first, s_last, ticket="PROJ-1"):
    return [{"S": s_first if i < n // 2 else s_last, "criteria": {"first_pass": 1.0 if i >= n // 2 else 0.0, "follows": 1.0}, "ticket": ticket, "rework": False, "round": 1, "scorer_version": 2}
            for i in range(n)]


def stats(h):
    ks = ("first_pass", "outcome", "judge", "follows", "grounded")
    return {"pass": {k: ([sum(1 for x in h if (x["criteria"].get(k) or 0) >= 1), len(h)] if k in h[0]["criteria"] else None) for k in ks}, "mean": {k: 0.5 for k in ks}}


def test_a_change_needs_ten_runs_on_each_side():
    few = pages.role_findings(stats(hist(12, 0.4, 0.8)), hist(12, 0.4, 0.8))
    assert any("Too few scored runs to call a change" in f for f in few) and not any("The change comes from" in f for f in few)
    enough = pages.role_findings(stats(hist(24, 0.4, 0.8)), hist(24, 0.4, 0.8))
    assert any("The change comes from" in f and "first_pass" in f for f in enough) and not any("Too few scored runs" in f for f in enough)


def test_one_ticket_ceiling_and_discreteness_findings():
    h = hist(9, 0.5, 0.5)
    for x in h:
        x["criteria"]["first_pass"] = 0.0
    st = {"pass": {"first_pass": [0, 9], "follows": [9, 9], "outcome": None, "judge": None, "grounded": None}, "mean": {"first_pass": 0.0, "follows": 1.0, "outcome": None, "judge": None, "grounded": None}}
    f = pages.role_findings(st, h)
    assert any("All 9 scored runs are on one ticket" in x for x in f) and any("\"first_pass\" never passed, so S cannot exceed" in x for x in f)


# ---------------- the verdict panel
def fake_ctx(n_tickets, s_for, verdicts_for):
    runs = {f"r{i}": {"S": s_for(i), "key": f"PROJ-{i}", "kind": "sub"} for i in range(n_tickets)}
    return SimpleNamespace(d=SimpleNamespace(runs=runs)), {f"PROJ-{i}": {"verdict": verdicts_for(i)} for i in range(n_tickets)}


def test_the_verdict_panel_appears_at_twenty_tickets_and_compares_s_with_the_verdict(monkeypatch):
    c, v = fake_ctx(19, lambda i: 0.9 if i % 2 == 0 else 0.3, lambda i: "accepted" if i % 2 == 0 else "rejected")
    monkeypatch.setattr(gold, "latest_verdicts", lambda: v)
    p = pages.verdict_panel(c)
    assert p["n"] == 19 and p["shown"] is False
    c, v = fake_ctx(20, lambda i: 0.9 if i % 2 == 0 else 0.3, lambda i: "accepted" if i % 2 == 0 else "rejected")
    monkeypatch.setattr(gold, "latest_verdicts", lambda: v)
    p = pages.verdict_panel(c)
    assert p["shown"] is True and p["mean_S"]["accepted"] == pytest.approx(0.9) and p["mean_S"]["rejected"] == pytest.approx(0.3) and p["agree_share"] == 1.0
    c, v = fake_ctx(20, lambda i: 0.9, lambda i: "accepted" if i < 10 else "rejected")           # S says good for all, the person rejected half
    monkeypatch.setattr(gold, "latest_verdicts", lambda: v)
    assert pages.verdict_panel(c)["agree_share"] == pytest.approx(0.5)


# ---------------- the markers
def ctx_for(role, hist_):
    return events.EventCtx(role, Period(0, 9e9), hist_)


def test_markers_for_a_scorer_version_change_and_a_role_file_change():
    h = [{"start": "2026-10-20T10:00:00Z", "scorer_version": 1, "role_file_sha": "aaa1111"}, {"start": "2026-10-21T10:00:00Z", "scorer_version": 2, "role_file_sha": "aaa1111"},
         {"start": "2026-10-22T10:00:00Z", "scorer_version": 2, "role_file_sha": "bbb2222"}, {"start": "2026-10-23T10:00:00Z", "scorer_version": 2, "role_file_sha": None}]
    sv = events.scorer_version_change(ctx_for("builder", h))
    assert len(sv) == 1 and sv[0]["ts"] == "2026-10-21T10:00:00Z" and "not a change in the agent" in sv[0]["detail"]
    rf = events.role_file_change(ctx_for("builder", h))
    assert len(rf) == 1 and rf[0]["detail"] == "role file aaa1111 → bbb2222"


def test_benchmark_results_are_markers_with_pass_pow_k(env):
    gold.append("bench.jsonl", {"role": "builder", "ts": "2026-10-22T12:00:00+00:00", "tasks": 20, "k": 3, "pass_at_k": 0.9, "pass_pow_k": 0.65})
    gold.append("bench.jsonl", {"role": "reviewer", "ts": "2026-10-22T12:00:00+00:00", "tasks": 5, "k": 3, "pass_at_k": 1.0, "pass_pow_k": 1.0})
    gold.append("bench.jsonl", {"role": "builder", "ts": "2026-10-23T12:00:00+00:00", "dry_run": True, "tasks": 3, "k": 3})
    ev = events.bench_results(ctx_for("builder", []))
    assert len(ev) == 1 and ev[0]["kind"] == "benchmark" and "pass^k 65%" in ev[0]["detail"] and ev[0]["label"] == "bench 65%"


# ---------------- the ticket page
def test_the_ticket_page_carries_the_verdict_and_the_defect_reports(api):
    t = api.get("/api/ctq/tickets/PROJ-1").json()
    assert t["verdict"] is None and t["defects"] == []
    api.post("/api/verdict", json={"ticket": "PROJ-1", "verdict": "accepted_after_rework", "note": "two rounds", "roles": ["builder"]})
    api.post("/api/defect", json={"ticket": "PROJ-1", "date": "2026-11-02", "roles": ["reviewer"], "note": "found in beta"})
    t = api.get("/api/ctq/tickets/PROJ-1").json()
    assert t["verdict"]["verdict"] == "accepted_after_rework" and t["verdict"]["roles"] == ["builder"] and t["defects"][0]["roles"] == ["reviewer"]


def test_deception_items_in_needs_a_person_can_be_decided(api, env):
    rows = [line("S1:a0", "builder", "PROJ-1", 1, 0.5, flags=["deception"], flag_evidence={"deception": {"suspected": True, "reasons": []}})]
    (env.home / "scores.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    items = api.get("/api/ctq/overview").json()["needs_person"]["items"]
    assert [(x["flag"], x["decidable"]) for x in items] == [("deception", True)]
    api.post("/api/flags/decide", json={"run_id": "S1:a0", "flag": "deception", "decision": "confirm"})
    assert api.get("/api/ctq/overview").json()["needs_person"]["items"] == []


def test_meta_reports_the_judge_off_by_default(api):
    j = api.get("/api/ctq/meta").json()["judge"]
    assert j["on"] is False and j["weight_active"] is False and j["needs_n"] == 30 and j["needs_kappa"] == 0.6
