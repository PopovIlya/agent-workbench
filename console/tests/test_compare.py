"""Ticket comparison, data layer (EXP1-R22C): agent_console.compare.compare / ticket / unknown_keys / to_json.

Cases are named EP-nnn-nn, DT-nnn-nn, BVA-nnn, TC-ST-nn (ticket EXP1-R22C).
The page, the CLI text and the formatter halves of shared cases live in test_compare_page.py,
test_compare_cli.py and test_compare_format.py. Here: the figures (JSON tree), the key checks and the wait-time rules.
The product module is imported inside each test: a missing module fails the test, it never skips it.
"""

from __future__ import annotations

import copy
import importlib
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from agent_console import config
from agent_console.pricing import Pricing
from agent_console.store import Store
from conftest import PROJECT, add_sub, api_error, assistant, tool_result, tool_use, usage, user_prompt, write_jsonl

M1, M2 = "m-one", "m-two"
PX = ("regional_multiplier: 1.0\nmodels:\n"
      "  m-one: {input: 1.00, output: 2.00, cache_write_5m: 3.00, cache_write_1h: 4.00, cache_read: 0.50}\n"
      "  m-two: {input: 10.00, output: 20.00, cache_write_5m: 30.00, cache_write_1h: 40.00, cache_read: 5.00}\n"
      "tier_defaults: {sonnet: m-one}\n")
SONNET = ("regional_multiplier: 1.0\nmodels:\n"
          "  sonnet-5-5: {input: 2.00, output: 10.00, cache_write_5m: 2.50, cache_write_1h: 4.00, cache_read: 0.20}\n")
SONNET_MODEL = "claude-sonnet-5-5"
NO_MAIN = "no main session"
KEYS4 = ("input", "output", "cache_write", "cache_read")
DENIED = "Permission to use Bash has been denied"
DISMISSED = "The user doesn't want to proceed with this tool use"


def at(n: int, day: str = "2026-10-20") -> str:
    """Timestamp n seconds after 10:00:00Z of `day`; equals conftest.ts(n) for n < 3600."""
    base = datetime.fromisoformat(day).replace(hour=10, tzinfo=timezone.utc)
    return (base + timedelta(seconds=n)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Sub:
    def __init__(self, sess, agent, tid, path):
        self.sess, self.agent, self.tid, self.path = sess, agent, tid, path


class W:
    """Builds the synthetic logs of one test. Main files are written by flush(); sub files at once."""

    def __init__(self, env, pricing=PX, day="2026-10-20", cwd="/work/app", filler_model=M1):
        self.env, self.day, self.cwd, self.filler_model = env, day, cwd, filler_model
        (env.tmp / "pricing.yaml").write_text(pricing)
        self.mains: dict[str, list[dict]] = {}
        self.k = 0
        self.sp = 0

    # ---- ids and times
    def at(self, n):
        return at(n, self.day)

    def uid(self, p):
        self.k += 1
        return f"{p}{self.k}"

    def main_path(self, sess):
        return self.env.root / PROJECT / f"{sess}.jsonl"

    # ---- records
    def asst(self, n, u=None, sess="S1", agent=None, mid=None, blocks=None, model=M1, **kw):
        # u=None: a filler record with a zero usage block under self.filler_model (a zero block equals no block at 0891a04)
        if u is None:
            u, model = usage(0, 0), self.filler_model
        return assistant(mid or self.uid("m"), model=model, u=u, blocks=blocks, session=sess,
                         agent=agent, day=self.at(n), cwd=self.cwd, **kw)

    def stop(self, n, sess="S1", u=None, mid=None, uuid=None, rid=None, agent=None):
        r = self.asst(n, u, sess, agent=agent, mid=mid, rid=rid)
        r["message"]["stop_reason"] = "end_turn"
        if uuid:
            r["uuid"] = uuid
        return r

    def text(self, n, text="done", sess="S1", agent=None, u=None):
        return self.asst(n, u, sess, agent=agent, blocks=[{"type": "text", "text": text}])

    def use(self, n, tid, name="Bash", sess="S1", agent=None, **inp):
        return self.asst(n, None, sess, agent=agent, blocks=[tool_use(tid, name, **(inp or {"command": "ls"}))])

    def prompt(self, n, text, sess="S1", agent=None, origin=None):
        r = user_prompt(text, t=n, session=sess, agent=agent, cwd=self.cwd)
        r["timestamp"] = self.at(n)
        if origin:
            r["origin"] = {"kind": origin}
        return r

    def typed(self, n, sess="S1", text="continue", origin="human"):
        return self.prompt(n, text, sess, origin=origin)

    def res(self, tid, n, err=False, sess="S1", text=None):
        r = tool_result(tid, err, t=n, session=sess)
        r["timestamp"] = self.at(n)
        if text is not None:
            r["message"]["content"][0]["content"] = text
        return r

    # ---- files
    def main(self, sess, key, *recs, at0=0):
        self.mains[sess] = [self.prompt(at0, f"[{key}] go" if key else "start", sess)] + list(recs)

    def add(self, sess, *recs):
        self.mains[sess].extend(recs)

    def sub(self, sess, key, steps=(), role="builder", agent=None, tid=None, spawn_n=None, res_n=None, desc=None,
            err=False, file=True, spawn=True, prompt="p"):
        """A spawn in main `sess` (record + result; err None = no result) and, with file=True, its run file.
        steps: records, or tuples (n, usage[, model]) turned into assistant records of the run."""
        self.sp += 1
        agent = agent or self.uid("ag")
        tid = tid or self.uid("tu")
        spawn_n = self.sp if spawn_n is None else spawn_n
        res_n = spawn_n + 1 if res_n is None else res_n
        if spawn:
            inp = {"description": desc if desc is not None else (f"[{key}] x" if key else "do it"), "prompt": prompt}
            if role:
                inp["subagent_type"] = role
            self.mains[sess].append(self.asst(spawn_n, None, sess, blocks=[tool_use(tid, "Agent", **inp)]))
            if err is not None:
                self.mains[sess].append(self.res(tid, res_n, err, sess))
        path = None
        if file:
            recs = [s if isinstance(s, dict) else self.asst(s[0], s[1], sess, agent=agent, model=s[2] if len(s) > 2 else M1) for s in steps]
            path = add_sub(self.env.root, sess, agent, role or "general-purpose", recs, tid)
        return Sub(sess, agent, tid, path)

    def nomain(self, k, own="ABC-9", fillers=2, fill_key=None, sess="S9", steps=None, **kw):
        """Key k has a sub run and no main session: the main `own` keeps its key (fillers/(fillers+1) < 0.8)."""
        self.main(sess, own, self.asst(5, usage(10, 0), sess))
        for _ in range(fillers):
            self.sub(sess, fill_key or own, [(20, usage(10, 0))])
        return self.sub(sess, k, [(30, usage(1000, 0))] if steps is None else steps, **kw)

    def flush(self):
        for sess, recs in self.mains.items():
            has_ts = any("timestamp" in r for r in recs)
            write_jsonl(self.main_path(sess), sorted(recs, key=lambda r: r.get("timestamp", "")) if has_ts else recs)


# ---- reading the comparison
def cmp_mod():
    return importlib.import_module("agent_console.compare")


def scan():
    st = Store()
    st.ingest()
    return st


def tree(st, a, b=None):
    cmp = cmp_mod()
    pr = Pricing.load(config.pricing_path())
    db = st.reader()
    try:
        return cmp.compare(db, pr, a, b or a)
    finally:
        db.close()


def data(st, k):
    return tree(st, k)["a"]


def tkt(st, k):
    cmp = cmp_mod()
    pr = Pricing.load(config.pricing_path())
    db = st.reader()
    try:
        return cmp.ticket(db, pr, k)
    finally:
        db.close()


def unknown(st, a, b):
    cmp = cmp_mod()
    db = st.reader()
    try:
        return cmp.unknown_keys(db, a, b)
    finally:
        db.close()


def go(w, k="ABC-1"):
    """Flush the logs, index them, return DATA(k)."""
    w.flush()
    return data(scan(), k)


def wait_of(w, k="ABC-1"):
    return go(w, k)["time_s"]["wait"]


def run_keys(st, run_id):
    db = st.reader()
    try:
        r = db.execute("SELECT ticket, ticket_eff FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return (r["ticket"], r["ticket_eff"]) if r else None
    finally:
        db.close()


def paths(d, pre=""):
    out = set()
    for k, v in d.items():
        if isinstance(v, dict):
            out |= paths(v, f"{pre}{k}.")
        else:
            out.add(f"{pre}{k}")
    return out


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def child3(w):
    """CHILD3: main S1 own key ABC-1 whose 3 of 3 keyed children carry ABC-2 (effective key ABC-2)."""
    w.main("S1", "ABC-1", w.asst(5, usage(400, 0)))
    for _ in range(3):
        w.sub("S1", "ABC-2", [(20, usage(10, 0))])


# =====================================================================================================
# CON-012  no period or scope filter
# =====================================================================================================

# rule: CON-012
def test_ep_012_01_old_record_counts(env):
    """EP-012-01 (CI-012-03): a record eight months old still counts."""
    w = W(env, day="2026-03-01")
    w.main("S1", "ABC-1", w.asst(5, usage(1000, 0)))
    w.sub("S1", "ABC-1", [(3, usage(2000, 0))])
    d = go(w)
    assert d["main_sessions"] == 1 and d["runs"]["total"] == 1
    assert d["tokens"]["total"]["input"] == 3000 and d["tokens"]["main"]["input"] == 1000


# rule: CON-012
def test_ep_012_02_session_outside_project_scope_counts(env):
    """EP-012-02 (CI-012-02): records whose cwd is outside the project tree still count."""
    w = W(env, cwd="/elsewhere/other")
    w.main("S1", "ABC-1", w.asst(5, usage(1000, 0)))
    w.sub("S1", "ABC-1", [(3, usage(2000, 0))])
    d = go(w)
    assert d["main_sessions"] == 1 and d["runs"]["total"] == 1 and d["tokens"]["total"]["input"] == 3000


# =====================================================================================================
# CON-013  which sessions belong to a ticket
# =====================================================================================================

# rule: CON-013
def test_ep_013_01_sub_run_included(env):
    """EP-013-01 (CI-013-01)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(700, 0))])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["tokens"]["by_model"][M1]["input"] == 700


# rule: CON-013
def test_ep_013_02_main_only(env):
    """EP-013-02 (CI-013-02)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(900, 0)))
    d = go(w)
    assert d["main_sessions"] == 1 and d["tokens"]["main"]["input"] == 900 and d["runs"]["total"] == 0


# rule: CON-013
def test_ep_013_03_effective_key_decides(env):
    """EP-013-03 (CI-013-03): a main session belongs to its effective key, not its own key."""
    w = W(env)
    child3(w)
    w.flush()
    st = scan()
    assert run_keys(st, "S1") == ("ABC-1", "ABC-2")
    d1, d2 = data(st, "ABC-1"), data(st, "ABC-2")
    assert d1["main_sessions"] == 0 and d1["tokens"]["main"] == NO_MAIN and d1["tokens"]["total"]["input"] == 0
    assert d2["main_sessions"] == 1 and d2["tokens"]["main"]["input"] == 400 and d2["runs"]["total"] == 3


# rule: CON-013
def test_ep_013_04_two_mains_summed(env):
    """EP-013-04 (CI-013-04): tokens, cost and wait add up over the ticket's main sessions."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100, "S1", usage(1_000_000, 0)), w.typed(400, "S1", "go", origin=None))
    w.main("S2", "ABC-1", w.stop(100, "S2", usage(2_000_000, 0)), w.typed(260, "S2", "go", origin=None))
    d = go(w)
    assert d["main_sessions"] == 2 and d["tokens"]["main"]["input"] == 3_000_000
    assert d["cost_usd"]["main"] == pytest.approx(3.0) and d["time_s"]["wait"] == 460


# rule: CON-013
def test_ep_013_05_key_is_case_sensitive(env):
    """EP-013-05 (CI-013-05): abc-1 is not ABC-1 (data half; the CLI exit line is in test_compare_cli.py)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(10, 0))])
    w.main("S2", "ABC-9")
    w.flush()
    st = scan()
    assert unknown(st, "abc-1", "ABC-9") == ["abc-1"]
    assert data(st, "abc-1")["runs"]["total"] == 0


# =====================================================================================================
# CON-014  spawns with no run file
# =====================================================================================================

# rule: CON-014
def test_ep_014_06_spawn_lead_wins_over_text(env):
    """EP-014-06 (CI-014-06): the key in the description wins over a key in the prompt text."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", None, file=False, err=True, desc="[ABC-2] x", prompt="please ABC-3", spawn_n=10, res_n=20)
    w.flush()
    st = scan()
    d2 = data(st, "ABC-2")
    assert d2["runs"]["total"] == 1 and d2["runs"]["failed"] == 1
    assert data(st, "ABC-1")["runs"]["total"] == 0
    assert unknown(st, "ABC-3", "ABC-1") == ["ABC-3"]


# rule: CON-014
def test_ep_014_07_spawn_text_key(env):
    """EP-014-07 (CI-014-07): no key in the description, a key in the prompt text."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", None, file=False, err=True, desc="do it", prompt="work on ABC-2 now", spawn_n=10, res_n=20)
    w.flush()
    st = scan()
    d2 = data(st, "ABC-2")
    assert d2["runs"]["total"] == 1 and d2["runs"]["failed"] == 1
    assert data(st, "ABC-1")["runs"]["total"] == 0


