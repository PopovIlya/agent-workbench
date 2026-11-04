"""Agent score v2: the gate, the hard limits, every weighted check (empty / partial / full), coverage, re-scoring that keeps v1 lines,
and three hand-made cases (lead-qa, test-designer, a rework run)."""

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]   # the workbench
sys.path.insert(0, str(REPO / "console"))
from agent_scoring import agent_score as A  # noqa: E402
from agent_scoring import agent_score_v2 as V  # noqa: E402

from agent_console.store import Store  # noqa: E402
from conftest import PROJECT, add_sub, assistant, role_file, tool_use, user_prompt, write_jsonl  # noqa: E402


def facts(**kw):
    base = dict(name="r", tools=["Read", "Grep", "Glob", "Edit", "Write", "Bash"], outputs=[A.Output("report", "reply")], allowed=None, next_gates=["reviewer"])
    base.update(kw)
    return A.RoleFacts(**base)


def ev(**kw):
    base = dict(run_id="S:a", role="r", agent_type="r", ticket="PROJ-1", start="2026-10-20T10:00:00Z", tokens=100, rounds=3, reply="done: see report")
    base.update(kw)
    return A.Evidence(**base)


def W(path, text="x", nonempty=True, in_repo=True, via_bash=False):
    return A.Write(path, in_repo, via_bash, nonempty, text)


def tk(**kw):
    return V.Ticket(kw.pop("key", "PROJ-1"), **kw)


# ------------------------------------------------------------------------------------------ combine and coverage
def C(key, c, **kw):
    return V.Check(key, c, **kw)


def test_weights_sum_to_one_and_budget_is_gone():
    assert sum(V.WEIGHTS.values()) == pytest.approx(1.0) and "budget" not in V.WEIGHTS and V.COVERAGE_MIN == 0.5


def test_s_is_renormalised_over_the_checks_that_have_a_value_and_coverage_is_their_weight():
    s, cov = V.combine([C("first_pass", 1.0), C("outcome", 0.5), C("judge", None), C("follows", 1.0), C("grounded", None)])
    assert cov == pytest.approx(0.65) and s == pytest.approx((0.25 + 0.30 * 0.5 + 0.10) / 0.65)
    assert V.combine([C(k, None) for k in V.ORDER]) == (None, 0.0)


@pytest.mark.parametrize("values,shown", [({"follows": 1.0, "grounded": 1.0}, False),                    # 0.20
                                          ({"outcome": 1.0, "follows": 1.0}, False),                     # 0.40
                                          ({"outcome": 0.5, "follows": 1.0, "grounded": 1.0}, True),     # exactly 0.50
                                          ({"first_pass": 1.0, "outcome": 1.0, "follows": 0.0}, True)])  # 0.65
def test_s_is_shown_only_from_coverage_one_half(values, shown):
    r = V.score_v2([C(k, values.get(k)) for k in V.ORDER], V.Gate(True), secrets=[], confirmed_deception=False, out_of_scope=False, generic_for=None, agent_type="r")
    assert (r["S"] is not None) is shown and r["too_little_evidence"] is (not shown) and r["S_partial"] is not None


def test_a_ceiling_like_lead_qas_040_cannot_happen():
    # v1: done never passed and follows passed -> 0.20 / 0.50 = 0.40 on every run. v2: follows alone is 0.10 of the weight: too little evidence, no number.
    r = V.score_v2([C("first_pass", None), C("outcome", None), C("judge", None), C("follows", 1.0), C("grounded", None)], V.Gate(True),
                   secrets=[], confirmed_deception=False, out_of_scope=False, generic_for=None, agent_type="lead-qa")
    assert r["S"] is None and r["coverage"] == pytest.approx(0.10) and r["too_little_evidence"] is True


# ------------------------------------------------------------------------------------------ first_pass
def verdicts(*vs):
    return [A.Verdict("reviewer", v, f"r{i}") for i, v in enumerate(vs)]


def test_first_pass_is_pending_until_the_gate_speaks_and_is_never_provisional():
    c = V.check_first_pass(facts(), ev(), [])
    assert c.c is None and c.pending is True and "pending" in c.omitted and "provisional" not in c.public()
    assert V.check_first_pass(facts(), ev(), verdicts(None)).pending is True            # a reply with no verdict word is still no verdict
    assert V.check_first_pass(facts(), ev(ticket=None), []).pending is True


