"""The console scores role tasks by itself after a rescan (new or changed runs, at most once a minute) and shows it in the header."""

import threading
import time

from agent_console import queries
from agent_console.autoscore import AutoScorer
from agent_console.store import Store
from conftest import PROJECT, add_sub, assistant, user_prompt, write_jsonl
from test_agent_score import build_logs, make_repo


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def seeded(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go"), assistant("m1", t=1)])
    add_sub(env.root, "S1", "a1", "builder", [assistant("a1", agent="a1", t=5)], "t_a1")
    s = Store()
    s.ingest()
    return s


def test_scores_when_runs_changed_and_not_again_when_nothing_changed(env):
    s, clock, calls = seeded(env), Clock(), []
    sc = AutoScorer(s, run=lambda st: calls.append(1) or {"written": 3}, clock=clock)
    assert sc.tick() is True and len(calls) == 1
    assert s.progress["last_score_ok"] and s.progress["score_written"] == 3 and s.progress["score_error"] is None
    clock.t += 500
    assert sc.tick() is False and len(calls) == 1          # same runs: nothing to score, however long ago


def test_a_new_run_is_scored_but_not_more_often_than_once_a_minute(env):
    s, clock, calls = seeded(env), Clock(), []
    sc = AutoScorer(s, run=lambda st: calls.append(1) or {"written": 1}, min_interval=60, clock=clock)
    assert sc.tick() is True
    add_sub(env.root, "S1", "a2", "reviewer", [assistant("a2", agent="a2", t=9)], "t_a2")
    s.ingest()
    clock.t += 30
    assert sc.tick() is False and len(calls) == 1          # changed, but only 30 s since the last scoring
    clock.t += 31
    assert sc.tick() is True and len(calls) == 2           # 61 s: now it runs


def test_a_failure_is_shown_and_retried_after_the_interval(env):
    s, clock = seeded(env), Clock()
    state = {"fail": True}

    def run(st):
        if state["fail"]:
            raise RuntimeError("boom with details that must not leak")
        return {"written": 2}

    sc = AutoScorer(s, run=run, min_interval=60, clock=clock)
    assert sc.tick() is False
    assert s.progress["score_error"] == "RuntimeError" and s.progress["last_score_ok"] is None
    state["fail"] = False
    clock.t += 10
    assert sc.tick() is False                              # too soon after the failed try
    clock.t += 60
    assert sc.tick() is True and s.progress["score_error"] is None


def test_it_waits_while_the_index_is_being_built(env):
    s = seeded(env)
    s.progress.update(state="indexing")
    assert AutoScorer(s, run=lambda st: {"written": 0}).tick() is False


def test_the_header_gets_the_time_of_the_last_scoring(env):
    s = seeded(env)
    f = queries.freshness(s)
    assert f["last_score_ok"] is None and f["score_age_s"] is None and f["score_error"] is None
    AutoScorer(s, run=lambda st: {"written": 0}).tick()
    f = queries.freshness(s)
    assert f["last_score_ok"] and 0 <= f["score_age_s"] < 5


def test_it_runs_after_every_finished_rescan_without_anyone_calling_the_cli(env):
    make_repo(env)
    build_logs(env)
    s = Store()
    done = threading.Event()
    sc = AutoScorer(s, min_interval=0)                     # the real agent-score, into the real score log
    orig = sc.tick

    def tick():
        r = orig()
        done.set()
        return r

    sc.tick = tick
    sc.attach()
    assert s.rescan(wait=True, min_interval=0) is True
    assert done.wait(60)
    for _ in range(100):                                   # the hook scores in its own thread
        if s.progress.get("last_score_ok"):
            break
        time.sleep(0.1)
    lines = (env.home / "scores.jsonl").read_text().splitlines()
    assert len(lines) >= 4 and s.progress["last_score_ok"] and s.progress["score_written"] == len(lines)
    assert len(queries.score_lines()) >= 4    # the Agents tab reads what was written