# rule: CON-014
def test_ep_014_09_spawn_takes_runs_own_key_not_effective_key(env):
    """EP-014-09 (CI-014-09): no evidence before the spawn: the spawning run's own runs.ticket, not ticket_eff."""
    w = W(env)
    w.main("S1", None)
    w.add("S1", w.asst(500, None, "S1", blocks=[tool_use("w1", "Write", file_path="/x/changes/ABC-1.md", content="x")]))
    for i in range(3):
        w.sub("S1", "ABC-2", [(20, usage(10, 0))], spawn_n=10 + 10 * i, res_n=100 + i)
    w.sub("S1", None, file=False, err=True, desc="do it", spawn_n=50, res_n=60)
    w.flush()
    st = scan()
    assert run_keys(st, "S1") == ("ABC-1", "ABC-2")
    d1, d2 = data(st, "ABC-1"), data(st, "ABC-2")
    assert d1["runs"]["total"] == 1 and d1["runs"]["failed"] == 1
    assert d2["runs"]["total"] == 3 and d2["runs"]["failed"] == 0


# rule: CON-014
def test_ep_014_10_run_file_spawn_not_counted_twice(env):
    """EP-014-10 (CI-014-10)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(10, 0))], role="builder")
    w.sub("S1", "ABC-1", [(21, usage(10, 0))], role="tester")
    d = go(w)
    assert d["main_sessions"] == 1 and d["runs"]["total"] == 2


# rule: CON-014
def test_ep_014_11_same_spawn_in_two_files_counts_once(env):
    """EP-014-11 (CI-014-11): a resumed session copies the spawn; one tool_use id, one spawn."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=True, tid="tu1", spawn_n=100, res_n=150)
    w.main("S2", "ABC-1")
    w.sub("S2", "ABC-1", file=False, err=True, tid="tu1", spawn_n=200, res_n=250)
    w.flush()
    st = scan()
    db = st.reader()
    try:
        assert db.execute("SELECT count(*) FROM tool_calls WHERE id='tu1'").fetchone()[0] == 2
    finally:
        db.close()
    d = data(st, "ABC-1")
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1 and d["runs"]["repeat_rounds"] == 0


# rule: CON-014
def test_ep_014_12_agent_and_task_tool_names_both_count(env):
    """EP-014-12 (CI-014-12)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=True, tid="tu1", role="builder", spawn_n=10)
    spec = w.asst(12, None, "S1", blocks=[tool_use("tu2", "Task", description="[ABC-1] x", subagent_type="tester", prompt="p")])
    w.add("S1", spec, w.res("tu2", 13, True))
    d = go(w)
    assert d["runs"]["total"] == 2 and d["runs"]["failed"] == 2 and d["runs"]["repeat_rounds"] == 0


# =====================================================================================================
# CON-015  failed runs
# =====================================================================================================

def one_sub(w, steps, **kw):
    w.main("S1", "ABC-1")
    return w.sub("S1", "ABC-1", steps, agent="a1", tid="tu1", spawn_n=10, **kw)


# rule: CON-015
@pytest.mark.parametrize("text", [DENIED, "Permission for this action was denied by the Claude Code auto mode classifier", DISMISSED],
                         ids=["EP-015-03", "EP-015-04", "EP-015-05"])
def test_ep_015_denial_as_last_turn_is_failed(env, text):
    """EP-015-03/04/05 (CI-015-03/04/05): a denial text in the last tool result fails the run."""
    w = W(env)
    one_sub(w, [w.use(20, "x1", agent="a1"), w.res("x1", 30, True, text=text)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_ep_015_08_final_text_is_not_failed(env):
    """EP-015-08 (CI-015-08)."""
    w = W(env)
    one_sub(w, [w.use(20, "x1", agent="a1"), w.res("x1", 25), w.text(30, "done", agent="a1")])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_ep_015_09_handback_is_not_failed(env):
    """EP-015-09 (CI-015-09)."""
    w = W(env)
    one_sub(w, [w.use(20, "h1", "SubagentHandback", agent="a1", message="report")])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_ep_015_10_unanswered_tool_use_is_failed(env):
    """EP-015-10 (CI-015-10)."""
    w = W(env)
    one_sub(w, [w.use(20, "x1", agent="a1")])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_ep_015_11_ordinary_result_last_is_failed(env):
    """EP-015-11 (CI-015-11): the run ends on an ordinary tool result, no final reply."""
    w = W(env)
    one_sub(w, [w.use(20, "x1", agent="a1"), w.res("x1", 30)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_ep_015_12_verdict_texts_are_results_not_failures(env):
    """EP-015-12 (CI-015-12)."""
    w = W(env)
    w.main("S1", "ABC-1")
    for i, (role, txt) in enumerate((("builder", "FAIL: x"), ("tester", "BLOCKED: y"), ("reviewer", "REJECT: z"))):
        w.sub("S1", "ABC-1", [w.text(20 + i, txt, agent=f"a{i}")], role=role, agent=f"a{i}")
    d = go(w)
    assert d["runs"]["total"] == 3 and d["runs"]["failed"] == 0 and d["runs"]["repeat_rounds"] == 0


# rule: CON-015
def test_ep_015_16_main_session_is_never_failed(env):
    """EP-015-16 (CI-015-16)."""
    w = W(env)
    w.main("S1", "ABC-1", api_error(t=900, session="S1"))
    w.sub("S1", "ABC-1", [(20, usage(10, 0))])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


def deleted_sub_world(w):
    return one_sub(w, [w.asst(20, usage(1_000_000, 0), agent="a1", blocks=[tool_use("x1", "Bash", command="ls")])])


# rule: CON-015
def test_ep_015_17_deleted_log_with_log_deleted_row_is_not_failed(env):
    """EP-015-17 (CI-015-17)."""
    w = W(env)
    sub = deleted_sub_world(w)
    w.flush()
    st = scan()
    sub.path.unlink()
    st.rescan(wait=True, min_interval=0)
    d = data(st, "ABC-1")
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0 and d["tokens"]["total"]["input"] == 1_000_000


# rule: CON-015
def test_ep_015_18_deleted_log_without_rescan_is_not_failed(env):
    """EP-015-18 (CI-015-18)."""
    w = W(env)
    sub = deleted_sub_world(w)
    w.flush()
    st = scan()
    sub.path.unlink()
    d = data(st, "ABC-1")
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0 and d["tokens"]["total"]["input"] == 1_000_000


# rule: CON-015
def test_ep_015_19_unreadable_log_is_not_failed(env):
    """EP-015-19 (CI-015-19)."""
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    w = W(env)
    sub = deleted_sub_world(w)
    w.flush()
    st = scan()
    os.chmod(sub.path, 0o000)
    try:
        d = data(st, "ABC-1")
    finally:
        os.chmod(sub.path, 0o600)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_ep_015_20_bad_lines_are_skipped(env):
    """EP-015-20 (CI-015-20): a line that is not JSON is skipped, the last valid turn decides."""
    w = W(env)
    w.main("S1", "ABC-1")
    s1 = w.sub("S1", "ABC-1", [w.use(20, "x1", agent="a1"), w.res("x1", 30, True, text=DENIED)], role="builder", agent="a1")
    s2 = w.sub("S1", "ABC-1", [w.text(20, "reply", agent="a2")], role="tester", agent="a2")
    w.flush()
    lines = s1.path.read_text().splitlines()
    s1.path.write_text("\n".join([lines[0], "{not json", lines[1], '{"type":"assistant","message":{"con']) + "\n")
    s2.path.write_text("{not json\n" + s2.path.read_text())
    d = data(scan(), "ABC-1")
    assert d["runs"]["total"] == 2 and d["runs"]["failed"] == 1


# rule: CON-015
@pytest.mark.parametrize("case", ["DT-015-01", "DT-015-02", "DT-015-06", "DT-015-07"])
def test_dt_015_last_turn_markers(env, case):
    """DT-015-01 api error message last; -02 final text, then a system api_error last; -06 denial then final text; -07 api_error then final text."""
    w = W(env)
    steps = {
        "DT-015-01": [w.prompt(10, "task", agent="a1"), w.asst(20, None, agent="a1", isApiErrorMessage=True, error="x", apiErrorStatus=403)],
        "DT-015-02": [w.prompt(10, "task", agent="a1"), w.text(15, "done", agent="a1"), api_error(t=20)],
        "DT-015-06": [w.use(20, "U1", agent="a1"), w.res("U1", 25, True, text=DENIED), w.text(30, "done", agent="a1")],
        "DT-015-07": [api_error(t=20), w.text(30, "done", agent="a1")],
    }[case]
    one_sub(w, steps)
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == (1 if case in ("DT-015-01", "DT-015-02") else 0)


# rule: CON-015
@pytest.mark.parametrize("err,text,total,failed", [(True, "Agent type 'x' not found", 1, 1), (False, None, 1, 0), (None, None, 0, 0)],
                         ids=["DT-015-13", "DT-015-14", "DT-015-15"])
def test_dt_015_spawn_without_run_file(env, err, text, total, failed):
    """DT-015-13 error result -> failed; -14 non-error result -> run, not failed; -15 no result -> not counted."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=err, tid="tu1", spawn_n=10)
    if text:
        w.mains["S1"][-1]["message"]["content"][0]["content"] = text
    d = go(w)
    assert d["runs"]["total"] == total and d["runs"]["failed"] == failed


# =====================================================================================================
# CON-014 decision table (DT-014-xx)
# =====================================================================================================

KA, KB, KC = "EXP1-AAA", "EXP1-BBB", "EXP1-CCC"


# rule: CON-014
def test_dt_014_01_run_file_counts_once(env):
    """DT-014-01 (CI-014-01)."""
    w = W(env)
    w.main("S1", KA, w.asst(10, usage(10, 0)))
    w.sub("S1", KA, [w.text(20, "done", agent="a1")], role="reviewer", agent="a1", tid="T1", err=False)
    w.flush()
    d = tkt(scan(), KA)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-014
@pytest.mark.parametrize("err,total,failed", [(True, 1, 1), (False, 1, 0), (None, 0, 0)], ids=["DT-014-02", "DT-014-03", "DT-014-04"])
def test_dt_014_spawn_without_run_file(env, err, total, failed):
    """DT-014-02 error result, key -> counted failed; -03 non-error -> counted; -04 no result -> not counted, key still known."""
    w = W(env)
    w.main("S1", KA, w.asst(10, usage(10, 0)))
    w.sub("S1", KA, file=False, role="reviewer", tid="T1", err=err)
    w.flush()
    st = scan()
    d = tkt(st, KA)
    assert d["runs"]["total"] == total and d["runs"]["failed"] == failed
    assert unknown(st, KA, KA) == []
    if err is None:
        assert d["runs"]["repeat_rounds"] == 0 and d["main_sessions"] == 1


# rule: CON-014
def test_dt_014_05_spawn_with_no_key_counts_nowhere(env):
    """DT-014-05 (CI-014-05)."""
    w = W(env)
    w.main("S1", KA, w.asst(10, usage(10, 0)))
    w.sub("S1", KA, [(20, usage(10, 0))], role="reviewer", err=False)
    w.main("S2", None)
    w.sub("S2", None, file=False, tid="T9", err=True, desc="do it")
    w.flush()
    st = scan()
    d = tkt(st, KA)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0
    assert tkt(st, KB)["runs"] == {"total": 0, "failed": 0, "repeat_rounds": 0}


# =====================================================================================================
# CON-016  repeat rounds
# =====================================================================================================

# rule: CON-016
def test_ep_016_01_repeat_rounds_per_role(env):
    """EP-016-01 (CI-016-01)."""
    w = W(env)
    w.main("S1", "ABC-1")
    for n in (10, 20, 30):
        w.sub("S1", "ABC-1", [(n, usage(10, 0))])
    w.main("S2", "ABC-2")
    w.sub("S2", "ABC-2", [(10, usage(10, 0))])
    w.flush()
    st = scan()
    assert data(st, "ABC-1")["runs"]["repeat_rounds"] == 2 and data(st, "ABC-2")["runs"]["repeat_rounds"] == 0


# rule: CON-016
def test_ep_016_02_rounds_are_numbered_per_role(env):
    """EP-016-02 (CI-016-02)."""
    w = W(env)
    w.main("S1", "ABC-1")
    for i, role in enumerate(("builder", "builder", "tester", "tester")):
        w.sub("S1", "ABC-1", [(10 + i, usage(10, 0))], role=role)
    d = go(w)
    assert d["runs"]["total"] == 4 and d["runs"]["repeat_rounds"] == 2


# rule: CON-016
@pytest.mark.parametrize("err,total,failed,repeat", [(True, 2, 1, 1), (False, 2, 0, 1), (None, 1, 0, 0)],
                         ids=["EP-016-03", "EP-016-04", "EP-016-05"])
def test_ep_016_spawn_then_run(env, err, total, failed, repeat):
    """EP-016-03 error spawn (no file) then a run of the role -> the run is a repeat; -04 non-error spawn; -05 spawn with no result counts nothing."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=err, spawn_n=5, res_n=6)
    w.sub("S1", "ABC-1", [(20, usage(10, 0))], spawn_n=15)
    d = go(w)
    assert d["runs"]["total"] == total and d["runs"]["failed"] == failed and d["runs"]["repeat_rounds"] == repeat


# rule: CON-016
def test_ep_016_06_two_mains_are_not_rounds(env):
    """EP-016-06 (CI-016-06)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.main("S2", "ABC-1")
    w.sub("S1", "ABC-1", [(10, usage(10, 0))])
    d = go(w)
    assert d["main_sessions"] == 2 and d["runs"]["total"] == 1 and d["runs"]["repeat_rounds"] == 0