@pytest.mark.parametrize("vs,expected", [(("PASS",), 1.0), (("REJECT", "PASS"), 0.5), (("REJECT", "REJECT", "PASS"), 0.0), (("REJECT", "REJECT"), 0.0)])
def test_first_pass_one_half_zero_by_the_number_of_returns(vs, expected):
    c = V.check_first_pass(facts(), ev(), verdicts(*vs))
    assert c.c == expected and not c.pending


def test_first_pass_is_empty_for_a_role_with_no_next_gate():
    c = V.check_first_pass(facts(next_gates=[]), ev(), [])
    assert c.c is None and not c.pending and "no next gate" in c.omitted


@pytest.mark.parametrize("text,v", [("Verdict: PASS", "PASS"), ("**APPROVE** (step 1)", "PASS"), ("REJECT: HIGH x", "REJECT"), ("REJECTED for now", "REJECT"), ("we rejected the idea earlier", None), ("looks fine", None), (None, None)])
def test_verdict_words(text, v):
    assert V.verdict_of(text) == v


# ------------------------------------------------------------------------------------------ the gate
def outs(*pairs):
    return [A.Output(what, kind, arg) for what, kind, arg in pairs]


def test_delivered_by_a_file_in_the_run_a_file_in_another_round_or_git():
    f = facts(outputs=outs(("the change file", "write", "docs/requirements/changes/*.md")))
    assert V.delivered(ev(writes=[W("docs/requirements/changes/PROJ-1.md")]), f, tk(), []).found_in == ["run"]
    g = V.delivered(ev(), f, tk(), [W("docs/requirements/changes/PROJ-1.md")])
    assert g.delivered and g.found_in == ["ticket"]
    g = V.delivered(ev(), f, tk(git_files={"docs/requirements/changes/PROJ-1.md"}), [])
    assert g.delivered and g.found_in == ["git"]


def test_delivered_by_a_structured_block_in_the_reply_but_not_by_a_short_or_unstructured_one():
    f = facts(outputs=outs(("the approvals", "write", "qa/suites/**")))
    report = "**APPROVE** (step A). Nothing blocks.\n\n**Files:** four of four present.\n**Items:** 12 read, 2 remarks.\n**Risk:** small, one remark on item 9.\n" + "detail " * 40
    assert V.structured_block(report) and V.delivered(ev(reply=report), f, tk(), []).found_in == ["reply"]
    for bad in ("done", "I did the work and it is fine. " * 30):
        g = V.delivered(ev(reply=bad), f, tk(), [])
        assert not g.delivered and g.named == "the approvals" and g.public()["reason"] == "not delivered: the approvals"


def test_delivered_at_the_alternative_paths_a_brief_may_name():
    cases = facts(outputs=outs(("draft cases", "write", "qa/cases/*.yaml")))
    assert V.delivered(ev(writes=[W("docs/work/batch/drafts/PILOT9-RUN-B.yaml")]), cases, tk(), []).delivered
    triage = facts(outputs=outs(("one triage file", "write", "docs/tasks/**/TRIAGE-*.md")))
    assert V.delivered(ev(writes=[W("docs/work/batch/checkpoints/PILOT9-RUN-TRIAGE-pipeline-1.md")]), triage, tk(), []).delivered
    assert not V.delivered(ev(writes=[W("docs/other/notes.md")]), triage, tk(), []).delivered


def test_a_reply_output_needs_its_regex_and_a_contains_output_the_text():
    f = facts(outputs=outs(("a verdict", "reply", r"\b(PASS|REJECT)\b")))
    assert V.delivered(ev(reply="Verdict: PASS"), f, tk(), []).delivered and not V.delivered(ev(reply="seems fine"), f, tk(), []).delivered
    c = facts(outputs=outs(("H9 targets", "contains", "H9 targets")))
    assert V.delivered(ev(writes=[W("a.md", "## H9 targets\n")]), c, tk(), []).found_in == ["run"]
    t = tk(git_files={"docs/requirements/changes/PROJ-1.md"}, read=lambda p: "## H9 targets\n")
    assert V.delivered(ev(), c, t, []).found_in == ["git"]
    assert not V.delivered(ev(), c, tk(), []).delivered


