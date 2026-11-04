"""Hand-written log records with EXPLICIT timestamps (seconds after a fixed base), for the time / wait / attribution tests.
No real log text anywhere."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import PROJECT, add_sub, write_jsonl  # noqa: F401  (re-exported for the tests)

BASE = datetime(2026, 10, 20, 8, 0, 0, tzinfo=timezone.utc)
CWD = "/work/app"


def at(sec: float) -> str:
    return (BASE + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(round((sec % 1) * 1000)):03d}Z"


def A(mid, sec, blocks=None, session="S1", agent=None, stop="end_turn", model="claude-sonnet-5-5", inp=10):
    """An assistant record at `sec`."""
    o = {"type": "assistant", "uuid": f"a-{mid}", "timestamp": at(sec), "cwd": CWD, "gitBranch": "HEAD", "sessionId": session, "isSidechain": agent is not None,
         "message": {"id": mid, "model": model, "stop_reason": stop, "usage": {"input_tokens": inp, "output_tokens": 5, "cache_read_input_tokens": 100,
                                                                            "cache_creation_input_tokens": 0},
                     "content": blocks or [{"type": "text", "text": "ok"}]}}
    return o


def TU(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def R(tid, sec, err=False, session="S1", text="x"):
    """A tool_result user record at `sec`."""
    return {"type": "user", "uuid": f"r-{tid}", "timestamp": at(sec), "sessionId": session, "cwd": CWD, "toolUseResult": {"x": 1},
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": err, "content": text}]}}


def P(sec, origin=None, session="S1", text="go", meta=False):
    """A user prompt record. origin = the log's origin.kind ("human", "task-notification", ...) or None (unmarked)."""
    o = {"type": "user", "uuid": f"p-{sec}", "timestamp": at(sec), "sessionId": session, "cwd": CWD, "gitBranch": "HEAD",
         "message": {"role": "user", "content": text}}
    if origin:
        o["origin"] = {"kind": origin}
    if meta:
        o["isMeta"] = True
    return o


def main_file(env, records, session="S1"):
    write_jsonl(env.root / PROJECT / f"{session}.jsonl", records)


def q(store, sql, *a):
    db = store.reader()
    try:
        return [dict(r) for r in db.execute(sql, a)]
    finally:
        db.close()


def one_call(env, name, dur, **inp):
    """A main session with ONE tool call of `dur` seconds: returns its tool_calls row and the waits."""
    from agent_console.store import Store
    main_file(env, [P(0, "human"), A("m1", 5, [TU("t1", name, **inp)]), R("t1", 5 + dur), A("m2", 6 + dur)])
    s = Store()
    s.ingest()
    return s, q(s, "SELECT * FROM tool_calls WHERE id='t1'")[0], q(s, "SELECT * FROM waits ORDER BY start_ts")
