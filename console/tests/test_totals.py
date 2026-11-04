"""Token totals: local-day boundary, message de-duplication, rewritten files, discovery by cwd, rescan, staleness,
and equality with the standalone ground-truth script (ground_truth.py, which shares no code with the console)."""

import datetime
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ground_truth as gt  # noqa: E402

from agent_console import config, queries, server  # noqa: E402
from agent_console.pricing import Pricing  # noqa: E402
from agent_console.store import Store  # noqa: E402
from conftest import PROJECT, add_sub, assistant, usage, user_prompt, write_jsonl  # noqa: E402

UTC = datetime.timezone.utc
PROJECT_DIR = "/work/app"
WT = "/work/worktrees"


def at(iso):  # a message timestamp, UTC ('...Z')
    return iso


def msg(mid, ts_utc, tok=100, rid=None, **kw):
    return assistant(mid, u=usage(tok, 0), day=ts_utc, rid=rid or f"req-{mid}", **kw)


def now_local(y, mo, d, h, mi):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))  # CET


TOK = "u.input + u.output + u.cache_read + u.cache_w5m + u.cache_w1h"


def _scope_join(scope):
    return "JOIN runs r ON r.run_id = u.run_id" + (" AND r.scope = 'project'" if scope != "all" else "")


def day_totals(store, days=7, now=None, scope="project"):
    """Tokens per LOCAL day for the last `days` local days: the stored usage.day buckets (one row per API message)."""
    now = now or datetime.datetime.now(UTC)
    today = now.astimezone(config.tz()).date()
    first = (today - datetime.timedelta(days=days - 1)).isoformat()
    db = store.reader()
    try:
        by_day = {r[0]: r[1] for r in db.execute(f"SELECT u.day, sum({TOK}) FROM usage u {_scope_join(scope)} WHERE u.day >= ? GROUP BY u.day", (first,))}  # nosec B608
    finally:
        db.close()
    return by_day, {"window_from": first, "today_date": today.isoformat(), "today": {"total": by_day.get(today.isoformat(), 0)}, "tz": config.tz_name()}


def all_tokens(store, scope="project"):
    db = store.reader()
    try:
        return db.execute(f"SELECT coalesce(sum({TOK}), 0) FROM usage u {_scope_join(scope)}").fetchone()[0]  # nosec B608
    finally:
        db.close()


# ---------- 1. day boundary (Europe/Madrid, DST) ----------
def test_midnight_crossing_session_is_split_by_local_day_not_utc(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [
        user_prompt("go"), msg("a", "2026-10-27T22:30:00.000Z"), msg("b", "2026-10-27T23:30:00.000Z"), msg("c", "2026-10-28T00:30:00.000Z")])
    s = Store()
    s.ingest()
    days, o = day_totals(s, now=now_local(2026, 10, 28, 9, 0))
    assert days == {"2026-10-27": 100, "2026-10-28": 200}  # UTC logic would have said 27th: 200, 28th: 100
    assert (o["today_date"], o["today"]["total"]) == ("2026-10-28", 200) and o["tz"] == "Europe/Madrid"


def test_today_does_not_drop_to_zero_shortly_after_local_midnight(env):
    # 00:30 local = 23:30Z on the 27th. With a UTC "today" this was already "tomorrow", i.e. an empty day.
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-27T23:10:00.000Z", tok=500)])
    s = Store()
    s.ingest()
    assert day_totals(s, now=now_local(2026, 10, 28, 0, 40))[1]["today"]["total"] == 500
    # 01:30 local = 00:30Z on the 28th: still the same local day, still 500 (UTC "today" would show 0 here)
    assert day_totals(s, now=now_local(2026, 10, 28, 1, 30))[1]["today"]["total"] == 500


def test_dst_change_25_oct_2026(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-24T22:30:00.000Z"),   # 00:30 CEST on the 25th
                                                   msg("b", "2026-10-25T22:30:00.000Z"),                      # 23:30 CET on the 25th
                                                   msg("c", "2026-10-25T23:30:00.000Z")])                     # 00:30 CET on the 26th
    s = Store()
    s.ingest()
    days, _ = day_totals(s, now=now_local(2026, 10, 28, 9, 0))
    assert days == {"2026-10-25": 200, "2026-10-26": 100}


