"""Index (runs, tokens, dedup, incremental) and every quality flag."""

import json


from agent_console.store import Store
from conftest import (PROJECT, add_sub, api_error, assistant, role_file, tool_use, usage, user_prompt, write_jsonl)


def build_main_with_subs(env, subs):
    """One main session that spawns the given subs: [(agent, role, ticket_desc, records)]."""
    spawn_blocks = []
    for agent, role, desc, _ in subs:
        spawn_blocks.append(tool_use(f"toolu_{agent}", "Agent", subagent_type=role, description=desc, prompt="p"))
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), assistant("main1", blocks=spawn_blocks, t=1)])
    for agent, role, desc, recs in subs:
        add_sub(env.root, "S1", agent, role, recs, f"toolu_{agent}")


def sub_recs(agent, n_msgs=3, tok=100, start=10, **kw):
    return [assistant(f"{agent}-m{i}", u=usage(tok, 0), t=start + i, agent=agent, **kw) for i in range(n_msgs)]


def q(store, sql, *a):
    db = store.reader()
    try:
        return [dict(r) for r in db.execute(sql, a)]
    finally:
        db.close()


def test_roles_from_meta_and_spawn_link(env):
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1")), ("a2", "reviewer", "review", sub_recs("a2", start=20))])
    s = Store()
    s.ingest()
    runs = {r["run_id"]: r for r in q(s, "SELECT * FROM runs")}
    assert runs["S1"]["role"] == "main" and runs["S1:a1"]["role"] == "builder" and runs["S1:a2"]["role"] == "reviewer"
    assert runs["S1:a1"]["parent_run_id"] == "S1"
    assert runs["S1:a1"]["ticket"] == "PROJ-60036" and runs["S1:a1"]["ticket_src"] == "spawn_text"
    assert runs["S1:a2"]["ticket"] is None


def test_tokens_deduplicated_per_message(env):
    one_msg_three_blocks = [assistant("dup", u=usage(100, 50, 1000, 200), t=i, blocks=[{"type": "text", "text": "x"}]) for i in range(3)]
    write_jsonl(env.root / PROJECT / "S1.jsonl", one_msg_three_blocks)
    s = Store()
    s.ingest()
    r = q(s, "SELECT * FROM runs")[0]
    assert (r["rounds"], r["input"], r["output"], r["cache_read"], r["cache_w5m"]) == (1, 100, 50, 1000, 200)


def test_incremental_ingest_reads_only_new_lines(env):
    p = env.root / PROJECT / "S1.jsonl"
    write_jsonl(p, [assistant("m1", u=usage(10, 5))])
    s = Store()
    assert s.ingest()["files_read"] == 1
    assert s.ingest().get("files_read", 0) == 0  # nothing new: file untouched
    with open(p, "a") as fh:
        fh.write(json.dumps(assistant("m2", u=usage(10, 5), t=5)) + "\n")
    assert s.ingest()["files_read"] == 1
    assert q(s, "SELECT rounds, input FROM runs")[0] == {"rounds": 2, "input": 20}
    s2 = Store()  # a restart keeps the offsets
    assert s2.ingest().get("files_read", 0) == 0


def test_replaced_shorter_file_is_reparsed_and_old_spend_is_kept(env):
    p = env.root / PROJECT / "S1.jsonl"
    write_jsonl(p, [assistant("m1"), assistant("m2", t=1), assistant("m3", t=2)])
    s = Store()
    s.ingest()
    write_jsonl(p, [assistant("n1")])
    s.ingest()
    assert q(s, "SELECT rounds FROM runs")[0]["rounds"] == 4  # 3 earlier messages stay counted (that spend happened) + the new one


def test_ticket_sources_in_priority_order(env):
    # worklog beats path beats branch beats prompt
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("work on PROJ-60009", t=1), assistant("m1", t=2, branch="PROJ-60006-x",
                blocks=[tool_use("e", "Edit", file_path="/r/docs/PROJ-60003-notes.md", old_string="a", new_string="b")])])
    (env.repo / "worklogs" / "w.jsonl").write_text(json.dumps({"type": "request", "ticket": "PROJ-60000", "start": "2026-10-20T10:00:00+00:00",
                                                                 "end": "2026-10-20T11:00:00+00:00"}) + "\n")
    s = Store()
    s.ingest()
    assert q(s, "SELECT ticket, ticket_src FROM runs")[0] == {"ticket": "PROJ-60000", "ticket_src": "worklog"}
    (env.repo / "worklogs" / "w.jsonl").unlink()
    s.ingest()
    assert q(s, "SELECT ticket, ticket_src FROM runs")[0] == {"ticket": "PROJ-60003", "ticket_src": "path"}