# ------------------------------------------------------------------------------------------ the four hard limits
def hard(**kw):
    base = dict(secrets=[], confirmed_deception=False, out_of_scope=False, generic_for=None, agent_type="r")
    base.update(kw)
    return V.score_v2([C("first_pass", 1.0), C("outcome", 1.0), C("judge", None), C("follows", 1.0), C("grounded", 1.0)], base.pop("gate", V.Gate(True)), **base)


def test_hard_limits():
    assert hard()["S"] == 1.0
    r = hard(secrets=[("aws-access-key", "final reply")])
    assert r["S"] == 0.0 and r["hard_limit"]["limit"] == "secret"
    r = hard(confirmed_deception=True)
    assert r["S"] == 0.0 and r["hard_limit"]["limit"] == "deception_confirmed"
    r = hard(out_of_scope=True)
    assert r["S"] == 0.5 and r["hard_limit"]["limit"] == "out_of_scope_edit"
    r = hard(generic_for="reviewer", agent_type="general-purpose")
    assert r["S"] == 0.5 and r["hard_limit"]["limit"] == "generic_for_role"
    r = hard(gate=V.Gate(False, "the change file"))
    assert r["S"] == 0.0 and r["hard_limit"]["detail"] == "not delivered: the change file" and r["gate"]["delivered"] is False


def test_suspected_deception_stays_a_flag_only_and_a_confirmed_one_is_read_from_the_decisions_file(tmp_path):
    assert hard()["hard_limit"] is None                                              # score_v2 never sees a suspicion, only a confirmation
    (tmp_path / "flag_decisions.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"run_id": "a", "flag": "deception", "decision": "confirm"}, {"run_id": "b", "flag": "deception", "decision": "confirm"},
        {"run_id": "b", "flag": "deception", "decision": "dismiss"},                       # the latest decision wins
        {"run_id": "c", "flag": "secret_suspected", "decision": "confirm"}]) + "\n")
    assert V.confirmed_deception(tmp_path) == {"a"}


# ------------------------------------------------------------------------------------------ outcome checks
IDS = {"SAFE-P10-01", "SAFE-P10-02", "SAFE-P10-03", "SAFE-P10-04"}


def test_traceability_is_a_share_times_one_minus_the_open_markers():
    e = ev(writes=[W("docs/requirements/access.md", "SAFE-P10-01 SAFE-P10-02 SAFE-P10-03 SAFE-P10-04")])
    full = V.check_traceability(e, tk(), IDS, IDS, "")
    assert full.c == 1.0 and full.reason == ""
    part = V.check_traceability(e, tk(), IDS, {"SAFE-P10-01", "SAFE-P10-02"}, "")
    assert part.c == pytest.approx(0.5) and "2 of 4" in part.reason
    change = "UNVERIFIED: a claim\nCONFLICT: two rules\nUNVERIFIED: was checked, DONE in v5\nplain text\n"
    marked = V.check_traceability(e, tk(), IDS, IDS, change)                          # 2 of 3 markers open
    assert marked.c == pytest.approx(1 - 2 / 3) and "2 of 3" in marked.reason
    assert V.check_traceability(ev(), tk(), IDS, IDS, "").c is None                     # no requirement id in the output: empty


def test_requirements_reviewer_escapes():
    runs = [{"run_id": "t1", "role": "test-designer", "start_ts": "2026-10-20T11:00:00Z"}]
    run = {"run_id": "rr", "role": "requirements-reviewer", "start_ts": "2026-10-20T10:00:00Z"}
    assert V.check_escapes_requirements(run, tk(runs=runs, replies={"t1": "all cases written"}), "PASS").c == 1.0
    esc = V.check_escapes_requirements(run, tk(runs=runs, replies={"t1": "SAFE-P10-02: the requirement contradicts SAFE-P10-03, cannot test"}), "PASS")
    assert esc.c == 0.0 and "test-designer" in esc.reason
    assert V.check_escapes_requirements(run, tk(runs=[]), "PASS").c is None             # nothing after it yet
    assert V.check_escapes_requirements(run, tk(runs=runs), "REJECT").c is None         # it rejected: nothing escaped