def test_tokens_are_dated_by_each_message_not_by_session_start(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go", ), msg("a", "2026-10-20T10:00:00.000Z"), msg("b", "2026-10-28T08:00:00.000Z")])
    s = Store()
    s.ingest()
    days, _ = day_totals(s, days=30, now=now_local(2026, 10, 28, 9, 0))
    assert days == {"2026-10-20": 100, "2026-10-28": 100}


def test_window_is_whole_local_days(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("old", "2026-10-21T10:00:00.000Z"), msg("edge", "2026-10-22T09:00:00.000Z")])
    s = Store()
    s.ingest()
    days, o = day_totals(s, days=7, now=now_local(2026, 10, 28, 23, 50))
    assert o["window_from"] == "2026-10-22" and days == {"2026-10-22": 100}


# ---------- 2. de-duplication ----------
def test_resumed_session_repeating_message_ids_counts_once(env):
    first = [user_prompt("go", session="S1"), msg("m1", "2026-10-28T08:00:00.000Z", session="S1"), msg("m2", "2026-10-28T08:01:00.000Z", session="S1")]
    resumed = [user_prompt("again", session="S2"), msg("m1", "2026-10-28T08:00:00.000Z", session="S2"), msg("m2", "2026-10-28T08:01:00.000Z", session="S2"),
               msg("m3", "2026-10-28T09:00:00.000Z", session="S2")]
    write_jsonl(env.root / PROJECT / "S1.jsonl", first)
    write_jsonl(env.root / PROJECT / "S2.jsonl", resumed)
    s = Store()
    s.ingest()
    days, _ = day_totals(s, now=now_local(2026, 10, 28, 12, 0))
    assert days == {"2026-10-28": 300}  # 3 unique messages, not 5
    db = s.reader()
    assert db.execute("SELECT count(*) FROM usage").fetchone()[0] == 3
    assert sum(r[0] for r in db.execute("SELECT input FROM runs")) == 300  # run totals are de-duplicated too


def test_same_message_id_with_another_request_id_is_another_message(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("x", "2026-10-28T08:00:00.000Z", rid="r1"), msg("x", "2026-10-28T08:00:05.000Z", rid="r2")])
    s = Store()
    s.ingest()
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 200}


def test_message_split_over_several_records_counts_once(env):
    recs = [user_prompt("go")] + [msg("m1", f"2026-10-28T08:00:0{i}.000Z", tok=100, rid="r1") for i in range(3)]
    write_jsonl(env.root / PROJECT / "S1.jsonl", recs)
    s = Store()
    s.ingest()
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 100}


# ---------- 3. rewritten / truncated files ----------
def test_file_truncated_after_compaction_is_reread_and_not_double_counted(env):
    p = env.root / PROJECT / "S1.jsonl"
    write_jsonl(p, [user_prompt("go"), msg("a", "2026-10-28T08:00:00.000Z"), msg("b", "2026-10-28T08:01:00.000Z"), msg("c", "2026-10-28T08:02:00.000Z")])
    s = Store()
    s.ingest()
    # compaction rewrites the file: new first line, shorter, keeps c and adds d
    write_jsonl(p, [{"type": "system", "subtype": "compact_boundary", "timestamp": "2026-10-28T08:03:00.000Z", "sessionId": "S1", "cwd": PROJECT_DIR},
                    msg("c", "2026-10-28T08:02:00.000Z"), msg("d", "2026-10-28T08:04:00.000Z")])
    assert p.stat().st_size < s.reader().execute("SELECT off FROM files").fetchone()[0]
    stats = s.ingest()
    assert stats["rewritten"] == 1
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 400}  # a, b kept (spent), c once, d new


