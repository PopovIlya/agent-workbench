"""Index (runs, tokens, dedup, incremental) and every quality flag."""

import json

import pytest

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


# ---- EXP1-R22C: the index meta rows (home, repo_root) and the ticket columns must not change -------------------------

def _golden_logs(root):
    """Extra sessions for the ticket-column golden (own key, effective key, spawn keys, a Write path key); the golden was made from the base commit 0891a04."""
    from conftest import PROJECT, add_sub, assistant, tool_result, tool_use, usage, user_prompt, write_jsonl
    recs = [user_prompt("[ABC-1] go", t=0, session="G1")]
    for i in range(3):
        recs += [assistant(f"g1-m{i}", t=1 + i, session="G1", u=usage(0, 0), blocks=[tool_use(f"g1-t{i}", "Agent", subagent_type="builder", description="[ABC-2] x", prompt="p")]),
                 tool_result(f"g1-t{i}", t=100 + i, session="G1")]
        add_sub(root, "G1", f"g1-ag{i}", "builder", [assistant(f"g1-s{i}", agent=f"g1-ag{i}", session="G1", t=10 + i)], f"g1-t{i}")
    write_jsonl(root / PROJECT / "G1.jsonl", recs)
    recs = [user_prompt("plain start", t=0, session="G2"),
            assistant("g2-w", t=5, session="G2", blocks=[tool_use("g2-write", "Write", file_path="/work/app/docs/ABC-7-notes.md", content="x")]),
            assistant("g2-m", t=20, session="G2", u=usage(0, 0), blocks=[tool_use("g2-t", "Agent", subagent_type="tester", description="check", prompt="please look at ABC-8")]),
            tool_result("g2-t", t=100, session="G2")]
    write_jsonl(root / PROJECT / "G2.jsonl", recs)
    add_sub(root, "G2", "g2-ag", "tester", [assistant("g2-s", agent="g2-ag", session="G2", t=21)], "g2-t")


# rule: CON-032
def test_ep_032_02_ticket_columns_equal_the_golden_of_the_base_commit(env):
    import shutil
    from pathlib import Path
    here = Path(__file__).resolve().parent
    shutil.copytree(here / "fixtures" / "logs", env.root)
    _golden_logs(env.root)
    s = Store()
    s.ingest()
    got = [list(r) for r in s.db.execute("SELECT run_id, ticket, ticket_src, ticket_eff FROM runs ORDER BY run_id")]
    golden = json.loads((here / "fixtures" / "golden_ticket_columns.json").read_text())
    assert len(golden) >= 1
    assert got == golden


# rule: CON-011
def test_ep_011_18_a_new_index_records_the_console_home_and_the_checkout(env):
    from pathlib import Path
    env.home.mkdir(parents=True, exist_ok=True)
    s = Store(env.home / "index.sqlite", env.repo)
    meta = dict(s.db.execute("SELECT k, v FROM meta").fetchall())
    assert meta["home"] == str(env.home.resolve()) and meta["repo_root"] == str(Path(env.repo).resolve())
    assert meta["tz"] == "Europe/Madrid"


# rule: CON-011
def test_ep_011_19_a_start_overwrites_home_and_checkout_and_keeps_the_derived_rows(env):
    from pathlib import Path
    from agent_console.store import SCHEMA_VERSION
    build_main_with_subs(env, [("a1", "builder", "ABC-1 build", sub_recs("a1"))])
    s = Store()
    s.ingest()
    n = q(s, "SELECT count(*) AS n FROM runs")[0]["n"]
    assert n >= 1
    kept = {r["k"]: r["v"] for r in q(s, "SELECT k, v FROM meta WHERE k IN ('tz','key_patterns')")}
    s.db.execute("UPDATE meta SET v='/other/home' WHERE k='home'")
    s.db.execute("UPDATE meta SET v='/other/repo' WHERE k='repo_root'")
    s.db.commit()
    s.db.close()
    s2 = Store(env.home / "index.sqlite", env.repo)
    assert q(s2, "SELECT count(*) AS n FROM runs")[0]["n"] == n
    assert s2.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    meta = {r["k"]: r["v"] for r in q(s2, "SELECT k, v FROM meta")}
    assert meta["home"] == str(env.home.resolve()) and meta["repo_root"] == str(Path(env.repo).resolve())
    assert {k: meta[k] for k in kept} == kept


# rule: CON-032
def test_ep_032_03_old_index_without_the_new_rows_keeps_its_derived_rows(env):
    from pathlib import Path
    build_main_with_subs(env, [("a1", "builder", "ABC-1 build", sub_recs("a1"))])
    s = Store()
    s.ingest()
    before = (q(s, "SELECT count(*) AS n FROM runs")[0]["n"], s.db.execute("PRAGMA user_version").fetchone()[0],
              {r["k"]: r["v"] for r in q(s, "SELECT k, v FROM meta WHERE k IN ('tz','key_patterns')")})
    assert before[0] >= 1
    s.db.execute("DELETE FROM meta WHERE k IN ('home','repo_root')")
    s.db.commit()
    s.db.close()
    s2 = Store(env.home / "index.sqlite", env.repo)
    meta = {r["k"]: r["v"] for r in q(s2, "SELECT k, v FROM meta")}
    assert meta["home"] == str(env.home.resolve()) and meta["repo_root"] == str(Path(env.repo).resolve())
    assert (q(s2, "SELECT count(*) AS n FROM runs")[0]["n"], s2.db.execute("PRAGMA user_version").fetchone()[0],
            {k: meta[k] for k in ("tz", "key_patterns")}) == before