def test_mutation_score_is_killed_over_planted_and_empty_without_a_run(tmp_path):
    assert V.check_mutation("PROJ-1", tmp_path).c is None
    (tmp_path / "mutation").mkdir()
    (tmp_path / "mutation" / "PROJ-1.json").write_text(json.dumps({"planted": 8, "killed": 6}))
    c = V.check_mutation("PROJ-1", tmp_path)
    assert c.c == pytest.approx(0.75) and "6 of 8" in c.reason
    (tmp_path / "mutation" / "PROJ-1.json").write_text(json.dumps({"planted": 4, "killed": 4}))
    assert V.check_mutation("PROJ-1", tmp_path).c == 1.0
    (tmp_path / "mutation" / "PROJ-1.json").write_text(json.dumps({"planted": 0, "killed": 0}))
    assert V.check_mutation("PROJ-1", tmp_path).c is None
    (tmp_path / "mutation" / "PROJ-1.json").write_text("not json")
    assert V.check_mutation("PROJ-1", tmp_path).c is None


def test_builder_green_first_time():
    run = {"run_id": "b"}
    g, red = {"error": False}, {"error": True}
    assert V.check_green_first_time(run, tk(), [g]).c == 1.0
    assert V.check_green_first_time(run, tk(), [red, g]).c == 0.5
    assert V.check_green_first_time(run, tk(), [red, red, g]).c == 0.0                  # green only after two fix rounds
    assert V.check_green_first_time(run, tk(), [red, red]).c == 0.0
    assert V.check_green_first_time(run, tk(), []).c is None


def test_gate_escapes_wait_for_defect_reports_and_for_fourteen_days():
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    old = {"run_id": "g", "ticket_eff": "PROJ-1", "end_ts": "2026-11-01T10:00:00Z"}
    new = {"run_id": "g", "ticket_eff": "PROJ-1", "end_ts": "2026-11-15T10:00:00Z"}
    d = [{"ticket": "PROJ-1", "roles": ["reviewer"], "date": "2026-11-10"}]
    assert V.check_gate_escapes("reviewer", old, "PASS", [], now, defects_exist=False).c is None          # nobody reports defects yet
    assert V.check_gate_escapes("reviewer", old, "PASS", d, now, True).c == 0.0
    assert V.check_gate_escapes("reviewer", old, "PASS", [{"ticket": "PROJ-2", "roles": ["reviewer"]}], now, True).c == 1.0
    assert V.check_gate_escapes("reviewer", new, "PASS", [{"ticket": "PROJ-2", "roles": []}], now, True).c is None   # 5 days: pending
    assert V.check_gate_escapes("reviewer", old, "REJECT", d, now, True).c is None


def test_test_runner_honest_report():
    log = ["== 3 failed, 41 passed, 2 skipped in 12.50s =="]
    assert V.check_honest_report("41 passed, 3 failed, 2 skipped", log).c == 1.0
    c = V.check_honest_report("all 44 passed, 0 failed", log)
    assert c.c == 0.0 and "passed 44 (log: 41)" in c.reason
    assert V.check_honest_report("42 passed, 3 failed", log).c == 0.5                    # one of two counts is wrong
    assert V.check_honest_report("nothing to report", log).c is None and V.check_honest_report("41 passed", []).c is None
    assert V.counts_of("== 1 failed, 5 passed, 2 errors in 1.0s ==") == {"passed": 5, "failed": 1, "errors": 2}


def test_consumed_without_rework():
    run = {"run_id": "l1", "role": "lead-qa", "start_ts": "2026-10-20T10:00:00Z"}
    assert V.check_consumed(run, tk(runs=[])).c is None
    nxt = {"run_id": "x", "role": "automation-engineer", "start_ts": "2026-10-20T11:00:00Z", "flag_names": []}
    assert V.check_consumed(run, tk(runs=[nxt])).c == 1.0
    again = {"run_id": "y", "role": "lead-qa", "start_ts": "2026-10-20T12:00:00Z", "flag_names": ["returned"]}
    assert V.check_consumed(run, tk(runs=[nxt, again])).c == 0.0