def test_file_rewritten_to_a_longer_one_with_a_new_first_line_is_reread(env):
    p = env.root / PROJECT / "S1.jsonl"
    write_jsonl(p, [user_prompt("first version"), msg("a", "2026-10-28T08:00:00.000Z")])
    s = Store()
    s.ingest()
    old_size = p.stat().st_size
    write_jsonl(p, [user_prompt("a completely different and longer first line " * 5), msg("a", "2026-10-28T08:00:00.000Z"),
                    msg("b", "2026-10-28T08:05:00.000Z"), msg("c", "2026-10-28T08:06:00.000Z")])
    assert p.stat().st_size > old_size  # longer than the stored offset: only the first-line hash can tell
    assert s.ingest()["rewritten"] == 1
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 300}


def test_appended_file_is_not_treated_as_rewritten(env):
    p = env.root / PROJECT / "S1.jsonl"
    write_jsonl(p, [user_prompt("go"), msg("a", "2026-10-28T08:00:00.000Z")])
    s = Store()
    s.ingest()
    with open(p, "a") as fh:
        fh.write(json.dumps(msg("b", "2026-10-28T08:01:00.000Z")) + "\n")
    assert s.ingest().get("rewritten", 0) == 0
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 200}


# ---------- 4. discovery by cwd ----------
def test_sessions_are_selected_by_cwd_not_by_directory_name(env):
    root = env.root
    write_jsonl(root / "-work-worktrees-app-a" / "A.jsonl", [user_prompt("x", session="A", cwd=f"{WT}/app-a"), msg("a1", "2026-10-28T08:00:00.000Z", session="A", cwd=f"{WT}/app-a")])
    write_jsonl(root / "-work-worktrees-app-b" / "B.jsonl", [user_prompt("x", session="B", cwd=f"{WT}/app-b/sub"), msg("b1", "2026-10-28T08:00:00.000Z", session="B", cwd=f"{WT}/app-b/sub")])
    write_jsonl(root / "-some-odd-dir-name" / "C.jsonl", [user_prompt("x", session="C", cwd=f"{PROJECT_DIR}/sub dir"), msg("c1", "2026-10-28T08:00:00.000Z", session="C", cwd=f"{PROJECT_DIR}/sub dir")])
    write_jsonl(root / "-work-looks-like-project" / "D.jsonl", [user_prompt("x", session="D", cwd="/home/dev/elsewhere"), msg("d1", "2026-10-28T08:00:00.000Z", session="D", cwd="/home/dev/elsewhere")])
    write_jsonl(root / "-work-helper" / "E.jsonl", [user_prompt("x", session="E", cwd=f"{PROJECT_DIR}-evil"), msg("e1", "2026-10-28T08:00:00.000Z", session="E", cwd=f"{PROJECT_DIR}-evil")])
    s = Store()
    s.ingest()
    now = now_local(2026, 10, 28, 12, 0)
    assert day_totals(s, now=now, scope="project")[0] == {"2026-10-28": 300}   # A, B (two parallel worktrees) and C
    assert day_totals(s, now=now, scope="all")[0] == {"2026-10-28": 500}
    db = s.reader()
    by = {Path(r["project_dir"]).name: r["scope"] for r in db.execute("SELECT project_dir, scope FROM runs")}
    assert len(by) == 5 and by["-work-worktrees-app-a"] == "project" and by["-work-looks-like-project"] == "other"
    assert by["-work-helper"] == "other" and by["-some-odd-dir-name"] == "project"


def test_two_parallel_worktree_sessions_at_the_same_time_are_both_counted(env):
    for sid, wt in (("P1", "app-one"), ("P2", "app-two")):
        recs = [user_prompt("x", session=sid, cwd=f"{WT}/{wt}")] + [msg(f"{sid}-{i}", f"2026-10-28T08:0{i}:00.000Z", session=sid, cwd=f"{WT}/{wt}") for i in range(3)]
        write_jsonl(env.root / f"-wt-{wt}" / f"{sid}.jsonl", recs)
    s = Store()
    s.ingest()
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 600}