def test_ticket_unknown_is_unknown(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [assistant("m1")])
    s = Store()
    s.ingest()
    assert q(s, "SELECT ticket, ticket_src FROM runs")[0] == {"ticket": None, "ticket_src": "unknown"}


def flags_of(s, name):
    return {r["run_id"]: json.loads(r["evidence"]) for r in q(s, "SELECT * FROM flags WHERE flag=?", name)}


def test_overthinking_needs_20_runs_and_flags_above_2x_median(env):
    subs = [(f"b{i}", "builder", "x", sub_recs(f"b{i}", n_msgs=3, tok=100, start=10 + i)) for i in range(24)]
    subs.append(("big", "builder", "x", sub_recs("big", n_msgs=3, tok=100000, start=60)))
    build_main_with_subs(env, subs)
    s = Store()
    s.ingest()
    f = flags_of(s, "overthinking")
    assert set(f) == {"S1:big"} and f["S1:big"]["tokens"] > 2 * f["S1:big"]["median_tokens"]


def test_overthinking_by_rounds(env):
    subs = [(f"b{i}", "builder", "x", sub_recs(f"b{i}", n_msgs=3, tok=100, start=10 + i)) for i in range(24)]
    subs.append(("long", "builder", "x", sub_recs("long", n_msgs=9, tok=1, start=60)))
    build_main_with_subs(env, subs)
    s = Store()
    s.ingest()
    assert set(flags_of(s, "overthinking")) == {"S1:long"}
    assert "rounds" in flags_of(s, "overthinking")["S1:long"]


def test_no_overthinking_flag_below_20_runs(env):
    subs = [(f"b{i}", "builder", "x", sub_recs(f"b{i}", tok=100, start=10 + i)) for i in range(5)]
    subs.append(("big", "builder", "x", sub_recs("big", tok=10**6, start=60)))
    build_main_with_subs(env, subs)
    s = Store()
    s.ingest()
    assert flags_of(s, "overthinking") == {}


def edit_recs(agent, *paths):
    blocks = [tool_use(f"{agent}-e{i}", "Edit", file_path=p, old_string="a", new_string="b") for i, p in enumerate(paths)]
    return [assistant(f"{agent}-m", blocks=blocks, t=10, agent=agent)]


def test_out_of_scope_by_role_paths(env):
    role_file(env.repo, "qa-analyst", tools="Read, Edit", output="- Writes `docs/requirements/changes/<KEY>.md` and `docs/requirements/*.md`.")
    build_main_with_subs(env, [("q1", "qa-analyst", "x", edit_recs("q1", "/work/worktrees/wt/docs/requirements/orders.md",
                                                                    "/work/worktrees/wt/api/app.py"))])
    s = Store()
    s.ingest()
    ev = flags_of(s, "out_of_scope_edit")["S1:q1"]
    assert [i["path"] for i in ev["items"]] == ["api/app.py"] and ev["items"][0]["why"] == "outside role paths"


def test_out_of_scope_by_ticket_modules_and_scratch_ignored(env):
    (env.repo / "qa" / "impact-map" / "orders.yaml").write_text("module: orders\ncode_paths:\n  globs:\n    - api/app_api/api/v1/orders.py\n    - web/src/pages/order/*\n")
    from agent_console.scope import ScopeProvider
    s = Store(scope=ScopeProvider(env.repo, claim_loader=lambda t: ["orders"] if t == "PROJ-60036" else None))
    build_main_with_subs(env, [("g1", "general-purpose", "task PROJ-60036", edit_recs(
        "g1", "/work/worktrees/wt/web/src/pages/order/A.tsx",
        "/work/worktrees/wt/api/app_api/api/v1/invoices.py", "/tmp/scratch.log"))])
    s.ingest()
    ev = flags_of(s, "out_of_scope_edit")["S1:g1"]
    assert [(i["path"], i["why"]) for i in ev["items"]] == [("api/app_api/api/v1/invoices.py", "outside ticket modules")]
    assert ev["checks"] == {"role_paths": False, "ticket_scope": True}