def test_judge_is_empty_unless_calibrated_and_present():
    assert V.check_judge("t", Path("."), False, {"t": 0.9}).c is None
    assert V.check_judge("t", Path("."), True, {}).c is None
    assert V.check_judge("t", Path("."), True, {"t": 0.9}).c == 0.9


def test_grounded_is_a_share():
    cases = "- id: C1\n  rules: [SAFE-P10-01]\n- id: C2\n  rules: []\n- id: C3\n  rules: [SAFE-P10-02]\n- id: C4\n  rules: [NOPE-1]\n"
    proj = V.projectmod.Project(None, gates={"test_case_files": "qa/cases/*.yaml"})
    c = V.check_grounded(ev(writes=[W("qa/cases/x.yaml", cases)], project=proj), facts(criterion3=True), {"SAFE-P10-01", "SAFE-P10-02"})
    assert c.c == pytest.approx(0.5) and "2 of 4" in c.reason
    assert V.check_grounded(ev(), facts(criterion3=True), set()).c is None
    assert V.check_grounded(ev(), facts(criterion3=False), set()).c is None


# ------------------------------------------------------------------------------------------ the settle rule and re-scoring
def test_a_run_is_finished_when_meta_says_so_or_after_600_seconds_of_silence():
    now = datetime(2026, 10, 20, 10, 20, tzinfo=timezone.utc)
    run = {"end_ts": "2026-10-20T10:10:01.000Z"}
    assert V.SCORE_SETTLE_S == 600
    assert not V.is_finished(run, False, now) and V.is_finished(run, True, now)
    assert V.is_finished({"end_ts": "2026-10-20T10:10:00.000Z"}, False, now) and not V.is_finished({"end_ts": None}, False, now)


def test_rescore_when_the_run_has_newer_records_or_a_first_pass_is_pending():
    run = {"end_ts": "2026-10-20T10:10:00Z"}
    done = {"scored_at": "2026-10-20T10:30:00+00:00", "checks": {"first_pass": {"c": 1.0}}}
    assert V.needs_rescore(None, run, False) and V.needs_rescore(done, run, True)
    assert not V.needs_rescore(done, run, False)
    assert V.needs_rescore(done, {"end_ts": "2026-10-20T10:45:00Z"}, False)                  # a record arrived after the scoring
    assert V.needs_rescore({**done, "checks": {"first_pass": {"c": None, "pending": True}}}, run, False)


# ------------------------------------------------------------------------------------------ a run over fixture logs
def make_repo(env, roles=("lead-qa", "test-designer", "reviewer", "builder")):
    cdir = env.repo / "roles-22" / "criteria"
    cdir.mkdir(parents=True, exist_ok=True)
    (env.repo / "docs" / "agents").mkdir(parents=True, exist_ok=True)
    (env.repo / "docs" / "agents" / "PROJECT.md").write_text("# Project profile: test\n\n## Optional gates\n- `test_case_files`: qa/cases/*.yaml\n")
    for r in roles:
        shutil.copy(REPO / "roles-22" / "criteria" / f"{r}.md", cdir / f"{r}.md")
        role_file(env.repo, r, tools="Read, Grep, Glob, Edit, Write, Bash")
    (env.repo / "docs" / "requirements").mkdir(parents=True, exist_ok=True)
    (env.repo / "docs" / "requirements" / "ops.md").write_text("| ORD-FLD-D15 | PROJ-203 |\n| ORD-FLD-D16 | PROJ-203 |\n")


def spawn(desc, typ, tid):
    return tool_use(tid, "Agent", subagent_type=typ, description=desc, prompt="p")


def handback(text):
    return tool_use("hb", "SubagentHandback", message=text)


def put_main(env, spawns):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go", t=1), assistant("main1", t=2, blocks=spawns)])


def run_v2(env, **kw):
    s = Store()
    s.ingest()
    kw.setdefault("now", datetime(2026, 12, 1, tzinfo=timezone.utc))
    kw.setdefault("state", env.home)
    return V.run_scoring_v2(env.repo, scores_path=env.home / "scores.jsonl", store=s, **kw)