# ---------- 5. new files, rescan, staleness ----------
def test_session_started_after_the_console_is_picked_up_by_a_page_load_rescan(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-28T08:00:00.000Z")])
    s = Store()
    s.ingest()
    c = TestClient(server.create_app(store=s, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")
    write_jsonl(env.root / "-fresh-new-dir" / "NEW.jsonl", [user_prompt("x", session="NEW", cwd=f"{WT}/app-new"), msg("n1", "2026-10-28T08:30:00.000Z", tok=777, session="NEW", cwd=f"{WT}/app-new")])
    before = all_tokens(s)
    r = c.post("/api/rescan?wait=true", json={}).json()
    assert r["started"] is True and r["state"] == "idle" and r["stale"] is False
    assert all_tokens(s) == before + 777
    assert c.post("/api/rescan?wait=true", json={}).json()["started"] is False  # throttled: not more often than every 5 s


def test_rescan_picks_up_appended_lines_and_new_files_every_cycle(env):
    p = env.root / PROJECT / "S1.jsonl"
    write_jsonl(p, [user_prompt("go"), msg("a", "2026-10-28T08:00:00.000Z")])
    s = Store()
    assert s.rescan(wait=True, min_interval=0) is True
    with open(p, "a") as fh:
        fh.write(json.dumps(msg("b", "2026-10-28T08:01:00.000Z")) + "\n")
    write_jsonl(env.root / "-other" / "N.jsonl", [user_prompt("x", session="N"), msg("n", "2026-10-28T08:02:00.000Z", session="N")])
    assert s.rescan(wait=True, min_interval=0) is True
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 300}


def test_freshness_is_stale_after_two_minutes(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-28T08:00:00.000Z")])
    s = Store()
    assert queries.freshness(s)["stale"] is True and queries.freshness(s)["last_scan_ok"] is None  # never scanned
    s.ingest()
    last = datetime.datetime.fromisoformat(s.progress["last_scan_ok"])
    assert queries.freshness(s, now=last + datetime.timedelta(seconds=30))["stale"] is False
    assert queries.freshness(s, now=last + datetime.timedelta(seconds=119))["stale"] is False
    f = queries.freshness(s, now=last + datetime.timedelta(seconds=121))
    assert f["stale"] is True and f["age_s"] == pytest.approx(121, abs=1) and f["stale_after_s"] == 120


def test_pages_say_incomplete_while_the_first_index_is_built(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-28T08:00:00.000Z")])
    s = Store()
    s.ingest()
    c = TestClient(server.create_app(store=s, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")
    s.progress.update(state="indexing", initial=True, files_done=1, files_total=9)
    assert c.get("/api/ctq/overview").json()["period"]["incomplete"] is True
    s.progress.update(state="idle", initial=False)
    assert c.get("/api/ctq/overview").json()["period"]["incomplete"] is False


def test_changing_the_time_zone_rebuilds_the_day_buckets(env, monkeypatch):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-27T23:30:00.000Z")])
    s = Store()
    s.ingest()
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 100}
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    s2 = Store()
    s2.ingest()
    assert day_totals(s2, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-27": 100}


# ---------- 6. subagent transcripts ----------
def test_subagent_transcripts_are_separate_files_and_counted_once(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("main1", "2026-10-28T08:00:00.000Z", tok=1000)])
    shared = msg("shared", "2026-10-28T08:10:00.000Z", tok=50, agent="a1", rid="rq")
    add_sub(env.root, "S1", "a1", "builder", [dict(shared, agentId="a1"), msg("a1-2", "2026-10-28T08:11:00.000Z", tok=10, agent="a1")], "toolu_1")
    add_sub(env.root, "S1", "a2", "builder", [dict(shared, agentId="a2"), msg("a2-2", "2026-10-28T08:12:00.000Z", tok=20, agent="a2")], "toolu_2")
    s = Store()
    s.ingest()
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 1000 + 50 + 10 + 20}  # `shared` once, not twice
    db = s.reader()
    assert {r["run_id"]: r["input"] for r in db.execute("SELECT run_id, input FROM runs")} == {"S1": 1000, "S1:a1": 60, "S1:a2": 20}


# ---------- 7. equality with the standalone ground truth ----------
def test_console_equals_the_standalone_ground_truth_on_a_mixed_fixture(env):
    root = env.root
    write_jsonl(root / PROJECT / "S1.jsonl", [user_prompt("go"), msg("a", "2026-10-27T22:30:00.000Z", 111), msg("b", "2026-10-27T23:30:00.000Z", 222),
                                               msg("c", "2026-10-28T00:30:00.000Z", 333, model="claude-haiku-4-5")])
    write_jsonl(root / PROJECT / "S2.jsonl", [user_prompt("again", session="S2"), msg("a", "2026-10-27T22:30:00.000Z", 111, session="S2"), msg("z", "2026-10-28T07:00:00.000Z", 444, session="S2")])
    add_sub(root, "S1", "s1", "builder", [msg("sa", "2026-10-28T08:00:00.000Z", 55, agent="s1"), msg("sb", "2026-10-26T08:00:00.000Z", 66, agent="s1")], "t1")
    write_jsonl(root / "-wt-x" / "W.jsonl", [user_prompt("x", session="W", cwd=f"{WT}/x"), msg("w", "2026-10-28T09:00:00.000Z", 77, session="W", cwd=f"{WT}/x")])
    write_jsonl(root / "-oth" / "O.jsonl", [user_prompt("x", session="O", cwd="/home/dev/elsewhere"), msg("o", "2026-10-28T09:30:00.000Z", 88, session="O", cwd="/home/dev/elsewhere")])
    s = Store()
    s.ingest()
    now = datetime.datetime(2026, 10, 28, 11, 0, tzinfo=UTC)
    files, recs = gt.load(str(root))
    assert len(files) == 5
    for scope in ("all", "project"):
        truth = gt.summarize(recs, 7, "Europe/Madrid", now=now, scope=scope, project_roots=[PROJECT_DIR, WT], remote="example-app")
        total = lambda c: c["input"] + c["output"] + c["cache_write"] + c["cache_read"]  # noqa: E731
        days, _ = day_totals(s, 7, now=now, scope=scope)
        assert days == {k: total(v) for k, v in truth["day"].items()}, scope
        db = s.reader()
        first = (now.astimezone(config.tz()).date() - datetime.timedelta(days=6)).isoformat()
        by_model = {r[0]: r[1] for r in db.execute(f"SELECT u.model, sum({TOK}) FROM usage u {_scope_join(scope)} WHERE u.day >= ? GROUP BY u.model", (first,))}  # nosec B608
        assert by_model == {k: total(v) for k, v in truth["model"].items()}, scope
        proj = {r[0]: r[1] for r in db.execute(f"SELECT r.project_dir, sum({TOK}) FROM usage u {_scope_join(scope)} WHERE u.day >= ? GROUP BY r.project_dir", (first,))}  # nosec B608
        assert proj == {k: total(v) for k, v in truth["project"].items()}, scope
        assert db.execute(f"SELECT count(*) FROM usage u {_scope_join(scope)} WHERE u.day >= ?", (first,)).fetchone()[0] == sum(v["messages"] for v in truth["day"].values()), scope  # nosec B608


def test_ground_truth_script_shares_no_code_with_the_console():
    src = (Path(gt.__file__)).read_text()
    assert "agent_console" not in src and "import sqlite3" not in src


# ---------- UI contract ----------
def test_ui_shows_last_rescan_and_stale():
    js = (Path(server.STATIC) / "app.js").read_text()
    for needle in ("last rescan", "STALE", "/api/rescan"):
        assert needle in js, needle
    assert "setInterval(pollStatus" not in js and "pollTimer" in js  # status refreshes itself every 5 s (1.5 s while scanning)


def test_file_rewritten_with_the_same_first_line_but_different_content_is_reread(env):
    p = env.root / PROJECT / "S1.jsonl"
    first = user_prompt("go")
    write_jsonl(p, [first, msg("a", "2026-10-28T08:00:00.000Z"), msg("b", "2026-10-28T08:01:00.000Z")])
    s = Store()
    s.ingest()
    write_jsonl(p, [first, msg("x", "2026-10-28T08:05:00.000Z", tok=400), msg("y", "2026-10-28T08:06:00.000Z", tok=500), msg("z", "2026-10-28T08:07:00.000Z", tok=600)])
    assert p.stat().st_size > 0 and s.ingest()["rewritten"] == 1               # the tail bytes before the stored offset no longer match
    assert day_totals(s, now=now_local(2026, 10, 28, 12, 0))[0] == {"2026-10-28": 100 + 100 + 400 + 500 + 600}