# rule: CON-016
def test_ep_016_07_empty_role_is_general_purpose(env):
    """EP-016-07 (CI-016-07)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=True, tid="tu1", role="builder", spawn_n=5, res_n=6)
    w.sub("S1", "ABC-1", file=False, err=True, tid="tu2", role=None, spawn_n=7, res_n=8)
    w.sub("S1", "ABC-1", [(20, usage(10, 0))], role="builder", spawn_n=15)
    w.sub("S1", "ABC-1", [(30, usage(10, 0))], role=None, spawn_n=25)
    d = go(w)
    assert d["runs"]["total"] == 4 and d["runs"]["failed"] == 2 and d["runs"]["repeat_rounds"] == 2


# rule: CON-016
def test_bva_003_equal_start_timestamps(env):
    """BVA-003 (CI-016-08): two runs of one role start at the same second; the order is stable."""
    w = W(env)
    w.main("S1", "EXP1-100")
    w.add("S1", w.asst(1, None, "S1", blocks=[tool_use(t, "Agent", subagent_type="reviewer", description="[EXP1-100] r", prompt="p") for t in ("tA", "tB")]))
    for i, t in enumerate(("tA", "tB")):
        w.sub("S1", "EXP1-100", [w.text(5, "done", agent=f"a{i}"), w.text(9, "done", agent=f"a{i}")], role="reviewer", agent=f"a{i}", tid=t, spawn=False)
    w.flush()
    st = scan()
    t1, t2 = tree(st, "EXP1-100"), tree(st, "EXP1-100")
    assert t1["a"]["runs"]["total"] == 2 and t1["a"]["runs"]["repeat_rounds"] == 1
    cmp = cmp_mod()
    assert cmp.to_json(t1) == cmp.to_json(t2)


# =====================================================================================================
# CON-017  tokens
# =====================================================================================================

# rule: CON-017
def test_ep_017_01_four_token_kinds(env):
    """EP-017-01 (CI-017-01): cache write = 5m + 1h."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(inp=100, out=200, cr=300, cw=450, w5=400, w1=50))])
    d = go(w)
    want = {"input": 100, "output": 200, "cache_write": 450, "cache_read": 300}
    assert d["tokens"]["total"] == want and d["tokens"]["by_model"][M1] == want


# rule: CON-017
def test_ep_017_02_per_model(env):
    """EP-017-02 (CI-017-02)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(100, 0)), (21, usage(300, 0), M2)])
    d = go(w)
    assert set(d["tokens"]["by_model"]) == {M1, M2}
    assert d["tokens"]["by_model"][M1]["input"] == 100 and d["tokens"]["by_model"][M2]["input"] == 300 and d["tokens"]["total"]["input"] == 400


# rule: CON-017
def test_ep_017_03_null_model_is_unknown(env):
    """EP-017-03 (CI-017-03)."""
    w = W(env, filler_model=None)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [w.asst(20, usage(70, 0), agent="a1", model=None)], agent="a1")
    d = go(w)
    assert set(d["tokens"]["by_model"]) == {"unknown"}
    assert d["tokens"]["by_model"]["unknown"]["input"] == 70 and d["tokens"]["total"]["input"] == 70


# rule: CON-017
def test_ep_017_04_main_tokens_summed_over_sessions(env):
    """EP-017-04 (CI-017-04)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(100, 0), "S1"))
    w.main("S2", "ABC-1", w.asst(5, usage(250, 0), "S2"))
    d = go(w)
    assert d["tokens"]["main"]["input"] == 350 and d["tokens"]["total"]["input"] == 350


# rule: CON-017
def test_ep_017_05_duplicate_message_counted_once(env):
    """EP-017-05 (CI-017-05): the same API message in two files is one message."""
    w = W(env)
    rec = w.asst(5, usage(100, 0), "S1", mid="dup", rid="r1")
    w.main("S1", "ABC-1", rec)
    w.main("S2", "ABC-1", copy.deepcopy(rec))
    d = go(w)
    assert d["tokens"]["main"]["input"] == 100 and d["tokens"]["total"]["input"] == 100


# =====================================================================================================
# CON-018 / CON-019  cost, unpriced
# =====================================================================================================

# rule: CON-018
def test_ep_018_01_cost_per_model(env):
    """EP-018-01 (CI-018-01): m-one 1M x 1.00 = 1.0; m-two 100k x 10.00 = 1.0."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(1_000_000, 0)), (21, usage(100_000, 0), M2)])
    c = go(w)["cost_usd"]
    assert c["by_model"] == {M1: pytest.approx(1.0), M2: pytest.approx(1.0)}
    assert c["total"] == pytest.approx(2.0) and c["total"] == pytest.approx(sum(c["by_model"].values()))


# rule: CON-018
def test_ep_018_02_tier_price(env):
    """EP-018-02 (CI-018-02): a model with no key falls back to the tier default."""
    w = W(env, filler_model="claude-sonnet-9")
    tokens = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_w5m": 0, "cache_w1h": 0}
    cost, match = Pricing.load(config.pricing_path()).message_cost("claude-sonnet-9", tokens)
    assert cost is not None and match.how == "tier"
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(1_000_000, 0), "claude-sonnet-9")])
    c = go(w)["cost_usd"]
    assert c["total"] == pytest.approx(1.0) and c["unpriced_messages"] == 0
    assert c["by_model"] == {"claude-sonnet-9": pytest.approx(1.0)}


# rule: CON-018
def test_ep_018_03_cache_write_prices(env):
    """EP-018-03 (CI-018-03): 5m at 3.00 plus 1h at 4.00 per 1M."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(inp=0, out=0, cw=2_000_000, w5=1_000_000, w1=1_000_000))])
    d = go(w)
    assert d["cost_usd"]["total"] == pytest.approx(7.0) and d["tokens"]["total"]["cache_write"] == 2_000_000


# rule: CON-018
def test_ep_018_04_main_cost_and_share(env):
    """EP-018-04 (CI-018-04): main 2.0, sub 1.0: total 3.0, share 2.0."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(2_000_000, 0)))
    w.sub("S1", "ABC-1", [(20, usage(1_000_000, 0))])
    d = go(w)
    assert d["cost_usd"]["main"] == pytest.approx(2.0) and d["cost_usd"]["total"] == pytest.approx(3.0)
    assert d["cost_share"] == pytest.approx(2.0)


# rule: CON-019
def test_ep_019_01_unpriced_adds_zero_and_is_counted(env):
    """EP-019-01 (CI-019-01)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, usage(1_000_000, 0), "zzz-unpriced"), (21, usage(1_000_000, 0))])
    d = go(w)
    c = d["cost_usd"]
    assert c["total"] == pytest.approx(1.0) and c["unpriced_messages"] == 1
    assert d["tokens"]["by_model"]["zzz-unpriced"]["input"] == 1_000_000
    assert c["by_model"] == {M1: pytest.approx(1.0), "zzz-unpriced": pytest.approx(0.0)}


# rule: CON-019
def test_bva_004_zero_unpriced_messages(env):
    """BVA-004 (CI-019-02): only priced messages: the count is the integer 0."""
    w = W(env, SONNET)
    w.main("S1", "EXP1-100", w.asst(2, usage(10, 20), model=SONNET_MODEL))
    c = go(w, "EXP1-100")["cost_usd"]
    assert c["unpriced_messages"] == 0 and isinstance(c["unpriced_messages"], int) and not isinstance(c["unpriced_messages"], bool)
    assert c["total"] == pytest.approx(0.00022)


# rule: CON-019
def test_bva_005_one_unpriced_message(env):
    """BVA-005 (CI-019-03): one unpriced message adds exactly 0 to the cost, keeps its tokens, is listed with 0."""
    w = W(env, SONNET)
    w.main("S1", "EXP1-100", w.asst(2, usage(10, 20), model=SONNET_MODEL), w.asst(3, usage(10, 20), model="claude-unpriced-x"))
    d = go(w, "EXP1-100")
    c = d["cost_usd"]
    assert c["unpriced_messages"] == 1 and c["total"] == pytest.approx(0.00022)
    assert d["tokens"]["total"]["input"] == 20 and d["tokens"]["total"]["output"] == 40
    assert "claude-unpriced-x" in c["by_model"] and c["by_model"]["claude-unpriced-x"] == 0
    assert c["by_model"][SONNET_MODEL] == pytest.approx(0.00022)
    assert set(d["tokens"]["by_model"]) == {SONNET_MODEL, "claude-unpriced-x"}


# =====================================================================================================
# CON-020 / CON-021  wall and active time
# =====================================================================================================

# rule: CON-020
def test_ep_020_01_wall_spans_main_and_runs(env):
    """EP-020-01 (CI-020-01): first to last event over the main session and the run."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(300, usage(1, 0)))
    w.sub("S1", "ABC-1", [(100, usage(1, 0)), (600, usage(1, 0))])
    assert go(w)["time_s"]["wall"] == 600


# rule: CON-020
def test_ep_020_02_main_only_wall(env):
    """EP-020-02 (CI-020-02)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(360, usage(1, 0)), at0=60)
    assert go(w)["time_s"]["wall"] == 300


# rule: CON-020
def test_ep_020_03_run_without_timestamps_is_skipped(env):
    """EP-020-03 (CI-020-03)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(100, usage(1, 0)))
    recs = [w.asst(20, usage(1, 0), agent="a1"), w.asst(30, usage(1, 0), agent="a1")]
    for r in recs:
        del r["timestamp"]
    w.sub("S1", "ABC-1", recs, agent="a1")
    d = go(w)
    assert d["time_s"]["wall"] == 100 and d["runs"]["total"] == 1


# rule: CON-021
def test_ep_021_01_active_time_adds_overlapping_runs(env):
    """EP-021-01 (CI-021-01): active time may exceed wall time."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(500, usage(1, 0)))
    w.sub("S1", "ABC-1", [(0, usage(1, 0)), (300, usage(1, 0))], role="builder")
    w.sub("S1", "ABC-1", [(100, usage(1, 0)), (500, usage(1, 0))], role="tester")
    t = go(w)["time_s"]
    assert t["active_role"] == 700 and t["wall"] == 500


# rule: CON-021
def test_ep_021_02_active_is_run_time_only(env):
    """EP-021-02 (CI-021-02)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(1000, usage(1, 0)))
    w.sub("S1", "ABC-1", [(100, usage(1, 0)), (200, usage(1, 0))])
    t = go(w)["time_s"]
    assert t["active_role"] == 100 and t["wall"] == 1000


# rule: CON-021
def test_ep_021_03_spawn_without_file_has_no_time(env):
    """EP-021-03 (CI-021-03)."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=True, tid="tu1", role="tester", spawn_n=5, res_n=6)
    w.sub("S1", "ABC-1", [(0, usage(1, 0)), (200, usage(1, 0))], spawn_n=1)
    d = go(w)
    assert d["runs"]["total"] == 2 and d["time_s"]["active_role"] == 200


# rule: CON-021
def test_ep_021_04_run_without_timestamps_adds_zero(env):
    """EP-021-04 (CI-021-04)."""
    w = W(env)
    w.main("S1", "ABC-1")
    r1 = [w.asst(20, usage(1, 0), agent="a1"), w.asst(30, usage(1, 0), agent="a1")]
    for r in r1:
        del r["timestamp"]
    w.sub("S1", "ABC-1", r1, agent="a1", role="builder")
    w.sub("S1", "ABC-1", [(100, usage(1, 0)), (300, usage(1, 0))], role="tester")
    d = go(w)
    assert d["runs"]["total"] == 2 and d["time_s"]["active_role"] == 200


# rule: CON-020
def test_bva_006_no_timestamp_at_all(env):
    """BVA-006 (CI-020-04): a main session with no timestamps: wall and active are the number 0."""
    w = W(env)
    w.main("S1", "EXP1-100", w.asst(5, usage(1, 0)))
    for r in w.mains["S1"]:
        del r["timestamp"]
    t = go(w, "EXP1-100")["time_s"]
    assert t["wall"] == 0 and t["active_role"] == 0 and is_num(t["wall"]) and is_num(t["active_role"])


# rule: CON-020
def test_bva_006b_failed_spawn_only_has_no_time(env):
    """BVA-006b (CI-020-04, second variant): a ticket known only through a failed spawn."""
    w = W(env)
    w.main("S2", "EXP1-299", w.asst(5, usage(1, 0), "S2"))
    w.sub("S2", None, file=False, err=True, desc="EXP1-300 build")
    d = go(w, "EXP1-300")
    assert d["time_s"]["wall"] == 0 and d["time_s"]["active_role"] == 0
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1 and d["main_sessions"] == 0


# =====================================================================================================
# CON-022  wait time
# =====================================================================================================

def gap_world(w, xs, extra=()):
    """prompt 0 (typed), stop 100, extra, X at 200, typed 'later' 500 (no origin)."""
    w.main("S1", "ABC-1", w.stop(100), *extra, *xs, w.typed(500, "S1", "later", origin=None))
    return wait_of(w)


def user_x(w, text, **extra):
    r = w.prompt(200, text)
    r.update(extra)
    return r