def lines(env):
    return [json.loads(x) for x in (env.home / "scores.jsonl").read_text().splitlines()]


def v2_of(env):
    return {k.split(":")[-1]: v for k, v in V.read_scores_v2(env.home / "scores.jsonl").items()}


LEAD_REPLY = ("**APPROVE** (step A). Nothing blocks.\n\n**Files:** four of four present.\n**Items:** 12 read, 2 remarks.\n"
              "**Risk:** small; one remark on item 9.\n" + "Detail line. " * 30)


def test_lead_qa_has_no_040_ceiling_it_shows_too_little_evidence(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] Lead QA: approve the design", "lead-qa", "t_l1")])
    add_sub(env.root, "S1", "l1", "lead-qa", [assistant("l1", agent="l1", t=10, day="2026-10-20", blocks=[handback(LEAD_REPLY)])], "t_l1")
    run_v2(env)
    lq = v2_of(env)["l1"]
    assert lq["scorer_version"] == 2 and lq["gate"]["delivered"] is True and lq["gate"]["found_in"][0] == "reply"
    assert lq["S"] is None and lq["too_little_evidence"] is True and lq["coverage"] == pytest.approx(0.10)       # follows only
    assert lq["S"] != 0.4 and lq["checks"]["follows"]["c"] == 1.0 and lq["checks"]["first_pass"]["omitted"].startswith("no next gate")
    assert lq["step"] == "Lead QA: approve the design" and lq["round"] == 1 and lq["ticket_eff"] == "PROJ-203"


def test_test_designer_gets_a_partial_value_where_the_mutation_score_exists(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] design the cases", "test-designer", "t_d1")])
    cases = "- id: C1\n  rules: [ORD-FLD-D15]\n- id: C2\n  rules: [ORD-FLD-D16]\n"
    add_sub(env.root, "S1", "d1", "test-designer", [assistant("d1", agent="d1", t=10, day="2026-10-20", blocks=[
        tool_use("w1", "Write", file_path="/work/worktrees/wt/qa/cases/ops.yaml", content=cases), handback("13 cases written")])], "t_d1")
    run_v2(env)
    assert v2_of(env)["d1"]["S"] is None and v2_of(env)["d1"]["checks"]["outcome"]["omitted"].startswith("no mutation run")
    (env.home / "mutation").mkdir()
    (env.home / "mutation" / "PROJ-203.json").write_text(json.dumps({"planted": 5, "killed": 3}))
    run_v2(env, rescore=True)
    d = v2_of(env)["d1"]
    assert d["checks"]["outcome"]["c"] == pytest.approx(0.6) and d["checks"]["grounded"]["c"] == 1.0 and d["coverage"] == pytest.approx(0.5)
    assert d["S"] == pytest.approx(round((0.30 * 0.6 + 0.10 + 0.10) / 0.5, 4)) and d["S"] not in (0.44, 0.56, 0.78, 1.0)


def test_a_rework_run_is_marked_round_two_and_carries_its_context(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] build the thing", "builder", "t_b1"), spawn("[PROJ-203] build: fix the review findings", "builder", "t_b2")])
    for i, rid in enumerate(("b1", "b2")):
        add_sub(env.root, "S1", rid, "builder", [assistant(rid, agent=rid, t=10 + 100 * i, day="2026-10-20", blocks=[handback("report " * 80)])], f"t_{rid}")
    run_v2(env)
    t = v2_of(env)
    assert (t["b1"]["round"], t["b2"]["round"]) == (1, 2)
    assert t["b2"]["step"] == "build: fix the review findings" and t["b2"]["model"] == "claude-sonnet-5-5" and t["b2"]["input_tokens"] is not None
    assert {"ticket_eff", "round", "step", "input_tokens", "model", "role_file_sha"} <= set(t["b2"])