def test_no_claim_means_no_scope_check(env):
    from agent_console.scope import ScopeProvider
    s = Store(scope=ScopeProvider(env.repo, claim_loader=lambda t: None))
    build_main_with_subs(env, [("g1", "general-purpose", "task PROJ-60036", edit_recs("g1", "/work/worktrees/wt/anything.py"))])
    s.ingest()
    assert flags_of(s, "out_of_scope_edit") == {}


def test_outside_repo_edit_is_flagged(env):
    build_main_with_subs(env, [("g1", "general-purpose", "x", edit_recs("g1", "/home/dev/other-project/file.py"))])
    s = Store()
    s.ingest()
    assert flags_of(s, "out_of_scope_edit")["S1:g1"]["items"][0]["why"] == "outside repo"


def test_spawn_failure_aws_403(env):
    recs = [api_error(5, status=403, session="S1")]
    for r in recs:
        r["agentId"] = "f1"
    build_main_with_subs(env, [("f1", "builder", "x", recs)])
    s = Store()
    s.ingest()
    assert flags_of(s, "spawn_failure")["S1:f1"]["categories"] == ["aws_403"]


def test_error_followed_by_a_normal_reply_is_not_a_spawn_failure(env):
    recs = [api_error(5), assistant("ok", t=9, agent="f1")]
    recs[0]["agentId"] = "f1"
    build_main_with_subs(env, [("f1", "builder", "x", recs)])
    s = Store()
    s.ingest()
    assert flags_of(s, "spawn_failure") == {}


def test_model_downgraded_opus_to_sonnet_is_info(env):
    role_file(env.repo, "reviewer", model="opus")
    build_main_with_subs(env, [("r1", "reviewer", "x", sub_recs("r1", model="claude-sonnet-5-5", requested="us.anthropic.claude-opus-5-5"))])
    s = Store()
    s.ingest()
    assert flags_of(s, "model_downgraded")["S1:r1"] == {"expected_tier": "opus", "served_tiers": ["sonnet"]}
    assert q(s, "SELECT severity FROM flags WHERE flag='model_downgraded'")[0]["severity"] == "info"


def test_no_downgrade_flag_when_tier_matches(env):
    role_file(env.repo, "reviewer", model="opus")
    build_main_with_subs(env, [("r1", "reviewer", "x", sub_recs("r1", model="claude-opus-5-5"))])
    s = Store()
    s.ingest()
    assert flags_of(s, "model_downgraded") == {}


def test_returned_after_gate_and_reject(env):
    gate = sub_recs("g", start=30)
    gate[-1] = assistant("g-last", t=40, agent="g", blocks=[{"type": "text", "text": "REJECT: tests missing"}])
    build_main_with_subs(env, [("b1", "builder", "PROJ-60045 build", sub_recs("b1", start=10)), ("g", "reviewer", "PROJ-60045 review", gate),
                               ("b2", "builder", "PROJ-60045 rework", sub_recs("b2", start=50)), ("v", "verifier", "PROJ-60045 verify", sub_recs("v", start=60))])
    s = Store()
    s.ingest()
    assert set(flags_of(s, "returned")) == {"S1:b2"} and flags_of(s, "returned")["S1:b2"]["round"] == 1
    assert set(flags_of(s, "reject")) == {"S1:g"}


def test_two_builders_without_a_gate_between_are_not_a_return(env):
    build_main_with_subs(env, [("b1", "builder", "PROJ-60048", sub_recs("b1", start=10)), ("b2", "builder", "PROJ-60048", sub_recs("b2", start=50))])
    s = Store()
    s.ingest()
    assert flags_of(s, "returned") == {}


def test_checked_flag_survives_rebuild(env):
    from agent_console import queries
    build_main_with_subs(env, [("f1", "builder", "x", [{**api_error(5), "agentId": "f1"}])])
    s = Store()
    s.ingest()
    assert queries.check_flag(s, "S1:f1", "spawn_failure")
    s.ingest()
    db = s.reader()
    assert [f["status"] for f in queries.flag_rows(db, only_open=False)] == ["checked"] and queries.flag_rows(db) == []
    db.close()