# rule: CON-022
@pytest.mark.parametrize("make,want", [
    pytest.param(lambda w: user_x(w, "<command-name>/clear</command-name>"), 100, id="EP-022-06"),
    pytest.param(lambda w: user_x(w, "please continue"), 100, id="EP-022-07"),
    pytest.param(lambda w: user_x(w, "<task-notification>done</task-notification>", origin={"kind": "task-notification"}), 400, id="EP-022-08"),
    pytest.param(lambda w: user_x(w, "<local-command-stdout>ok</local-command-stdout>"), 400, id="EP-022-09"),
    pytest.param(lambda w: user_x(w, "[Request interrupted by user]"), 400, id="EP-022-10"),
    pytest.param(lambda w: user_x(w, "from a peer", isMeta=True, origin={"kind": "peer"}), 400, id="EP-022-12"),
    pytest.param(lambda w: user_x(w, "meta but human", isMeta=True, origin={"kind": "human"}), 400, id="EP-022-12b"),
    pytest.param(lambda w: user_x(w, "hook output", isMeta=True), 400, id="EP-022-13"),
    pytest.param(lambda w: {"type": "attachment", "uuid": "att-1", "sessionId": "S1", "timestamp": at(200), "attachment": {"type": "hook_success", "hookEvent": "SessionStart"}}, 400, id="EP-022-13b"),
    pytest.param(lambda w: {"type": "system", "subtype": "stop_hook_summary", "uuid": "sys-1", "sessionId": "S1", "timestamp": at(200)}, 400, id="EP-022-13c"),
    pytest.param(lambda w: user_x(w, "hello", origin={"kind": "human"}, toolUseResult={"x": 1}), 400, id="EP-022-16"),
])
def test_ep_022_what_ends_a_gap(env, make, want):
    """EP-022-06..16: a stop at 100, record X at 200, a typed message at 500. Ends a gap = 100, does not = 400."""
    w = W(env)
    assert gap_world(w, [make(w)]) == want


# rule: CON-022
def test_ep_022_11_ordinary_tool_result_ends_no_gap(env):
    """EP-022-11 (CI-022-11)."""
    w = W(env)
    assert gap_world(w, [w.res("x1", 200)], extra=[w.use(150, "x1")]) == 400


# rule: CON-022
def test_ep_022_17_sub_agent_files_add_nothing(env):
    """EP-022-17 (CI-022-17)."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100), w.typed(500, "S1", "go", origin=None))
    w.sub("S1", "ABC-1", [w.stop(150, agent="a1"), w.prompt(200, "plain", agent="a1")], agent="a1", spawn_n=20)
    assert wait_of(w) == 400


# rule: CON-022
def test_ep_022_18_two_mains_add_up(env):
    """EP-022-18 (CI-022-18)."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100, "S1"), w.typed(400, "S1"))
    w.main("S2", "ABC-1", w.stop(100, "S2"), w.typed(260, "S2"))
    assert wait_of(w) == 460


# rule: CON-022
def test_ep_022_19_stop_is_not_closed_by_another_session(env):
    """EP-022-19 (CI-022-19)."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100, "S1"))
    w.main("S2", "ABC-1", w.asst(400, None, "S2"), at0=300)
    d = go(w)
    assert d["main_sessions"] == 2 and d["time_s"]["wait"] == 0 and is_num(d["time_s"]["wait"])


def gone_world(w):
    w.main("S1", "ABC-1", w.stop(100), w.typed(400))
    w.flush()
    return scan()


# rule: CON-022
def test_ep_022_20_deleted_main_log_adds_no_wait(env):
    """EP-022-20 (CI-022-20): file deleted and rescanned (log_deleted row)."""
    w = W(env)
    st = gone_world(w)
    w.main_path("S1").unlink()
    st.rescan(wait=True, min_interval=0)
    d = data(st, "ABC-1")
    assert d["main_sessions"] == 1 and d["time_s"]["wait"] == 0 and d["time_s"]["wait"] != NO_MAIN
    assert isinstance(d["tokens"]["main"], dict)


# rule: CON-022
def test_ep_022_21_deleted_main_log_without_rescan(env):
    """EP-022-21 (CI-022-21)."""
    w = W(env)
    st = gone_world(w)
    w.main_path("S1").unlink()
    d = data(st, "ABC-1")
    assert d["main_sessions"] == 1 and d["time_s"]["wait"] == 0


# rule: CON-022
def test_ep_022_21b_unreadable_main_log(env):
    """EP-022-21b (CI-022-21): same item, the file exists but cannot be read."""
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    w = W(env)
    st = gone_world(w)
    os.chmod(w.main_path("S1"), 0o000)
    try:
        d = data(st, "ABC-1")
    finally:
        os.chmod(w.main_path("S1"), 0o600)
    assert d["main_sessions"] == 1 and d["time_s"]["wait"] == 0


def stop_pair(w, sess, uuid, mid="ms", rid="rq", typed_n=400, typed_uuid=None):
    t = w.typed(typed_n, sess)
    if typed_uuid:
        t["uuid"] = typed_uuid
    return w.stop(100, sess, mid=mid, uuid=uuid, rid=rid), t


# rule: CON-022
def test_ep_022_23_copied_file_counts_a_gap_once(env):
    """EP-022-23 (CI-022-23): S2 holds every S1 record unchanged."""
    w = W(env)
    w.main("S1", "ABC-1", *stop_pair(w, "S1", "u1"))
    w.mains["S2"] = copy.deepcopy(w.mains["S1"])
    d = go(w)
    assert d["main_sessions"] == 2 and d["time_s"]["wait"] == 300


# rule: CON-022
def test_ep_022_24_same_message_new_uuid_is_one_gap(env):
    """EP-022-24 (CI-022-24): the copy has a new uuid, the same message id + requestId."""
    w = W(env)
    w.main("S1", "ABC-1", *stop_pair(w, "S1", "u1"))
    w.main("S2", "ABC-1", *stop_pair(w, "S2", "u1b", typed_uuid="up-other"))
    assert wait_of(w) == 300


# rule: CON-022
def test_ep_022_25_stop_without_uuid_matches_on_message_id(env):
    """EP-022-25 (CI-022-25)."""
    w = W(env)
    w.main("S1", "ABC-1", *stop_pair(w, "S1", "u1"))
    s2 = stop_pair(w, "S2", "u1")
    del s2[0]["uuid"]
    w.main("S2", "ABC-1", *s2)
    w.flush()
    stop2 = [json.loads(x) for x in w.main_path("S2").read_text().splitlines() if '"ms"' in x][0]
    assert "uuid" not in stop2
    assert data(scan(), "ABC-1")["time_s"]["wait"] == 300


# rule: CON-022
def test_ep_022_26_stop_without_any_id_matches_on_timestamp_pair(env):
    """EP-022-26 (CI-022-26): no uuid, no message id, no requestId: the (stop ts, gap end ts) pair is the key."""
    w = W(env)
    for sess in ("S1", "S2"):
        stop = w.stop(100, sess)
        del stop["uuid"]
        del stop["message"]["id"]
        w.main(sess, "ABC-1", stop, w.typed(400, sess))
    w.flush()
    stop_line = json.loads(w.main_path("S1").read_text().splitlines()[1])
    assert "uuid" not in stop_line and "id" not in stop_line["message"] and "requestId" not in stop_line
    assert data(scan(), "ABC-1")["time_s"]["wait"] == 300


# rule: CON-022
def test_ep_022_29_different_replies_same_times_are_two_gaps(env):
    """EP-022-29 (CI-022-29)."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100, "S1", mid="ms1", uuid="u1", rid="rq1"), w.typed(400, "S1"))
    w.main("S2", "ABC-1", w.stop(100, "S2", mid="ms2", uuid="u2", rid="rq2"), w.typed(400, "S2"))
    assert wait_of(w) == 600


# rule: CON-022
def test_dt_022_27_earliest_gap_end_counts(env):
    """DT-022-27 (CI-022-27): shared stop uuid, gap ends at 400 in file 1 and 450 in file 2: counted once, at 300."""
    w = W(env)
    first = w.prompt(0, f"[{KA}] go", "S1", origin="human")
    first["uuid"] = "u0"
    stop = w.stop(100, "S1", mid="m1", uuid="u1", rid="r1")
    t1 = w.typed(400, "S1")
    t1["uuid"] = "u2"
    w.mains["S1"] = [first, stop, t1]
    t2 = w.typed(450, "S2")
    t2["uuid"] = "u3"
    w.mains["S2"] = [copy.deepcopy(first), copy.deepcopy(stop), t2]
    d = go(w, KA)
    assert d["time_s"]["wait"] == 300 and d["main_sessions"] == 2 and d["time_s"]["wait_over_2h"] == 0


# rule: CON-035
def test_ep_035_04_failed_runs_leak_no_text(env):
    """EP-035-04 (CI-035-04), data half: denial and API-error texts never reach the JSON; runs.failed is 2."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [w.use(20, "x1", agent="a1"), w.res("x1", 30, True, text=DENIED + " SENT-DENY-9f3a")], agent="a1", role="builder")
    w.sub("S1", "ABC-1", [api_error(t=20, message="SENT-APIERR-9f3a arn:aws:sts::000000000000:assumed-role/x")], agent="a2", role="tester")
    w.flush()
    t = tree(scan(), "ABC-1")
    out = cmp_mod().to_json(t)
    assert t["a"]["runs"]["failed"] == 2
    for bad in ("SENT-", "Permission to use", "The user doesn't want to proceed", "arn:aws"):
        assert bad not in out


# ---- state-transition cases for CON-022

# rule: CON-022
def test_tc_st_04_rule_example_askuserquestion_and_notification(env):
    """TC-ST-04 (CI-022-01): AskUserQuestion answered, task notification between two stops: 300 + 600 = 900."""
    w = W(env)
    w.main("S1", "ABC-1", w.use(10, "ask1", "AskUserQuestion", question="q"), w.res("ask1", 310), w.stop(400),
           w.prompt(450, "<task-notification>x</task-notification>", origin="task-notification"), w.stop(500), w.typed(1100))
    assert wait_of(w) == 900


# rule: CON-022
def test_tc_st_05_dismissed_askuserquestion_ends_no_gap(env):
    """TC-ST-05 (CI-022-02): the dismissal at 40 ends nothing; the typed message at 400 closes the gap from 10."""
    w = W(env)
    w.main("S1", "ABC-1", w.use(10, "ask1", "AskUserQuestion", question="q"), w.res("ask1", 40, True, text=DISMISSED), w.typed(400))
    assert wait_of(w) == 390


# rule: CON-022
def test_tc_st_06_rejected_permission_prompt_gap_starts_at_the_turn(env):
    """TC-ST-06 (CI-022-03): the gap starts at the assistant record holding the tool_use (10), not at the rejection (40)."""
    w = W(env)
    w.main("S1", "ABC-1", w.use(10, "bash1", "Bash", command="x"), w.res("bash1", 40, True, text=DISMISSED), w.typed(400))
    assert wait_of(w) == 390


# rule: CON-022
def test_tc_st_07_one_stop_one_gap(env):
    """TC-ST-07 (CI-022-04)."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100), w.typed(400))
    assert wait_of(w) == 300


# rule: CON-022
@pytest.mark.parametrize("reason", ["tool_use", "stop_sequence"], ids=["TC-ST-07a", "TC-ST-07b"])
def test_tc_st_07ab_other_stop_reasons_are_no_stop(env, reason):
    """TC-ST-07a/b (CI-022-04): stop_reason tool_use or stop_sequence is not an end_turn stop."""
    w = W(env)
    r = w.asst(100)
    r["message"]["stop_reason"] = reason
    w.main("S1", "ABC-1", r, w.typed(400))
    assert wait_of(w) == 0


# rule: CON-022
def test_tc_st_07c_isMeta_record_ends_no_gap(env):
    """TC-ST-07c (CI-022-04)."""
    w = W(env)
    meta = w.prompt(400, "system reminder")
    meta["isMeta"] = True
    w.main("S1", "ABC-1", w.stop(100), meta)
    assert wait_of(w) == 0


# rule: CON-022
def test_tc_st_07d_gap_runs_past_an_isMeta_record(env):
    """TC-ST-07d (CI-022-04): as 07c, then a typed message at 700: gap 100 to 700."""
    w = W(env)
    meta = w.prompt(400, "system reminder")
    meta["isMeta"] = True
    w.main("S1", "ABC-1", w.stop(100), meta, w.typed(700))
    assert wait_of(w) == 600


# rule: CON-022
def test_tc_st_08_stop_with_no_gap_end_adds_nothing(env):
    """TC-ST-08 (CI-022-05): the stop at 500 has no typed message after it."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100), w.typed(400), w.stop(500))
    assert wait_of(w) == 300


# rule: CON-022
def test_tc_st_08b_only_a_stop_gives_zero_not_a_label(env):
    """TC-ST-08 second variant (CI-022-05): a main session exists, so wait is the number 0."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100))
    wait = wait_of(w)
    assert wait == 0 and wait != NO_MAIN and is_num(wait)


def resume_world(w, second):
    f1 = [w.prompt(0, "[EXP1-WWW] go", origin="human"), w.stop(100, mid="mA", uuid="uA"), w.typed(400), w.stop(500, mid="mB", uuid="uB")]
    w.mains["S1"] = f1
    w.mains["S2"] = copy.deepcopy(f1) + second
    return go(w, "EXP1-WWW")


# rule: CON-022
def test_tc_st_09_resumed_session_example(env):
    """TC-ST-09 (CI-022-22): the rule's resumed-session example: 300 + 1500 = 1800, not 2100."""
    w = W(env)
    d = resume_world(w, [w.typed(2000, "S2")])
    assert d["time_s"]["wait"] == 1800 and d["main_sessions"] == 2