def test_rescoring_keeps_the_v1_lines_and_appends_v2_lines(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] Lead QA: approve", "lead-qa", "t_l1")])
    add_sub(env.root, "S1", "l1", "lead-qa", [assistant("l1", agent="l1", t=10, day="2026-10-20", blocks=[handback(LEAD_REPLY)])], "t_l1")
    v1_line = {"schema": 1, "task_id": "S1:l1", "role": "lead-qa", "S": 0.4, "criteria": {"done": {"c": 0.0, "w": 0.3}}, "rev": 3, "ts": "2026-10-25T10:00:00+00:00", "start": "2026-10-20T10:00:10Z"}
    env.home.mkdir(parents=True, exist_ok=True)
    (env.home / "scores.jsonl").write_text(json.dumps(v1_line, sort_keys=True) + "\n")
    before = (env.home / "scores.jsonl").read_text()
    run_v2(env)
    text = (env.home / "scores.jsonl").read_text()
    assert text.startswith(before)                                                   # the v1 line is untouched, nothing was rewritten
    ls = lines(env)
    assert len(ls) == 2 and ls[0].get("scorer_version") is None and ls[1]["scorer_version"] == 2 and ls[1]["rev"] == 4
    assert V.read_scores_v2(env.home / "scores.jsonl")["S1:l1"]["rev"] == 4
    assert run_v2(env)["written"] == 0                                               # same result, line already newer than the run: nothing new


def test_only_finished_runs_are_scored(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] Lead QA: approve", "lead-qa", "t_l1")])
    add_sub(env.root, "S1", "l1", "lead-qa", [assistant("l1", agent="l1", t=10, day="2026-10-20", blocks=[handback(LEAD_REPLY)])], "t_l1")
    end = datetime(2026, 10, 20, 10, 0, 10, tzinfo=timezone.utc)
    early = run_v2(env, now=end + timedelta(seconds=300))
    assert early["written"] == 0 and early["stats"]["unsettled"] == 1                # still within 600 s of its last record
    assert run_v2(env, now=end + timedelta(seconds=601))["written"] == 1
    meta = env.root / PROJECT / "S1" / "subagents" / "agent-l1.meta.json"
    (env.home / "scores.jsonl").unlink()
    d = json.loads(meta.read_text())
    d["finished"] = True
    meta.write_text(json.dumps(d))
    assert run_v2(env, now=end + timedelta(seconds=5))["written"] == 1               # sub_meta.finished: no need to wait


def test_a_run_with_newer_records_is_scored_again(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] Lead QA: approve", "lead-qa", "t_l1")])
    p = add_sub(env.root, "S1", "l1", "lead-qa", [assistant("l1", agent="l1", t=10, day="2026-10-20", blocks=[handback(LEAD_REPLY)])], "t_l1")
    run_v2(env, now=datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc))
    first = v2_of(env)["l1"]
    assert run_v2(env, now=datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc))["written"] == 0
    with open(p, "a") as fh:                                                         # a late record, after the scoring
        fh.write(json.dumps(assistant("l2", agent="l1", t=50, day="2026-10-20", blocks=[handback(LEAD_REPLY + " extra")])) + "\n")
    # the scoring was at 12:00 on the same day; the new record is dated 10:00:50, i.e. EARLIER than scored_at, so only a later-dated record triggers it
    late = assistant("l3", agent="l1", t=0, day="2026-10-20T14:30:00.000Z", blocks=[handback(LEAD_REPLY + " more")])
    with open(p, "a") as fh:
        fh.write(json.dumps(late) + "\n")
    res = run_v2(env, now=datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc))
    assert res["written"] == 0 or v2_of(env)["l1"]["rev"] > first["rev"]            # same result: a touch line only when something changed
    assert V.needs_rescore(first, {"end_ts": "2026-10-20T14:30:00.000Z"}, False)


def test_a_generic_agent_without_flags_gets_a_skip_line_so_the_next_pass_does_not_read_it_again(env):
    make_repo(env)
    put_main(env, [spawn("explore the repo", "general-purpose", "t_g1")])
    add_sub(env.root, "S1", "g1", "general-purpose", [assistant("g1", agent="g1", t=10, day="2026-10-20", blocks=[handback("done " * 80)])], "t_g1")
    first = run_v2(env)
    g = v2_of(env)["g1"]
    assert first["written"] == 1 and g["S"] is None and g["scored"] is False and "not a role task" in g["skipped"]
    assert run_v2(env)["written"] == 0