# rule: CON-011
def test_ep_011_20_index_mismatch_lists_differ_and_missing_in_the_fixed_order(env):
    """CON-011: differ + missing are merged in INDEX_VALUES order; a matching index gives [], no file gives []."""
    from pathlib import Path
    from agent_console.store import INDEX_VALUES, index_mismatch
    env.home.mkdir(parents=True, exist_ok=True)
    db_path = env.home / "index.sqlite"
    assert index_mismatch(db_path, env.repo) == []
    Store(db_path, env.repo).db.close()
    assert index_mismatch(db_path, env.repo) == []
    s = Store(db_path, env.repo)
    s.db.execute("UPDATE meta SET v='other' WHERE k IN ('key_patterns','repo_root')")
    s.db.execute("DELETE FROM meta WHERE k IN ('tz','home')")
    s.db.commit()
    s.db.close()
    want = [n for n in INDEX_VALUES if n in ("time zone", "key patterns", "console home", "checkout")]
    assert want == ["time zone", "key patterns", "console home", "checkout"]
    assert index_mismatch(db_path, Path(env.repo)) == want


# rule: CON-010, CON-011
def test_ingest_leaves_no_scan_marker_row(env):
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    s.ingest()
    assert q(s, "SELECT k FROM meta WHERE k LIKE 'scan:%'") == []


# rule: CON-010, CON-011
def test_index_check_ignores_scan_marker_rows(env):
    from agent_console import config
    s = Store()
    s.ingest()
    from datetime import datetime, timezone
    s.db.execute("INSERT OR REPLACE INTO meta VALUES('scan:4000000', ?)", (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),))
    s.db.commit()
    s.db.close()
    from agent_console.store import index_check
    assert index_check(config.home() / "index.sqlite", config.repo_root()) == ([], [])


# ---------- EXP1-R22C security re-check: stale scan markers (NEW-2) ----------

def _plant_marker(s, pid, started):
    s.db.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (f"scan:{pid}", started))
    s.db.commit()


def _markers(s):
    return [r["k"] for r in q(s, "SELECT k FROM meta WHERE k LIKE 'scan:%' ORDER BY k")]


# rule: CON-010
def test_new_2_an_overflowing_pid_marker_does_not_fail_ingest_and_is_cleared(env):
    from datetime import datetime, timezone
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    _plant_marker(s, "99999999999999999999", datetime.now(timezone.utc).isoformat())
    assert _markers(s) == ["scan:99999999999999999999"]
    s.ingest()                                  # must not raise OverflowError
    assert s.progress["state"] == "idle"
    assert _markers(s) == []


# rule: CON-010
def test_new_2_a_live_pid_marker_older_than_the_age_bound_is_cleared(env):
    import os
    from datetime import datetime, timedelta, timezone
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    live = os.getppid()
    os.kill(live, 0)                            # alive, and not this process
    assert live != os.getpid()
    _plant_marker(s, live, (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
    s.ingest()
    assert _markers(s) == []


# rule: CON-010
def test_new_2_a_fresh_live_pid_marker_survives(env):
    import os
    from datetime import datetime, timezone
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    live = os.getppid()
    os.kill(live, 0)
    assert live != os.getpid()
    _plant_marker(s, live, datetime.now(timezone.utc).isoformat())
    s.ingest()
    assert _markers(s) == [f"scan:{live}"]


# rule: CON-010
@pytest.mark.parametrize("name", ["abc", "0"])
def test_review7_a_marker_with_an_unusable_pid_is_cleared(env, name):
    from datetime import datetime, timezone
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    s.db.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (f"scan:{name}", datetime.now(timezone.utc).isoformat()))
    s.db.commit()
    assert _markers(s) == [f"scan:{name}"]
    s.ingest()
    assert s.progress["state"] == "idle"
    assert _markers(s) == []


# rule: CON-010
def test_review7_a_live_pid_with_a_naive_time_two_hours_old_is_cleared(env):
    import os
    from datetime import datetime, timedelta, timezone
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    live = os.getppid()
    os.kill(live, 0)
    assert live != os.getpid()
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    assert "+" not in old and not old.endswith("Z")
    _plant_marker(s, live, old)
    s.ingest()
    assert s.progress["state"] == "idle"
    assert _markers(s) == []


# rule: CON-010
@pytest.mark.parametrize("started", ["now-naive", "not-a-time"])
def test_review7_a_live_pid_with_a_fresh_naive_or_unreadable_time_is_kept(env, started):
    import os
    from datetime import datetime, timezone
    build_main_with_subs(env, [("a1", "builder", "do PROJ-60036 thing", sub_recs("a1"))])
    s = Store()
    live = os.getppid()
    os.kill(live, 0)
    assert live != os.getpid()
    value = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() if started == "now-naive" else started
    _plant_marker(s, live, value)
    s.ingest()                                  # a naive time must not raise
    assert _markers(s) == [f"scan:{live}"]