# rule: CON-022
def test_tc_st_10_stop_closed_only_in_the_resumed_file(env):
    """TC-ST-10 (CI-022-28): the stop in file 1 is not closed there; the copy in file 2 is: one gap of 1500."""
    w = W(env)
    f1 = [w.prompt(0, "[EXP1-WWW] go", origin="human"), w.stop(500, mid="mA", uuid="uA")]
    w.mains["S1"] = f1
    w.mains["S2"] = copy.deepcopy(f1) + [w.typed(2000, "S2")]
    assert go(w, "EXP1-WWW")["time_s"]["wait"] == 1500


def same_reply_world(w, second_mid, second_rid):
    stop_a = w.stop(100, mid="M1", uuid="uA", rid="R1")
    stop_b = w.stop(500, mid=second_mid, uuid="uB", rid=second_rid)
    assert stop_a["uuid"] != stop_b["uuid"]
    w.main("S1", "EXP1-WWW", stop_a, w.typed(400), stop_b, w.typed(1100))
    return wait_of(w, "EXP1-WWW")


# rule: CON-022
def test_tc_st_11_same_reply_twice_in_one_file_is_one_gap(env):
    """TC-ST-11 (CI-022-30): two stops share message id + requestId: one gap, 300 not 900."""
    w = W(env)
    assert same_reply_world(w, "M1", "R1") == 300


# rule: CON-022
def test_tc_st_11b_different_replies_are_two_gaps(env):
    """TC-ST-11 negative variant (CI-022-30): the second stop has M2/R2: 300 + 600 = 900."""
    w = W(env)
    assert same_reply_world(w, "M2", "R2") == 900


# =====================================================================================================
# CON-022 boundaries and CON-023
# =====================================================================================================

def edge_wait(w, typed_n):
    w.main("S1", "EXP1-100", w.stop(100), w.typed(typed_n))
    return go(w, "EXP1-100")["time_s"]


# rule: CON-022
def test_bva_007_gap_of_59_seconds_counts_zero(env):
    """BVA-007 (CI-022-14)."""
    t = edge_wait(W(env), 159)
    assert t["wait"] == 0 and t["wait_over_2h"] == 0 and is_num(t["wait"])


# rule: CON-022
def test_bva_008_gap_of_exactly_60_seconds_counts(env):
    """BVA-008 (CI-022-15)."""
    t = edge_wait(W(env), 160)
    assert t["wait"] == 60 and t["wait_over_2h"] == 0


# rule: CON-023
def test_bva_009_gap_of_exactly_two_hours_is_not_over(env):
    """BVA-009 (CI-023-01)."""
    t = edge_wait(W(env), 7300)
    assert t["wait"] == 7200 and t["wait_over_2h"] == 0


# rule: CON-023
def test_bva_010_gap_of_7201_seconds_counts_in_full_as_over(env):
    """BVA-010 (CI-023-02)."""
    t = edge_wait(W(env), 7301)
    assert t["wait"] == 7201 and t["wait_over_2h"] == 7201


# rule: CON-023
def test_ep_023_03_over_two_hours_part(env):
    """EP-023-03 (CI-023-03): gaps 300, 7500, 100, 7300; the two long ones are over 2 h."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100), w.typed(400), w.stop(500), w.typed(8000), w.stop(8100), w.typed(8200), w.stop(9000), w.typed(16300))
    t = go(w)["time_s"]
    assert t["wait"] == 15200 and t["wait_over_2h"] == 14800


# rule: CON-023
def test_ep_023_04_no_main_session_label(env):
    """EP-023-04 (CI-023-04)."""
    w = W(env)
    w.nomain("ABC-1")
    t = go(w)["time_s"]
    assert t["wait"] == NO_MAIN and t["wait_over_2h"] == NO_MAIN


# =====================================================================================================
# CON-024  cost share
# =====================================================================================================

def share_world(w, with_sub=True):
    w.main("S1", KA, w.asst(10, usage(10, 1000), model=SONNET_MODEL))
    if with_sub:
        w.sub("S1", KA, [(20, usage(10, 1000), SONNET_MODEL)])


# rule: CON-024
def test_dt_024_01_share_is_main_over_sub_cost(env):
    """DT-024-01 (CI-024-01)."""
    w = W(env, SONNET)
    share_world(w)
    w.flush()
    d = tkt(scan(), KA)
    assert d["cost_usd"]["total"] > 0 and d["cost_share"] == pytest.approx(1.0) and isinstance(d["cost_share"], float)


# rule: CON-024
def test_dt_024_02_no_sub_agents_label(env):
    """DT-024-02 (CI-024-02)."""
    w = W(env, SONNET)
    share_world(w, with_sub=False)
    w.flush()
    d = tkt(scan(), KA)
    assert d["cost_usd"]["main"] > 0 and d["cost_share"] == "no sub-agents"


# rule: CON-024
def test_dt_024_03_no_main_with_sub_cost(env):
    """DT-024-03 (CI-024-03)."""
    w = W(env, SONNET)
    w.nomain(KA, own=KC, fillers=3, fill_key=KB, steps=[(30, usage(10, 1000), SONNET_MODEL)])
    w.flush()
    d = tkt(scan(), KA)
    assert d["main_sessions"] == 0 and d["cost_usd"]["total"] > 0 and d["cost_share"] == NO_MAIN


# rule: CON-024
def test_dt_024_04_no_main_wins_over_no_sub_agents(env):
    """DT-024-04 (CI-024-04): the KA child is only a counted failed spawn (no file, no cost)."""
    w = W(env, SONNET)
    w.nomain(KA, own=KC, fillers=3, fill_key=KB, file=False, err=True)
    w.flush()
    d = tkt(scan(), KA)
    assert d["main_sessions"] == 0 and d["runs"]["total"] == 1
    assert d["cost_share"] == NO_MAIN and d["cost_usd"]["total"] == 0


# rule: CON-024
def test_bva_011_zero_main_cost_is_a_number(env):
    """BVA-011 (CI-024-05): main cost exactly 0, sub cost above 0: the share is the number 0."""
    w = W(env, SONNET)
    w.main("S1", "EXP1-100", w.asst(5, usage(0, 0), model=SONNET_MODEL))
    w.sub("S1", "EXP1-100", [(20, usage(10, 20), SONNET_MODEL)])
    c = go(w, "EXP1-100")
    assert c["cost_usd"]["main"] == 0 and c["cost_usd"]["total"] == pytest.approx(0.00022)
    assert is_num(c["cost_share"]) and c["cost_share"] == 0


# =====================================================================================================
# CON-025  no main session
# =====================================================================================================

MAIN_ROWS = (("tokens", "main"), ("cost_usd", "main"), ("time_s", "wait"), ("time_s", "wait_over_2h"), ("cost_share",))


def label_rows(d):
    return [d[p[0]] if len(p) == 1 else d[p[0]][p[1]] for p in MAIN_ROWS]


# rule: CON-025
def test_ep_025_01_no_main_session_labels_and_other_figures(env):
    """EP-025-01 (CI-025-01)."""
    w = W(env)
    w.nomain("ABC-1")
    d = go(w)
    assert label_rows(d) == [NO_MAIN] * 5
    assert d["runs"]["total"] == 1 and d["tokens"]["total"]["input"] == 1000 and is_num(d["cost_usd"]["total"])


# rule: CON-025
def test_ep_025_02_ticket_known_only_from_a_failed_spawn(env):
    """EP-025-02 (CI-025-02): zeros stay numbers, the main rows are labels."""
    w = W(env)
    w.main("S1", "ABC-9")
    w.sub("S1", None, file=False, err=True, desc="[ABC-3] x")
    d = go(w, "ABC-3")
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1
    assert d["tokens"]["total"] == {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    assert all(isinstance(v, int) for v in d["tokens"]["total"].values())
    assert d["cost_usd"]["total"] == 0 and d["time_s"]["wall"] == 0 and d["time_s"]["active_role"] == 0 and d["main_sessions"] == 0
    assert label_rows(d) == [NO_MAIN] * 5


# rule: CON-025
def test_ep_025_03_label_side_and_number_side(env):
    """EP-025-03 (CI-025-03), data half: a has the label in the 5 main rows, b has numbers (page/CLI cells: other test files)."""
    w = W(env)
    w.nomain("ABC-1")
    w.flush()
    t = tree(scan(), "ABC-1", "ABC-9")
    assert label_rows(t["a"]) == [NO_MAIN] * 5
    assert is_num(t["b"]["time_s"]["wait"]) and isinstance(t["b"]["tokens"]["main"], dict) and is_num(t["b"]["cost_usd"]["main"])


# =====================================================================================================
# CON-026  difference and ratio
# =====================================================================================================

def two_tickets(w, ua, ub, model_a=M1, model_b=M1):
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [(20, ua, model_a)])
    w.main("S2", "ABC-2")
    w.sub("S2", "ABC-2", [(20, ub, model_b)])
    w.flush()
    return tree(scan(), "ABC-1", "ABC-2")


# rule: CON-026
def test_ep_026_05_union_of_models(env):
    """EP-026-05 (CI-026-05): a model on one side only: zero on the other, ratio n/a or 0.0."""
    d = two_tickets(W(env), usage(100, 0), usage(1000, 0), model_a=M2, model_b=M1)["diff"]
    assert d["tokens"]["by_model"][M2]["input"] == {"diff": -100, "ratio": 0.0}
    assert d["tokens"]["by_model"][M1]["input"] == {"diff": 1000, "ratio": "n/a"}


# rule: CON-026
def test_ep_026_06_difference_is_taken_from_raw_values(env):
    """EP-026-06 (CI-026-06), JSON half: 2501 - 1499 = 1002 (rounded cells 3k - 1k are not 2k; page/CLI cells: other files)."""
    t = two_tickets(W(env), usage(1499, 0), usage(2501, 0))
    assert t["diff"]["tokens"]["total"]["input"]["diff"] == 1002


# rule: CON-026
def test_dt_026_01_difference_and_ratio(env):
    """DT-026-01 (CI-026-01)."""
    w = W(env, SONNET)
    w.main("S1", KA, w.asst(10, usage(inp=100, out=1000), model=SONNET_MODEL))
    w.main("S2", KB, w.asst(10, usage(inp=300, out=3000), model=SONNET_MODEL))
    w.flush()
    d = tree(scan(), KA, KB)["diff"]["tokens"]["total"]
    assert d["input"] == {"diff": 200, "ratio": 3.0} and d["output"] == {"diff": 2000, "ratio": 3.0}


# rule: CON-026
def test_dt_026_02_zero_a_gives_ratio_n_a(env):
    """DT-026-02 (CI-026-02)."""
    w = W(env, SONNET)
    w.main("S1", KA, w.asst(10, usage(cr=0), model=SONNET_MODEL))
    w.main("S2", KB, w.asst(10, usage(cr=500), model=SONNET_MODEL))
    w.flush()
    d = tree(scan(), KA, KB)["diff"]["tokens"]["total"]["cache_read"]
    assert d == {"diff": 500, "ratio": "n/a"}


NA = {"diff": "n/a", "ratio": "n/a"}


def label_diff_world(w, label_first):
    w.nomain(KA, own=KC, fillers=3, fill_key=KB, steps=[(30, usage(10, 100), SONNET_MODEL)])
    w.main("S2", KB, w.asst(10, usage(10, 100), "S2", model=SONNET_MODEL))
    w.flush()
    st = scan()
    assert tkt(st, KA)["main_sessions"] == 0
    return tree(st, KA, KB) if label_first else tree(st, KB, KA)


def assert_label_leaves(diff):
    for k in KEYS4:
        assert diff["tokens"]["main"][k] == NA
    assert diff["cost_usd"]["main"] == NA and diff["time_s"]["wait"] == NA and diff["time_s"]["wait_over_2h"] == NA and diff["cost_share"] == NA


# rule: CON-026
def test_dt_026_03_label_on_a_gives_n_a(env):
    """DT-026-03 (CI-026-03): a has no main session."""
    t = label_diff_world(W(env, SONNET), True)
    assert_label_leaves(t["diff"])
    assert t["a"]["tokens"]["main"] == NO_MAIN and isinstance(t["b"]["tokens"]["main"], dict)


# rule: CON-026
def test_dt_026_04_label_on_b_gives_n_a(env):
    """DT-026-04 (CI-026-04): b has no main session."""
    t = label_diff_world(W(env, SONNET), False)
    assert_label_leaves(t["diff"])
    assert t["b"]["tokens"]["main"] == NO_MAIN


# rule: CON-026
def test_ep_026_08_diff_paths_do_not_depend_on_labels(env):
    """EP-026-08 (CI-026-08, CI-030-04): the key paths of `diff` are the same with a label side and with two main sides."""
    w = W(env)
    w.nomain("ABC-1")
    w.main("S5", "ABC-5", w.asst(5, usage(10, 0), "S5"))
    w.flush()
    st = scan()
    with_label, plain = tree(st, "ABC-1", "ABC-9")["diff"], tree(st, "ABC-9", "ABC-5")["diff"]
    assert paths(with_label) == paths(plain)
    assert_label_leaves(with_label)
    assert {k: with_label["tokens"]["main"][k] for k in KEYS4} == {k: NA for k in KEYS4}


# rule: CON-026
def test_bva_013_ratio_tie_values_are_raw(env):
    """BVA-013 (CI-026-07), JSON half: 1/8 = 0.125 and 17/8 = 2.125 stay unrounded (the "0.13" / "2.13" text is test_compare_format.py)."""
    w = W(env)
    for i, (key, n) in enumerate((("EXP1-100", 8), ("EXP1-101", 1), ("EXP1-102", 8), ("EXP1-103", 17))):
        sess = f"S{i}"
        w.main(sess, key)
        for j in range(n):
            w.sub(sess, key, [(20, usage(1, 0))], spawn_n=1 + (j % 50))
    w.flush()
    st = scan()
    d1 = tree(st, "EXP1-100", "EXP1-101")["diff"]["runs"]["total"]
    d2 = tree(st, "EXP1-102", "EXP1-103")["diff"]["runs"]["total"]
    assert d1 == {"diff": -7, "ratio": 0.125} and d2 == {"diff": 9, "ratio": 2.125}


# =====================================================================================================
# CON-027  known and unknown keys (unknown_keys; the page and CLI texts are in the other files)
# =====================================================================================================

# rule: CON-027
def test_ep_027_01_key_known_through_a_sub_run(env):
    """EP-027-01 (CI-027-01), data half."""
    w = W(env)
    w.nomain("ABC-1")
    w.flush()
    st = scan()
    d = data(st, "ABC-1")
    assert d["runs"]["total"] == 1 and d["main_sessions"] == 0
    assert unknown(st, "ABC-1", "ABC-9") == []


# rule: CON-027
def test_ep_027_02_own_key_of_a_main_session_is_known(env):
    """EP-027-02 (CI-027-02), data half: ABC-1 is only the own key of M; known, no data."""
    w = W(env)
    child3(w)
    w.flush()
    st = scan()
    assert run_keys(st, "S1") == ("ABC-1", "ABC-2")
    d = data(st, "ABC-1")
    assert d["runs"]["total"] == 0 and d["main_sessions"] == 0 and d["tokens"]["main"] == NO_MAIN
    assert unknown(st, "ABC-1", "ABC-2") == []


# rule: CON-027
def test_ep_027_03_key_known_through_a_counted_spawn_only(env):
    """EP-027-03 (CI-027-03), data half."""
    w = W(env)
    w.nomain("ABC-1")
    w.sub("S9", None, file=False, err=True, desc="[ABC-3] x", tid="tu-abc3", spawn_n=40)
    w.flush()
    st = scan()
    assert data(st, "ABC-9")["runs"]["total"] == 2
    d = data(st, "ABC-3")
    assert d["runs"]["total"] == 1 and d["time_s"]["wall"] == 0
    assert unknown(st, "ABC-3", "ABC-9") == []


# rule: CON-027
def test_ep_027_04_key_known_after_its_log_is_deleted(env):
    """EP-027-04 (CI-027-04), data half."""
    w = W(env)
    sub = w.nomain("ABC-1")
    w.flush()
    st = scan()
    sub.path.unlink()
    st.rescan(wait=True, min_interval=0)
    d = data(st, "ABC-1")
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0
    assert unknown(st, "ABC-1", "ABC-9") == []


# rule: CON-027
def test_ep_027_05_unknown_key_a(env):
    """EP-027-05 (CI-027-05), data half."""
    w = W(env)
    w.nomain("ABC-1")
    w.flush()
    assert unknown(scan(), "ABC-404", "ABC-9") == ["ABC-404"]


# rule: CON-027
def test_ep_027_07_both_unknown_a_first(env):
    """EP-027-07 / EP-027-08 (CI-027-07, CI-027-08), data half."""
    w = W(env)
    w.nomain("ABC-1")
    w.flush()
    st = scan()
    assert unknown(st, "ABC-404", "ABC-405") == ["ABC-404", "ABC-405"]
    assert unknown(st, "ABC-9", "ABC-405") == ["ABC-405"]


# rule: CON-027
def test_ep_027_09_same_unknown_key_named_once(env):
    """EP-027-09 (CI-027-09), data half."""
    w = W(env)
    w.nomain("ABC-1")
    w.flush()
    assert unknown(scan(), "ABC-404", "ABC-404") == ["ABC-404"]


# rule: CON-027
def test_ep_027_10_keys_are_case_sensitive(env):
    """EP-027-10 (CI-027-10), data half."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.nomain("ABC-5")
    w.flush()
    assert unknown(scan(), "abc-1", "ABC-9") == ["abc-1"]