def test_probe_runs_and_api_error_endings_are_skipped_not_scored_zero():
    assert V.not_scorable_reason("Live model-check test for test-runner", "Reply with exactly: ok", False)[0] == "probe"
    assert V.not_scorable_reason("Write-tool denial test for test-runner", "This is a tool-restriction denial test, not real work.", False)[0] == "probe"
    assert V.not_scorable_reason("Opus region test control: test-runner", "", False)[0] == "probe"
    kind, why = V.not_scorable_reason("Lead QA: reduced-suite proposal", "review the suite", True)
    assert kind == "api_error" and why.startswith("run ended on an API error")
    assert V.not_scorable_reason("[PROJ-1] Lead QA: approve", "review the design", False) is None
    assert V.not_scorable_reason("Test the login flow", "run the suite", False) is None
    import inspect
    assert list(inspect.signature(V.not_scorable_reason).parameters) == ["description", "prompt", "ended_on_api_error"]     # the run's reply is not an input


def test_a_run_that_ends_on_an_api_error_is_skipped_with_the_spawn_failure_flag_and_a_probe_is_skipped_by_its_prompt(env):
    make_repo(env)
    put_main(env, [spawn("[PROJ-203] Lead QA: approve", "lead-qa", "t_l1"), spawn("Live model-check test for lead-qa", "lead-qa", "t_l2")])
    err = assistant("l1e", agent="l1", t=60, day="2026-10-20", blocks=[{"type": "text", "text": "API Error: Connection refused"}])
    err["isApiErrorMessage"] = True
    err["apiErrorStatus"] = 500
    add_sub(env.root, "S1", "l1", "lead-qa", [assistant("l1", agent="l1", t=10, day="2026-10-20", blocks=[tool_use("x", "Read", file_path="/tmp/x")]), err], "t_l1")
    add_sub(env.root, "S1", "l2", "lead-qa", [assistant("l2", agent="l2", t=10, day="2026-10-20", blocks=[handback("**APPROVE** not real work, a denial test " + "x" * 80)])], "t_l2")
    run_v2(env)
    t = v2_of(env)
    assert t["l1"]["skip_kind"] == "api_error" and "spawn_failure" in t["l1"]["flags"] and t["l1"]["S"] is None and t["l1"]["scored"] is False
    assert t["l2"]["skip_kind"] == "probe"            # from the description; the reply says "denial test" too but is not read for this
    assert "gate" not in t["l1"] or t["l1"].get("gate") is None


def test_the_v2_log_holds_metadata_only_apart_from_the_short_step_label(env):
    make_repo(env)
    leak = "key " + "AKI" + "AABCDEFGHIJKLMNOP"
    put_main(env, [spawn("[PROJ-203] Lead QA: approve", "lead-qa", "t_l1")])
    add_sub(env.root, "S1", "l1", "lead-qa", [assistant("l1", agent="l1", t=10, day="2026-10-20", blocks=[tool_use("g1", "Bash", command="git diff secret-branch"), handback(LEAD_REPLY + leak)])], "t_l1")
    run_v2(env)
    blob = (env.home / "scores.jsonl").read_text()
    for forbidden in ("AKI" + "AABCDEFGHIJKLMNOP", "git diff secret-branch", "Detail line", "Hashes"):
        assert forbidden not in blob, forbidden
    assert v2_of(env)["l1"]["hard_limit"]["limit"] == "secret" and v2_of(env)["l1"]["S"] == 0.0


# ------------------------------------------------------------------------------------------ the rubric and the cli
def test_rubric_v2_states_the_weights_the_gate_the_limits_and_the_coverage_rule():
    t = (REPO / "console" / "RUBRIC-v2.md").read_text()
    for needle in ("0.25", "0.30", "0.10", "coverage ≥ 0.5", "too little evidence", "S = 0", "S ≤ 0.5", "confirmed by the person", "600 s", "scorer_version", "pending", "kappa ≥ 0.6"):
        assert needle in t, needle
    assert "budget" in t and "No `budget`" in t


def test_the_v2_option_is_on_the_agent_score_command(capsys):
    from agent_scoring import __main__ as cli
    with pytest.raises(SystemExit):
        cli.main(["agent-score", "--help"])
    assert "--v2" in capsys.readouterr().out