# rule: CON-027
def test_ep_027_11_spawn_without_result_does_not_make_a_key_known(env):
    """EP-027-11 (CI-027-11), data half."""
    w = W(env)
    w.main("S1", "ABC-9")
    w.sub("S1", None, file=False, err=None, desc="[ABC-7] x")
    w.flush()
    assert unknown(scan(), "ABC-7", "ABC-9") == ["ABC-7"]


# rule: CON-027
def test_ep_027_12_old_data_makes_a_key_known(env):
    """EP-027-12 (CI-027-12), data half: records from March are still data."""
    w = W(env, day="2026-03-01")
    w.nomain("ABC-8")
    w.flush()
    st = scan()
    assert data(st, "ABC-8")["runs"]["total"] == 1 and unknown(st, "ABC-8", "ABC-9") == []


# =====================================================================================================
# CON-028 / CON-030 / CON-035  same key twice, JSON shape
# =====================================================================================================

def numeric_leaves(d):
    for v in d.values():
        if isinstance(v, dict):
            if set(v) == {"diff", "ratio"}:
                yield v
            else:
                yield from numeric_leaves(v)


# rule: CON-028
def test_ep_028_01_same_key_twice_has_zero_differences(env):
    """EP-028-01 (CI-028-01)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(500, 0)))
    w.sub("S1", "ABC-1", [(20, usage(1000, 0))])
    w.flush()
    t = tree(scan(), "ABC-1", "ABC-1")
    assert t["a"] == t["b"]
    leaves = list(numeric_leaves(t["diff"]))
    assert leaves and all(v["diff"] == 0 or v["diff"] == "n/a" for v in leaves)
    assert t["diff"]["runs"]["total"] == {"diff": 0, "ratio": 1.0}
    assert t["diff"]["tokens"]["total"]["input"] == {"diff": 0, "ratio": 1.0}


# rule: CON-028
def test_bva_014_zero_figure_has_ratio_n_a(env):
    """BVA-014 (CI-028-02): 0 / 0 is n/a, 1 / 1 is 1."""
    w = W(env, SONNET, filler_model=SONNET_MODEL)
    w.main("S1", "EXP1-100")
    w.sub("S1", "EXP1-100", [w.text(20, "done", agent="a1")], agent="a1")
    w.flush()
    t = tree(scan(), "EXP1-100", "EXP1-100")
    assert t["diff"]["runs"]["failed"] == {"diff": 0, "ratio": "n/a"}
    assert t["diff"]["cost_usd"]["unpriced_messages"] == {"diff": 0, "ratio": "n/a"}
    assert t["diff"]["runs"]["total"] == {"diff": 0, "ratio": 1} and t["a"] == t["b"]


def pair_world(w):
    w.main("S1", "ABC-1", w.asst(5, usage(1500, 0)))
    w.sub("S1", "ABC-1", [(20, usage(1000, 0))])
    w.nomain("ABC-4")
    w.flush()
    return scan()


# rule: CON-030
def test_ep_030_01_json_is_sorted_and_versioned(env):
    """EP-030-01 (CI-030-01), data half: to_json is json.dumps(sort_keys=True, indent=2), no trailing newline."""
    t = tree(pair_world(W(env)), "ABC-1", "ABC-9")
    out = cmp_mod().to_json(t)
    assert json.dumps(json.loads(out), sort_keys=True, indent=2) == out and not out.endswith("\n")
    assert set(t) == {"a", "b", "diff", "version"} and t["version"] == 1


# rule: CON-030
def test_ep_030_02_same_data_same_bytes(env):
    """EP-030-02 (CI-030-02)."""
    st = pair_world(W(env))
    cmp = cmp_mod()
    assert cmp.to_json(tree(st, "ABC-1", "ABC-9")) == cmp.to_json(tree(st, "ABC-1", "ABC-9"))


# rule: CON-030
def test_ep_030_03_value_types(env):
    """EP-030-03 (CI-030-03): ints, floats and labels after json.loads; nothing rounded."""
    w = W(env)
    w.main("S9", "ABC-9", w.asst(5, usage(1500, 0), "S9"))
    for _ in range(2):
        w.sub("S9", "ABC-9", [(20, usage(10, 0))])
    w.sub("S9", "ABC-1", [(30, usage(1000, 0)), (31, usage(10, 0), "zzz-unpriced")])
    w.flush()
    t = json.loads(cmp_mod().to_json(tree(scan(), "ABC-1", "ABC-9")))
    a, b = t["a"], t["b"]
    assert isinstance(a["key"], str) and isinstance(a["main_sessions"], int)
    assert all(isinstance(a["runs"][k], int) for k in ("total", "failed", "repeat_rounds"))
    for part in ("total", "main"):
        for k in KEYS4:
            if part == "total" or isinstance(a["tokens"][part], dict):
                assert isinstance(a["tokens"][part][k], int)
    assert a["tokens"]["main"] == NO_MAIN and isinstance(b["tokens"]["main"], dict)
    assert isinstance(a["cost_usd"]["total"], float) and all(isinstance(v, float) for v in a["cost_usd"]["by_model"].values())
    assert isinstance(a["cost_usd"]["unpriced_messages"], int)
    assert isinstance(a["time_s"]["wall"], float) and isinstance(a["time_s"]["active_role"], float)
    assert isinstance(a["time_s"]["wait"], str) and isinstance(b["time_s"]["wait"], float)
    assert isinstance(a["cost_share"], str) and isinstance(b["cost_share"], float)


# rule: CON-030
def test_ep_030_05_leaf_paths_snapshot(env):
    """EP-030-05 (CI-030-05): the exact set of key paths."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.main("S2", "ABC-2", w.asst(5, usage(10, 0), "S2"))
    w.flush()
    t = tree(scan(), "ABC-1", "ABC-2")
    assert set(t) == {"a", "b", "diff", "version"}
    side = {"key", "main_sessions", "runs.total", "runs.failed", "runs.repeat_rounds", "cost_usd.total", "cost_usd.main",
            "cost_usd.unpriced_messages", "cost_usd.by_model.m-one", "time_s.wall", "time_s.active_role", "time_s.wait",
            "time_s.wait_over_2h", "cost_share"}
    side |= {f"tokens.{part}.{k}" for part in ("total", "main", "by_model.m-one") for k in KEYS4}
    assert paths(t["a"]) == side and paths(t["b"]) == side
    assert {p.removesuffix(".diff").removesuffix(".ratio") for p in paths(t["diff"])} == side - {"key"}
    assert all(set(v) == {"diff", "ratio"} for v in numeric_leaves(t["diff"]))


# rule: CON-035
def test_ep_035_02_no_log_text_in_the_json(env):
    """EP-035-02 (CI-035-02), data half: prompts, tool input and results, sub-agent text never reach the tree."""
    w = W(env)
    w.main("S1", "ABC-1", w.prompt(1, "[ABC-1] go SENT-USER-9f3a"), w.text(2, "SENT-ASSIST-9f3a"), w.use(3, "b1", command="SENT-TOOLIN-9f3a"),
           w.res("b1", 4, text="SENT-TOOLRES-9f3a"))
    w.sub("S1", "ABC-1", [w.text(20, "SENT-SUBTEXT-9f3a", agent="a1")], agent="a1", prompt="SENT-PROMPT-9f3a")
    w.nomain("ABC-5")
    w.flush()
    out = cmp_mod().to_json(tree(scan(), "ABC-1", "ABC-9"))
    assert "SENT-" not in out and '"ABC-1"' in out


# rule: CON-019
def test_d1_confirm_zero_token_message_under_unpriced_model_counts(env):
    """D1-confirm (Q-042, answer 8): a message with five zero counts under an unpriced model still counts as unpriced and lists its model with cost 0."""
    w = W(env, filler_model="zzz-unpriced")
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1")
    d = go(w)
    c = d["cost_usd"]
    assert c["unpriced_messages"] == 1
    assert c["by_model"] == {"zzz-unpriced": pytest.approx(0.0)} and c["total"] == pytest.approx(0.0)


# rule: CON-014, CON-015
@pytest.mark.parametrize("err, failed", [(False, 0), (True, 1)])
def test_g1_confirm_spawn_result_only_in_later_copy(env, err, failed):
    """CON-014/015: the same spawn id in two files, the tool_result only in the later copy: the spawn is counted, failed when that result is_error."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=None, tid="tu1", spawn_n=100)
    w.main("S2", "ABC-1")
    w.sub("S2", "ABC-1", file=False, err=err, tid="tu1", spawn_n=200, res_n=250)
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == failed


# rule: CON-014, CON-015
def test_g2_confirm_spawn_result_without_timestamp_still_counts(env):
    """CON-014, CON-015: a spawn whose tool_result record has no timestamp is still a counted spawn."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=False, tid="tu1")
    w.flush()
    path = w.main_path("S1")
    recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    res = [r for r in recs if isinstance(r.get("message", {}).get("content"), list)
           and any(b.get("type") == "tool_result" for b in r["message"]["content"])]
    assert len(res) == 1
    del res[0]["timestamp"]
    write_jsonl(path, recs)
    d = data(scan(), "ABC-1")
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# =====================================================================================================
# Pins for mutations that survived the first test set
# =====================================================================================================

def _spawn_world(w, writes, spawns):
    """Main S1 with no key of its own; Write records (t, key) give path evidence; spawns (n, tid) have no run file and an error result."""
    w.main("S1", None)
    for i, (n, key) in enumerate(writes):
        w.add("S1", w.use(n, f"w{i}", "Write", file_path=f"/work/app/docs/{key}-notes.md", content="x"))
    for n, tid in spawns:
        w.sub("S1", None, file=False, err=True, tid=tid, spawn_n=n, res_n=n + 5)


# rule: CON-014
def test_bva_002_spawn_key_is_the_newest_evidence_at_or_before_the_spawn(env):
    """BVA-002 (CI-014-08, Q-040): evidence key changes at 60 s; spawns at 59 (old key), 60 (same instant: new key), 61 (new key)."""
    w = W(env)
    _spawn_world(w, [(10, "EXP1-201"), (60, "EXP1-202")], [(59, "sp1"), (60, "sp2"), (61, "sp3")])
    w.flush()
    st = scan()
    a, b = data(st, "EXP1-201"), data(st, "EXP1-202")
    assert (a["runs"]["total"], a["runs"]["failed"], a["runs"]["repeat_rounds"]) == (1, 1, 0)
    assert (b["runs"]["total"], b["runs"]["failed"], b["runs"]["repeat_rounds"]) == (2, 2, 1)


# rule: CON-014
def test_bva_002b_same_timestamp_evidence_smaller_key_wins(env):
    """BVA-002 tie (Q-040): two keys written at the same second; a later spawn takes the smaller key."""
    w = W(env)
    _spawn_world(w, [(10, "EXP1-206"), (10, "EXP1-205")], [(20, "sp1")])
    w.flush()
    st = scan()
    assert data(st, "EXP1-205")["runs"]["total"] == 1
    assert data(st, "EXP1-206")["runs"]["total"] == 0


# rule: CON-015
def test_con_015_records_of_one_message_id_are_one_turn(env):
    """CON-015 (Q-044, Q-050): a handback record and a Bash record with the same message id are one turn; it holds a handback, so failed 0 (unmerged, the last turn is Bash only)."""
    w = W(env)
    one_sub(w, [w.prompt(10, "task", agent="a1"),
                w.asst(20, None, agent="a1", mid="M", blocks=[tool_use("h1", "SubagentHandback", message="done")]),
                w.asst(21, None, agent="a1", mid="M", blocks=[tool_use("x1", "Bash", command="ls")])])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_con_015_records_of_two_message_ids_are_two_turns(env):
    """Control of the one-turn test (Q-044, Q-050): the same records with two message ids end on a Bash-only turn, so the run failed."""
    w = W(env)
    one_sub(w, [w.prompt(10, "task", agent="a1"),
                w.asst(20, None, agent="a1", mid="M", blocks=[tool_use("h1", "SubagentHandback", message="done")]),
                w.asst(21, None, agent="a1", mid="N", blocks=[tool_use("x1", "Bash", command="ls")])])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


def _raw_main(w, sess, recs):
    """Write a main file in the given order (flush() would sort records without a timestamp to the front)."""
    write_jsonl(w.main_path(sess), recs)


# rule: CON-022
def test_con_022_a_task_notification_without_origin_ends_no_gap(env):
    """CON-022: typed 0, stop 100, a no-origin <task-notification> at 400, typed 1000 -> the gap runs to 1000: 900."""
    w = W(env)
    w.main("S1", "ABC-1", w.stop(100), w.prompt(400, "<task-notification>done</task-notification>"), w.typed(1000))
    assert wait_of(w) == 900


# rule: CON-022
def test_con_022_b_message_id_alone_does_not_make_two_stops_one(env):
    """CON-022: two files, stops with the same message id, no requestId, different uuids and times: two gaps, 300 + 500."""
    w = W(env)
    w.mains["S1"] = [w.prompt(0, "[ABC-1] go"), w.stop(100, mid="mX", uuid="uA"), w.typed(400)]
    w.mains["S2"] = [w.prompt(0, "[ABC-1] go", "S2"), w.stop(1000, "S2", mid="mX", uuid="uB"), w.typed(1500, "S2")]
    assert wait_of(w) == 800


# rule: CON-022
def test_con_022_c_a_gap_end_without_timestamp_still_closes_its_stop(env):
    """CON-022: stop 100, a typed record with no timestamp (gap end, no gap), typed 1000 adds nothing; stop 2000, typed 2500 -> 500."""
    w = W(env)
    nots = w.typed(0)
    del nots["timestamp"]
    _raw_main(w, "S1", [w.prompt(0, "[ABC-1] go"), w.stop(100), nots, w.typed(1000), w.stop(2000), w.typed(2500)])
    assert wait_of(w) == 500


# rule: CON-022
def test_con_022_d_a_stop_without_timestamp_adds_no_gap(env):
    """CON-022: a stop with no timestamp, typed 400 -> no gap; stop 1000, typed 1300 -> 300."""
    w = W(env)
    s0 = w.stop(100)
    del s0["timestamp"]
    _raw_main(w, "S1", [w.prompt(0, "[ABC-1] go"), s0, w.typed(400), w.stop(1000), w.typed(1300)])
    assert wait_of(w) == 300


# rule: CON-015
def test_b1_confirm_handback_then_its_tool_result_is_not_failed(env):
    """CON-015 (Q-047): the handback's own tool_result, not an error, last in the file, keeps the final reply."""
    w = W(env)
    one_sub(w, [w.use(20, "h1", "SubagentHandback", agent="a1", message="report"), w.res("h1", 25)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_b1_tool_result_after_a_non_handback_turn_is_failed(env):
    """CON-015 control (Q-046): a tool_result after a Bash tool_use, nothing after, is no final reply."""
    w = W(env)
    one_sub(w, [w.use(20, "x1", "Bash", agent="a1"), w.res("x1", 25)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_b1_handback_error_result_is_failed(env):
    """CON-015 (Q-048): the handback's own tool_result with is_error true is no final reply: the run is failed."""
    w = W(env)
    one_sub(w, [w.use(20, "h1", "SubagentHandback", agent="a1", message="report"), w.res("h1", 25, err=True)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


def b2_turn(w, hb_err=False, bash_err=False, one_record=True):
    """CON-015: one turn (same message id) holding a SubagentHandback and a parallel Bash tool_use, then the results."""
    hb = w.res("h1", 25, err=hb_err)
    bash = w.res("x1", 25, err=bash_err)
    if one_record:
        hb["message"]["content"] += bash["message"]["content"]
        results = [hb]
    else:
        results = [hb, bash]
    return [w.asst(20, None, agent="a1", mid="M", blocks=[tool_use("h1", "SubagentHandback", message="report")]),
            w.asst(21, None, agent="a1", mid="M", blocks=[tool_use("x1", "Bash", command="ls")])] + results


# rule: CON-015
def test_b2_handback_and_bash_results_in_one_record_not_failed(env):
    """CON-015 (Q-049): handback and parallel Bash results in one user record, none is_error: not failed."""
    w = W(env)
    one_sub(w, b2_turn(w))
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_b2_handback_and_bash_results_in_separate_records_not_failed(env):
    """CON-015 (Q-049): the two results in two user records, none is_error: not failed."""
    w = W(env)
    one_sub(w, b2_turn(w, one_record=False))
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_b2_other_tool_error_next_to_handback_not_failed(env):
    """CON-015 (Q-049): the Bash result is_error, the handback result is not: not failed."""
    w = W(env)
    one_sub(w, b2_turn(w, bash_err=True, one_record=False))
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 0


# rule: CON-015
def test_b2_handback_error_next_to_bash_is_failed(env):
    """CON-015 (Q-048/Q-049): the handback result is_error: failed."""
    w = W(env)
    one_sub(w, b2_turn(w, hb_err=True, one_record=False))
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# =====================================================================================================
# Pins for mutations that survived the second test set
# =====================================================================================================

# rule: CON-022
@pytest.mark.parametrize("text, err", [(None, True), (DENIED, True), (DISMISSED, False)],
                         ids=["ordinary-error", "denied-error", "marker-text-no-error"])
def test_con_022_only_a_rejected_prompt_result_is_a_stop(env, text, err):
    """CON-022 (v12): a rejected-prompt stop needs is_error AND the marker text; an ordinary error result, a "denied" text
    or the marker on a non-error result after a Bash tool_use is no stop, so no gap: wait 0."""
    w = W(env)
    w.main("S1", "ABC-1", w.use(100, "bash1", "Bash", command="x"), w.res("bash1", 140, err, text=text), w.typed(1000))
    assert wait_of(w) == 0


# rule: CON-022
def test_con_022_earliest_gap_end_wins_when_it_is_in_the_later_file(env):
    """CON-022 (Q-033): one stop (same uuid) in two files; S1 copy ends 450, S2 copy ends 400: the earliest end counts, 300."""
    w = W(env)
    w.mains["S1"] = [w.prompt(0, "[ABC-1] go"), w.stop(100, uuid="uS"), w.typed(450)]
    w.mains["S2"] = [w.prompt(0, "[ABC-1] go", "S2"), w.stop(100, "S2", uuid="uS"), w.typed(400, "S2")]
    assert wait_of(w) == 300


# rule: CON-014, CON-015
def test_con_015_an_error_in_any_copy_with_a_result_fails_the_spawn(env):
    """CON-014/015: the same spawn id in two files, copy 1 has a non-error result, copy 2 an error result: failed 1."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", file=False, err=False, tid="tu1", spawn_n=100)
    w.main("S2", "ABC-1")
    w.sub("S2", "ABC-1", file=False, err=True, tid="tu1", spawn_n=200, res_n=250)
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# =====================================================================================================
# CON-015 (Q-050) and CON-022 (Q-051)
# =====================================================================================================

def text_use(w, n, tid, name="Bash", **inp):
    """One last turn: a text block and a tool_use block in the same record."""
    return w.asst(n, None, agent="a1", blocks=[{"type": "text", "text": "working on it"}, tool_use(tid, name, **(inp or {"command": "ls"}))])


# rule: CON-015
def test_con_015_q050_text_and_open_tool_use_is_failed(env):
    """CON-015 (Q-050 case 1): the last turn has text and a Bash tool_use, the file ends on the open tool_use: failed 1."""
    w = W(env)
    one_sub(w, [text_use(w, 20, "x1")])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_con_015_q050_text_and_tool_use_then_its_result_is_failed(env):
    """CON-015 (Q-050 case 2): text + Bash tool_use, then its result, file ends: failed 1."""
    w = W(env)
    one_sub(w, [text_use(w, 20, "x1"), w.res("x1", 25)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_con_015_q050_handback_then_new_text_bash_turn_is_failed(env):
    """CON-015 (Q-050): a handback turn and its result, then a new text + Bash turn and its result: failed 1
    (the handback ids of the earlier turn do not carry over to the new turn)."""
    w = W(env)
    one_sub(w, [w.use(20, "h1", "SubagentHandback", agent="a1", message="report"), w.res("h1", 22),
                text_use(w, 30, "x2"), w.res("x2", 35)])
    d = go(w)
    assert d["runs"]["total"] == 1 and d["runs"]["failed"] == 1


# rule: CON-015
def test_con_015_q050_controls_text_only_and_handback_next_to_bash_are_not_failed(env):
    """CON-015 controls: a text-only last turn after a tool result: failed 0 (Q-050 does not touch it); a handback turn next to
    a Bash call, with the Bash result last (Q-049): failed 0."""
    w = W(env)
    w.main("S1", "ABC-1")
    w.sub("S1", "ABC-1", [w.use(20, "x1", agent="a1"), w.res("x1", 25), w.text(30, "done", agent="a1")], agent="a1", tid="tu1", spawn_n=10)
    both = w.asst(20, None, agent="a2", blocks=[tool_use("h2", "SubagentHandback", message="report"), tool_use("b2", "Bash", command="ls")])
    w.sub("S1", "ABC-1", [both, w.res("b2", 25), w.res("h2", 26)], agent="a2", tid="tu2", spawn_n=11)
    d = go(w)
    assert d["runs"]["total"] == 2 and d["runs"]["failed"] == 0


# rule: CON-022
@pytest.mark.parametrize("origin", [{}, {"other": "x"}, "human", ["human"], None],
                         ids=["empty-dict", "dict-no-kind", "string", "list", "null"])
def test_con_022_q051_origin_without_kind_counts_as_typed(env, origin):
    """CON-022 (Q-051): a plain-text, not-isMeta user record whose origin is not an object or has no kind carries no
    origin marker, so it is typed and ends the gap: stop at 100, record at 200, typed at 500 -> wait exactly 100."""
    w = W(env)
    assert gap_world(w, [user_x(w, "please continue", origin=origin)]) == 100


# ---- spawn with a run file and no readable meta (CON-014, CON-015, CON-016)

def _meta(sub):
    return sub.path.with_name(sub.path.stem + ".meta.json")


# rule: CON-014
@pytest.mark.parametrize("how", ["removed", "unreadable"])
@pytest.mark.parametrize("err", [False, True], ids=["ok-result", "error-result"])
def test_spawn_with_run_file_and_no_meta_counts_once(env, how, err):
    """CON-014, CON-015, CON-016: the run file exists but its meta is missing or unreadable: the spawn is not also a spawn
    with no run file. total 1, failed 0, repeat_rounds 0 (an error result alone does not fail a run)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    sub = w.sub("S1", "ABC-1", [w.prompt(15, "[ABC-1] build", "S1", agent="AG1"), (20, usage(1000, 0))],
                agent="AG1", spawn_n=10, res_n=40, err=err)
    w.flush()
    _meta(sub).unlink() if how == "removed" else _meta(sub).write_text("{")
    d = data(scan(), "ABC-1")
    assert (d["runs"]["total"], d["runs"]["failed"], d["runs"]["repeat_rounds"]) == (1, 0, 0)


# rule: CON-014
def test_unlinked_file_does_not_take_a_denied_spawn(env):
    """CON-014, CON-016 guard: a run file starting after a denied spawn's window does not pair with it: total 2, failed 1, repeat_rounds 1."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.sub("S1", "ABC-1", file=False, err=True, spawn_n=10, res_n=11)
    sub = w.sub("S1", "ABC-1", [w.prompt(15, "[ABC-1] build", "S1", agent="AG1"), (20, usage(1000, 0))],
                agent="AG1", spawn_n=12, res_n=40)
    w.flush()
    _meta(sub).unlink()
    d = data(scan(), "ABC-1")
    assert (d["runs"]["total"], d["runs"]["failed"], d["runs"]["repeat_rounds"]) == (2, 1, 1)


# ---- compact-summary user records (CON-022)

# rule: CON-022
def test_con_022_compact_summary_record_ends_no_gap(env):
    """CON-022: stop 100, a no-origin, not-isMeta user record with isCompactSummary and isVisibleInTranscriptOnly and plain
    text at 200, typed 500 -> the gap runs to 500: 400 (not 100)."""
    w = W(env)
    r = user_x(w, "This session is being continued from a previous conversation", isCompactSummary=True, isVisibleInTranscriptOnly=True)
    assert gap_world(w, [r]) == 400


# rule: CON-022
def test_con_022_visible_in_transcript_only_alone_ends_no_gap(env):
    """CON-022: the same record with only isVisibleInTranscriptOnly true ends no gap: 400 (not 100)."""
    w = W(env)
    r = user_x(w, "please continue", isVisibleInTranscriptOnly=True)
    assert gap_world(w, [r]) == 400


# rule: CON-022
def test_con_022_next_typed_message_closes_the_gap_after_a_compact_summary(env):
    """CON-022: stop 100, compact summary 200 (no gap end), typed 500 closes the gap from 100: 400; a second stop 600 and
    typed 900 add 300 -> 700."""
    w = W(env)
    r = user_x(w, "summary text", isCompactSummary=True, isVisibleInTranscriptOnly=True)
    w.main("S1", "ABC-1", w.stop(100), r, w.typed(500), w.stop(600), w.typed(900))
    assert wait_of(w) == 700


# ---- the CON-014 fallback pairing clauses (Q-053)

def _unlinked(w, sess, key, agent, n, role="builder"):
    """A sub file with no tool_use_id in its meta, starting at second n of `sess`, with no spawn record of its own."""
    sub = w.sub(sess, key, [w.prompt(n, f"[{key}] build", sess, agent=agent), (n + 5, usage(1000, 0))],
                role=role, agent=agent, spawn=False)
    _meta(sub).unlink()
    return sub


# rule: CON-014
def test_fallback_does_not_pair_across_sessions(env):
    """CON-014 (Q-053): the unlinked file of session S2 starts inside the window of a spawn of session S1: no pairing.
    The spawn stays a spawn with no run file and the file stays a run: total 2."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.main("S2", "ABC-1", w.asst(5, usage(10, 0), "S2"))
    w.sub("S1", "ABC-1", file=False, err=False, spawn_n=10, res_n=40)
    _unlinked(w, "S2", "ABC-1", "AG2", 15)
    d = go(w)
    assert d["runs"]["total"] == 2


# rule: CON-014
def test_fallback_takes_the_earliest_spawn_of_overlapping_windows(env):
    """CON-014 (Q-053): two spawns whose windows both hold the file start: the earlier call is taken (role builder, ABC-1),
    the later one (role tester, ABC-2) stays alone. With a linked builder run: total 2, repeat_rounds 1."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.sub("S1", "ABC-1", file=False, err=False, role="builder", spawn_n=10, res_n=40)
    w.sub("S1", "ABC-2", file=False, err=False, role="tester", spawn_n=12, res_n=41)
    w.sub("S1", "ABC-1", [(60, usage(10, 0))], role="builder", spawn=True, spawn_n=50, res_n=70)
    _unlinked(w, "S1", "ABC-1", "AG1", 15)
    d = go(w)
    assert (d["runs"]["total"], d["runs"]["repeat_rounds"]) == (2, 1)


# rule: CON-014
def test_fallback_is_one_to_one(env):
    """CON-014 (Q-053): two unlinked files start inside the window of one spawn (role builder): the first takes it, the second
    stays a run with its own role. total 2, repeat_rounds 0 (the spawn is not counted twice, the role not given twice)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.sub("S1", "ABC-1", file=False, err=False, role="builder", spawn_n=10, res_n=40)
    _unlinked(w, "S1", "ABC-1", "AG1", 15)
    _unlinked(w, "S1", "ABC-1", "AG2", 20)
    d = go(w)
    assert (d["runs"]["total"], d["runs"]["repeat_rounds"]) == (2, 0)


# rule: CON-014
def test_fallback_window_uses_the_earliest_copy_with_a_result(env):
    """CON-014 (Q-054): one spawn copied into a resumed file; copy 1 has its result at 40, copy 2 at 30. The window is the
    earliest copy's (10..40), so the unlinked file of the session starting at 35 pairs with it: total 1 (latest-wins gives 2)."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.sub("S1", "ABC-1", file=False, err=False, tid="tu1", spawn_n=10, res_n=40)
    w.main("S2", "ABC-1", w.asst(5, usage(10, 0), "S2"))
    w.sub("S2", "ABC-1", file=False, err=False, tid="tu1", spawn_n=10, res_n=30)
    _unlinked(w, "S1", "ABC-1", "AG1", 35)
    d = go(w)
    assert d["runs"]["total"] == 1


# rule: CON-003
def test_meta_role_wins_over_the_fallback_spawn_role(env):
    """CON-003 (Q-053): a file whose meta has a role but no tool_use_id is paired by the fallback with a builder spawn; its
    role stays the meta role (tester). With a linked builder run: repeat_rounds 0."""
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    sub = w.sub("S1", "ABC-1", [w.prompt(15, "[ABC-1] build", "S1", agent="AG1"), (20, usage(1000, 0))],
                role="builder", agent="AG1", spawn_n=10, res_n=40)
    _meta(sub).write_text(json.dumps({"agentType": "tester", "spawnDepth": 1}))
    w.sub("S1", "ABC-1", [(60, usage(10, 0))], role="builder", spawn_n=50, res_n=70)
    d = go(w)
    assert (d["runs"]["total"], d["runs"]["repeat_rounds"]) == (2, 0)


# ---------------------------------------------------------------- code review 6: malformed records read as absent (BD4, Q-057)

def _log(tmp_path, records, tail=""):
    p = tmp_path / "log.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records) + tail)
    return str(p)


def _stop(t=5, **kw):
    r = assistant("m-stop", t=t, **kw)
    r["message"]["stop_reason"] = "end_turn"
    return r


def _span(gaps):
    return [(g.uuid, g.reply, g.end - g.start) for g in gaps]


# rule: CON-015
def test_run_failed_a_list_message_id_never_merges_two_turns(tmp_path):
    """Review 6, 1: two records with the same list message.id are two turns: a tool call then a text-only reply -> not failed."""
    a = assistant("x", t=1, blocks=[tool_use("tb", "Bash", command="ls")])
    b = assistant("x", t=2, blocks=[{"type": "text", "text": "done"}])
    a["message"]["id"] = b["message"]["id"] = ["same"]
    assert importlib.import_module("agent_console.compare").run_failed(_log(tmp_path, [a, b])) is False


# rule: CON-015
def test_run_failed_a_list_handback_tool_use_id_and_a_list_tool_use_id_result(tmp_path):
    """Review 6, 1: a SubagentHandback call with a list id, then a non-error result with a list tool_use_id -> the final reply stands, not failed."""
    a = assistant("h", t=1, blocks=[{"type": "text", "text": "report"}, tool_use(["hb"], "SubagentHandback", message="m")])
    r = tool_result(["hb"], err=False, t=2)
    assert importlib.import_module("agent_console.compare").run_failed(_log(tmp_path, [a, r])) is False


# rule: CON-015
def test_run_failed_a_100000_deep_line_is_skipped(tmp_path):
    """Review 6, 1: a line nested 100000 deep is skipped like any bad line; the reply before it still stands -> not failed; a tool call before it -> failed."""
    compare = importlib.import_module("agent_console.compare")
    deep = "[" * 100000 + "]" * 100000 + "\n"
    reply = assistant("r", t=1)
    assert compare.run_failed(_log(tmp_path, [reply], tail=deep)) is False
    tool = assistant("t", t=1, blocks=[tool_use("tb", "Bash", command="ls")])
    assert compare.run_failed(_log(tmp_path, [tool], tail=deep)) is True


# rule: CON-022
def test_file_gaps_a_list_message_id_uuid_tool_ids_are_read_as_absent(tmp_path):
    """Review 6, 1: a stop with list message.id and list uuid, a tool call with a list id and its result with a list tool_use_id,
    then a typed prompt 2995 s later -> exactly one plain gap of 2995.0 s."""
    stop = _stop(t=5, requestId="req-1")
    stop["message"]["id"] = ["m"]
    stop["uuid"] = ["u"]
    call = assistant("c", t=20, blocks=[tool_use(["tb"], "Bash", command="ls")])
    res = tool_result(["tb"], err=False, t=25)
    late = user_prompt("go on", t=3000)
    gaps = importlib.import_module("agent_console.compare").file_gaps(_log(tmp_path, [user_prompt("start", t=0), stop, call, res, late]))
    assert _span(gaps) == [(None, None, 2995.0)]


# rule: CON-022
def test_file_gaps_a_list_tool_use_id_of_a_rejected_result_is_read_as_absent(tmp_path):
    """Review 6, 1: a rejected result whose tool_use_id is a list stops nothing: a reply that is no stop, no gap."""
    call = assistant("c", t=5, blocks=[tool_use("tb", "Bash", command="ls")])
    res = tool_result(["tb"], err=True, t=8)
    res["message"]["content"][0]["content"] = DISMISSED
    gaps = importlib.import_module("agent_console.compare").file_gaps(_log(tmp_path, [user_prompt("start", t=0), call, res, user_prompt("go", t=3000)]))
    assert gaps == []


# rule: CON-022
def test_file_gaps_an_ask_user_question_with_a_list_id_and_a_list_answer_id_gives_the_one_gap(tmp_path):
    """Review 7, 4: AskUserQuestion with id ["q"], a non-error result with tool_use_id ["q"] at t=50, a typed prompt at t=3000
    -> the ids are read as absent, the result ends no gap, the prompt ends the one gap: exactly [(uuid, None, 2995.0)]."""
    ask = assistant("a", t=5, blocks=[tool_use(["q"], "AskUserQuestion", question="which?")])
    ans = tool_result(["q"], err=False, t=50)
    gaps = importlib.import_module("agent_console.compare").file_gaps(_log(tmp_path, [user_prompt("start", t=0), ask, ans, user_prompt("go", t=3000)]))
    assert _span(gaps) == [(ask["uuid"], None, 2995.0)]


# rule: CON-022
def test_file_gaps_a_rejected_result_with_a_list_id_for_an_ask_user_question_gives_the_one_gap(tmp_path):
    """Review 7, 4: the same, the result at t=50 a rejected one (is_error, dismissed text) with tool_use_id ["q"] -> exactly [(uuid, None, 2995.0)]."""
    ask = assistant("a", t=5, blocks=[tool_use(["q"], "AskUserQuestion", question="which?")])
    res = tool_result(["q"], err=True, t=50)
    res["message"]["content"][0]["content"] = DISMISSED
    later = assistant("b", t=3010, blocks=[tool_use(["bq"], "Bash", command="ls")])   # a list id is no id: this call is no stop, so the prompt after it ends no gap
    gaps = importlib.import_module("agent_console.compare").file_gaps(
        _log(tmp_path, [user_prompt("start", t=0), ask, res, user_prompt("go", t=3000), later, user_prompt("more", t=3500)]))
    assert _span(gaps) == [(ask["uuid"], None, 2995.0)]


# rule: CON-022
def test_file_gaps_a_numeric_timestamp_gives_no_gap(tmp_path):
    """Review 6, 1: a stop with a numeric timestamp, or a prompt with a numeric timestamp, has no time: no gap; a good pair still gives 2995.0."""
    compare = importlib.import_module("agent_console.compare")
    stop = _stop(t=5)
    stop["timestamp"] = 12345
    assert compare.file_gaps(_log(tmp_path, [stop, user_prompt("go", t=3000)])) == []
    late = user_prompt("go", t=3000)
    late["timestamp"] = 12345
    assert compare.file_gaps(_log(tmp_path, [_stop(t=5), late])) == []
    assert _span(compare.file_gaps(_log(tmp_path, [_stop(t=5), user_prompt("go", t=3000)]))) == [("u-m-stop-0", None, 2995.0)]


# rule: CON-022
def test_file_gaps_a_100000_deep_line_is_skipped(tmp_path):
    """Review 6, 1: a line nested 100000 deep between a stop and the prompt is skipped; the gap is exactly 2995.0 s."""
    deep = "[" * 100000 + "]" * 100000 + "\n"
    p = tmp_path / "log.jsonl"
    p.write_text(json.dumps(_stop(t=5)) + "\n" + deep + json.dumps(user_prompt("go", t=3000)) + "\n")
    gaps = importlib.import_module("agent_console.compare").file_gaps(str(p))
    assert _span(gaps) == [("u-m-stop-0", None, 2995.0)]
