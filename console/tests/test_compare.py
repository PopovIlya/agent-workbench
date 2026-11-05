"""Ticket comparison (EXP1-KITC): the `compare` CLI subcommand and the /compare page.

The rules fix the numbers and the wording, not the JSON field names. So the tests look for raw numbers anywhere in the JSON
(`nums`), or under a model (`under`), or under a path that names the figure (`nums_at`), and for the fixed phrases in the text
output and on the page. Logs are synthetic (conftest helpers). The CLI runs with AGENT_CONSOLE_PORT=1: before the change the old
`main()` ignores the arguments and tries to start the server on a port it cannot bind, so the test fails fast instead of hanging.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_console import config, server
from agent_console.pricing import Pricing
from agent_console.store import Store
from conftest import PROJECT, add_sub, assistant, flat_routes, tool_use, usage, user_prompt, write_jsonl

CONSOLE = Path(__file__).resolve().parents[1]
BASE = datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc)
OLD = datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
SONNET, HAIKU = "claude-sonnet-5-5", "claude-haiku-5-5"
A, B, C, D = "AAA-1", "BBB-2", "CCC-3", "DDD-4"
PRICES = """regional_multiplier: 1.0
models:
  sonnet-5-5: {input: 1000, output: 5000, cache_write_5m: 1250, cache_write_1h: 2000, cache_read: 100}
  haiku-5-5: {input: 100, output: 500, cache_write_5m: 125, cache_write_1h: 200, cache_read: 10}
tier_defaults: {}
"""
DENY1 = "Permission for this action has been denied. SENTINEL-DENY"
DENY2 = "The user doesn't want to proceed with this tool use. SENTINEL-DENY"
SENTINELS = ("SENTINEL-PROMPT", "SENTINEL-REPLY", "SENTINEL-DENY", "SENTINEL-ERROR")


# ---------- log builders ----------

def at(sec: float, base: datetime = BASE) -> str:
    return (base + timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def amsg(mid, sec, session, model=SONNET, u=None, blocks=None, stop="end_turn", agent=None, base=BASE, **extra):
    r = assistant(mid, model=model, u=u, blocks=blocks, session=session, agent=agent, **extra)
    r["timestamp"] = at(sec, base)
    r["message"]["stop_reason"] = stop
    return r


def human(sec, session, text="next", agent=None, base=BASE, origin=None):
    r = user_prompt(text, session=session, agent=agent)
    r["timestamp"] = at(sec, base)
    r["uuid"] = f"h-{session}-{agent}-{sec}"
    if origin:
        r["origin"] = {"kind": origin}
    return r


def result(tid, sec, session, text, err=False, string_result=False, base=BASE, agent=None):
    r = {"parentUuid": None, "type": "user", "uuid": f"tr-{tid}-{sec}", "timestamp": at(sec, base), "sessionId": session,
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": err, "content": text}]}}
    if string_result:
        r["toolUseResult"] = text
    if agent:
        r["agentId"], r["isSidechain"] = agent, True
    return r


class Sess:
    """One main session with its sub-agent runs; `write()` puts the files under the log root."""

    def __init__(self, env, sid, key=None, base=BASE, cwd="/work/app", prompt=None):
        self.env, self.sid, self.base, self.n = env, sid, base, 0
        text = prompt if prompt is not None else (f"[{key}] go" if key else "go")
        self.recs = [human(0, sid, text, base=base)]
        for r in self.recs:
            r["cwd"] = cwd
        self.subs: list = []
        self.refused = 0

    def mid(self):
        self.n += 1
        return f"{self.sid}-m{self.n}"

    def say(self, sec, model=SONNET, u=None, stop="end_turn", blocks=None, **extra):
        self.recs.append(amsg(self.mid(), sec, self.sid, model, u, blocks, stop, base=self.base, **extra))
        return self

    def human(self, sec, text="next", origin=None):
        self.recs.append(human(sec, self.sid, text, base=self.base, origin=origin))
        return self

    def raw(self, rec):
        self.recs.append(rec)
        return self

    def spawn(self, role, key, sec, dur=60, model=SONNET, u=None, stop="end_turn", blocks=None, tail=None, refuse=None, desc=None, **extra):
        k = len(self.subs) + 1
        agent = f"{self.sid}a{k}"
        tid = f"tu-{agent}"
        if refuse:
            self.refused += 1
            tid = f"tu-{agent}-r{self.refused}"   # unique per refused spawn: the index keeps one row per tool id
        d = desc if desc is not None else f"{key} work"
        self.recs.append(amsg(self.mid(), sec, self.sid, SONNET, usage(0, 0), [tool_use(tid, "Agent", subagent_type=role, description=d, prompt="p")], "tool_use", base=self.base))
        self.n += 0
        if refuse:
            self.recs.append(result(tid, sec + 1, self.sid, refuse, err=True, string_result=True, base=self.base))
            return self
        recs = [human(sec, self.sid, "SENTINEL-PROMPT do it", agent=agent, base=self.base),
                amsg(f"{agent}-m1", sec + dur, self.sid, model, u or usage(10, 10), blocks, stop, agent=agent, base=self.base, **extra)]
        recs += (tail(agent) if tail else [])
        self.subs.append((agent, role, recs, tid))
        return self

    def write(self):
        write_jsonl(self.env.root / PROJECT / f"{self.sid}.jsonl", self.recs)
        for agent, role, recs, tid in self.subs:
            add_sub(self.env.root, self.sid, agent, role, recs, tid)
        return self


def text_block(t="SENTINEL-REPLY done"):
    return [{"type": "text", "text": t}]


def main_only(env, sid, key, u, end=100, base=BASE, model=SONNET):
    return Sess(env, sid, key, base=base).say(end, model=model, u=u, blocks=text_block()).write()


def u(inp=0, out=0, cr=0, w5=0, w1=0):
    return usage(inp, out, cr=cr, cw=w5 + w1, w5=w5, w1=w1)


@pytest.fixture
def e(env):
    (env.tmp / "pricing.yaml").write_text(PRICES)
    return env


# ---------- runners and readers ----------

def cli(env, *args, text=False):
    envv = dict(os.environ, AGENT_CONSOLE_PORT="1")
    argv = [sys.executable, "-m", "agent_console", "compare", *args] + ([] if text or "--json" in args else ["--json"])
    try:
        return subprocess.run(argv, cwd=CONSOLE, env=envv, capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        pytest.fail("the CLI hung: the server started instead of the compare subcommand")


def cli_json(env, a, b):
    p = cli(env, a, b, "--json")
    assert p.returncode == 0, f"exit {p.returncode}: {p.stderr[-300:]}"
    return json.loads(p.stdout)


def cli_text(env, a, b):
    p = cli(env, a, b, text=True)
    assert p.returncode == 0, f"exit {p.returncode}: {p.stderr[-300:]}"
    return p.stdout


def page(env, a, b, host="127.0.0.1:8790"):
    st = Store()
    st.ingest()
    app = server.create_app(store=st, pricing=Pricing.load(config.pricing_path()), port=8790)
    return TestClient(app, base_url="http://127.0.0.1:8790"), app, st


def get_page(env, a, b):
    client, _, _ = page(env, a, b)
    return client.get("/compare", params={"a": a, "b": b})


def nums(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from nums(v)
    elif isinstance(o, list):
        for v in o:
            yield from nums(v)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield o


def nums_at(o, *words, path=""):
    """Numbers whose key path (lower case) holds every word."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from nums_at(v, *words, path=f"{path}/{k}".lower())
    elif isinstance(o, list):
        for v in o:
            yield from nums_at(v, *words, path=path)
    elif isinstance(o, (int, float)) and not isinstance(o, bool) and all(w in path for w in words):
        yield o


def under(o, needle):
    """Numbers inside the dict that names `needle` as a key or as a string value (a per-model block)."""
    out: list = []
    if isinstance(o, dict):
        for k, v in o.items():
            if needle in str(k):
                out += list(nums(v))
            elif isinstance(v, str) and needle in v:
                out += list(nums({kk: vv for kk, vv in o.items() if not isinstance(vv, str)}))
            out += under(v, needle)
    elif isinstance(o, list):
        for v in o:
            out += under(v, needle)
    return out


def has(values, x):
    return any(abs(v - x) <= 1e-6 * max(1.0, abs(x)) for v in values)


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p).encode() + p.read_bytes())
    return h.hexdigest()


def two_simple(env):
    """A: main 2.00 USD; B: main 5.00 USD (sonnet in=1000 out=200 / out=800)."""
    main_only(env, "SA", A, u(1000, 200))
    main_only(env, "SB", B, u(1000, 800))


# ---------- CON-027: entry points ----------

# rule: CON-027
def test_cli_compare_subcommand_gives_json(e):
    two_simple(e)
    data = cli_json(e, A, B)
    assert isinstance(data, dict) and data


# rule: CON-027
def test_page_is_a_server_rendered_route_outside_the_hash_app(e):
    two_simple(e)
    r = get_page(e, A, B)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert A in r.text and B in r.text
    assert "<script" not in r.text.lower() and "/static/ctq-" not in r.text   # no hash-router shell: the page itself holds the numbers
    assert r.headers["x-content-type-options"] == "nosniff" and "default-src 'self'" in r.headers["content-security-policy"]


# rule: CON-027
def test_no_argument_starts_the_server_and_compare_does_not(monkeypatch):
    import runpy

    called = []
    monkeypatch.setattr(server, "main", lambda: called.append("server"))
    monkeypatch.setattr("agent_console.compare.cli_main", lambda argv: called.append("cli") or 0)
    monkeypatch.setattr(sys, "argv", ["agent_console"])
    runpy.run_module("agent_console", run_name="__main__")
    assert called == ["server"]
    called.clear()
    monkeypatch.setattr(sys, "argv", ["agent_console", "compare", A, B])
    with pytest.raises(SystemExit):
        runpy.run_module("agent_console", run_name="__main__")
    assert called == ["cli"]


# rule: CON-027
def test_page_keeps_the_local_host_check(e):
    two_simple(e)
    client, _, _ = page(e, A, B)
    assert client.get("/compare", params={"a": A, "b": B}).status_code == 200   # the route exists ...
    assert client.get("/compare", params={"a": A, "b": B}, headers={"host": "evil.example.com"}).status_code == 404   # ... behind the host guard


# ---------- CON-028: exactly two keys, read-only ----------

# rule: CON-028
@pytest.mark.parametrize("args", [[A], [A, B, C]])
def test_cli_takes_exactly_two_keys(e, args):
    two_simple(e)
    p = cli(e, *args, "--json")
    assert p.returncode == 2 and p.stdout.strip() == ""


# rule: CON-028
def test_page_without_a_or_b_is_one_422_error(e):
    two_simple(e)
    client, _, _ = page(e, A, B)
    r = client.get("/compare", params={"a": A})
    assert r.status_code == 422


# rule: CON-028
def test_compare_is_read_only(e):
    two_simple(e)
    before = tree_hash(e.root)
    assert cli_json(e, A, B)
    client, app, _ = page(e, A, B)
    assert client.get("/compare", params={"a": A, "b": B}).status_code == 200
    routes = [r for r in flat_routes(app) if "compare" in r.path]
    assert routes and all(set(r.methods) <= {"GET", "HEAD"} for r in routes)
    assert tree_hash(e.root) == before


# ---------- CON-029: same key twice ----------

# rule: CON-029
def test_same_key_twice_compares_the_ticket_with_itself(e):
    main_only(e, "SA", A, u(1234, 0))
    data = cli_json(e, A, A)
    vals = list(nums(data))
    assert sum(1 for v in vals if v == 1234) >= 2   # the same tokens in both columns
    assert has(vals, 1.0) and has(vals, 0)           # ratio 1, difference 0


# ---------- CON-030: a ticket is its runs by effective key ----------

# rule: CON-030
def test_ticket_is_the_runs_by_effective_key_across_sessions(e):
    s1 = Sess(e, "S1", A).say(5, u=u(1234, 0))
    s1.spawn("builder", A, 10).spawn("reviewer", A, 100)
    s1.write()
    s2 = Sess(e, "S2", B).say(5, u=u(7777, 0))
    for i, role in enumerate(["planner", "builder", "reviewer", "tester"]):
        s2.spawn(role, B, 10 + 100 * i)
    s2.spawn("analyst", A, 600)   # 4 of 5 children carry B: the main session is B's; this one run is A's
    s2.write()
    data = cli_json(e, A, B)
    totals = list(nums_at(data, "run", "total"))
    assert has(totals, 3) and has(totals, 4)   # A: 2 + 1 foreign-session run; B: 4 (the main is no role run)


# ---------- CON-031: always all logs ----------

# rule: CON-031
def test_old_log_outside_scope_is_still_compared(e):
    main_only(e, "SOLD", A, u(4321, 0), base=OLD)
    s = Sess(e, "SB", B, base=OLD, cwd="/home/someone/unrelated-checkout").say(50, u=u(5, 0), blocks=text_block())
    s.write()
    data = cli_json(e, A, B)
    assert has(list(nums(data)), 4321)


# ---------- CON-032: unknown key ----------

# rule: CON-032
@pytest.mark.parametrize("a,b", [(A, "NOPE-9"), ("NOPE-9", A), ("NOPE-8", "NOPE-9")])
def test_cli_unknown_key_exits_2_and_names_it(e, a, b):
    two_simple(e)
    p = cli(e, a, b, "--json")
    assert p.returncode == 2
    assert "NOPE-" in (p.stdout + p.stderr) and "Traceback" not in p.stderr


# rule: CON-032
def test_page_unknown_key_is_a_clear_error(e):
    two_simple(e)
    r = get_page(e, A, "NOPE-9")
    assert 400 <= r.status_code < 500 and "NOPE-9" in r.text and "unknown" in r.text.lower()


# ---------- CON-033: role runs are sub-agent runs only ----------

# rule: CON-033
def test_main_session_is_not_a_role_run(e):
    s = Sess(e, "SA", A).say(5, u=u(100, 0), stop="tool_use")   # the main ends without a final reply: still not a failed role run
    s.spawn("builder", A, 10).spawn("reviewer", A, 100)
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "run", "total")), 2) and not has(list(nums_at(data, "run", "total")), 3)
    assert set(nums_at(data, "fail")) <= {0, -0.0, 0.0}
    assert set(nums_at(data, "repeat")) <= {0, 0.0}


# ---------- CON-034: repeat rounds ----------

# rule: CON-034
def test_repeat_round_is_any_later_run_of_the_same_role(e):
    s = Sess(e, "SA", A)
    for i in range(3):
        s.spawn("builder", A, 10 + 100 * i, blocks=text_block("FAIL: no"))   # a FAIL verdict makes no difference
    s.spawn("reviewer", A, 500).write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "repeat")), 2)
    assert has(list(nums_at(data, "run", "total")), 4)


# ---------- CON-035: failed runs ----------

def _api_assistant(agent):
    return [amsg("err-1", 300, "SA", "<synthetic>", usage(0, 0), [{"type": "text", "text": "SENTINEL-ERROR api"}], "stop_sequence", agent=agent,
                 isApiErrorMessage=True, apiErrorStatus=529)]


def _api_system(agent):
    r = {"type": "system", "subtype": "api_error", "timestamp": at(300), "sessionId": "SA", "error": {"message": "SENTINEL-ERROR x", "status": 500}}
    return [r]


def _denial(agent):
    return [result("bash-1", 300, "SA", DENY1, err=True, string_result=True, agent=agent)]


FAILING = {
    "api_error_assistant": dict(tail=_api_assistant),
    "api_error_system": dict(tail=_api_system),
    "permission_denial": dict(stop="tool_use", blocks=[tool_use("bash-1", "Bash", command="x")], tail=_denial),
    "no_final_reply": dict(stop="tool_use", blocks=text_block()),
    # Agent decision (answer 37): narrowest reading of CON-035 is that a final reply is stop_reason end_turn only, so a run that
    # ends on a SubagentHandback tool call (stop_reason tool_use) is a run with no final reply
    "handback_call_is_not_a_final_reply": dict(stop="tool_use", blocks=[tool_use("hb-1", "SubagentHandback", message="PASS")]),
    # answer 3: a run with no final assistant reply is failed; an end_turn record with no text in it is no reply
    "end_turn_with_only_blank_text": dict(blocks=[{"type": "text", "text": "  \n "}]),
    "end_turn_with_only_non_text_blocks": dict(blocks=[{"type": "thinking", "thinking": "hm"}, tool_use("x-1", "Read", file_path="/x")]),
    # Agent decision (answer 37): narrowest reading of "ended in an API error" (answer 3) is that the run's final state decides,
    # so an API error after a normal reply makes the run failed ...
    "api_error_after_a_normal_reply": dict(blocks=text_block(), tail=_api_assistant),
}
NOT_FAILING = {
    "fail_verdict": dict(blocks=text_block("FAIL: criteria not met")),
    "blocked_verdict": dict(blocks=text_block("BLOCKED: need input")),
    "ordinary_tool_error": dict(blocks=text_block(), tail=lambda ag: [result("t9", 120, "SA", "exit 1", err=True, agent=ag)]),
    # Agent decision (answer 37): ... and a normal reply after an earlier API error clears it (the run recovered and ended normally)
    "normal_reply_after_an_api_error": dict(blocks=text_block(), tail=lambda ag: _api_assistant(ag) + [
        amsg("ok-2", 400, "SA", SONNET, usage(5, 5), text_block("SENTINEL-REPLY again"), "end_turn", agent=ag)]),
    "normal_reply_after_a_system_api_error": dict(blocks=text_block(), tail=lambda ag: _api_system(ag) + [
        amsg("ok-2", 400, "SA", SONNET, usage(5, 5), text_block("SENTINEL-REPLY again"), "end_turn", agent=ag)]),
}


def _failed_case(e, kw):
    s = Sess(e, "SA", A).spawn("builder", A, 10, dur=100)
    s.spawn("reviewer", A, 200, dur=100, **kw).write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    return cli_json(e, A, B)


# rule: CON-035
@pytest.mark.parametrize("name", sorted(FAILING))
def test_run_that_did_not_complete_is_failed(e, name):
    data = _failed_case(e, FAILING[name])
    assert has(list(nums_at(data, "fail")), 1)
    assert has(list(nums_at(data, "run", "total")), 2)


# rule: CON-035
@pytest.mark.parametrize("name", sorted(NOT_FAILING))
def test_verdicts_and_ordinary_errors_are_not_failed_runs(e, name):
    data = _failed_case(e, NOT_FAILING[name])
    assert has(list(nums_at(data, "run", "total")), 2)           # the comparison ran ...
    assert set(nums_at(data, "fail")) and set(nums_at(data, "fail")) <= {0, 0.0}   # ... and found no failed run


# ---------- CON-035 / CON-036: raw logs read-only, no log text in any output ----------

# rule: CON-035, CON-036
def test_raw_logs_are_read_only_and_no_log_text_reaches_the_output(e):
    s = Sess(e, "SA", A, prompt="[AAA-1] SENTINEL-PROMPT go")
    s.say(5, blocks=text_block(), u=u(10, 0))
    s.spawn("builder", A, 10, stop="tool_use", blocks=[tool_use("bash-1", "Bash", command="x")], tail=_denial)
    s.spawn("reviewer", A, 200, tail=_api_system, blocks=text_block())
    s.spawn("tester", A, 300, refuse=DENY2)
    s.write()
    main_only(e, "SB", B, u(1, 0))
    before = tree_hash(e.root)
    out = [cli(e, A, B, "--json").stdout, cli(e, A, B, text=True).stdout, get_page(e, A, B).text]
    assert all(o.strip() for o in out)
    for o in out:
        for sent in SENTINELS:
            assert sent not in o
    assert tree_hash(e.root) == before


# rule: CON-036
def test_compare_leaves_every_raw_log_file_untouched(e):
    s = Sess(e, "SA", A).spawn("builder", A, 10)
    s.spawn("reviewer", A, 200, stop="tool_use", blocks=[tool_use("bash-1", "Bash", command="x")], tail=_denial).write()
    main_only(e, "SB", B, u(1, 1))
    files = sorted(p for p in e.root.rglob("*") if p.is_file())
    assert files
    for p in files:
        os.utime(p, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in files}
    assert cli_json(e, A, B)
    assert get_page(e, A, B).status_code == 200
    assert sorted(p for p in e.root.rglob("*") if p.is_file()) == files
    assert {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in files} == before


# rule: CON-052
def test_no_new_dependency_is_declared_or_imported(e):   # reads source text: it is a guard, not the behaviour
    import ast
    import tomllib

    src = (CONSOLE / "agent_console" / "compare.py").read_text()
    mods = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            mods.add(n.module.split(".")[0])
    assert mods <= set(sys.stdlib_module_names) | {"agent_console"}, mods
    head = subprocess.run(["git", "show", "HEAD:console/pyproject.toml"], cwd=CONSOLE, capture_output=True, text=True)
    if head.returncode == 0:
        assert tomllib.loads((CONSOLE / "pyproject.toml").read_text()).get("project", {}).get("dependencies") == \
            tomllib.loads(head.stdout).get("project", {}).get("dependencies")


# ---------- CON-037: denied spawns ----------

# rule: CON-037
def test_denied_spawn_counts_in_run_total_and_failed(e):
    s = Sess(e, "SA", A).spawn("builder", A, 10)
    s.spawn("builder", A, 100, refuse=DENY1)                       # a denied run takes its number in the role's order (answer 25)
    s.spawn("reviewer", A, 200, refuse=DENY2)
    s.spawn("tester", "no key here", 300, refuse=DENY1, desc="do stuff")   # no key in the spawn input: counted for no ticket
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "run", "total")), 3)
    assert has(list(nums_at(data, "fail")), 2)
    assert has(list(nums_at(data, "repeat")), 1)


# ---------- CON-038: tokens per model ----------

# rule: CON-038
def test_tokens_are_split_per_model_by_the_messages_own_model(e):
    s = Sess(e, "SA", A).say(5, model=SONNET, u=u(1111, 222, 3333, 444, 55), blocks=text_block())
    s.spawn("builder", A, 10, model="anthropic.claude-haiku-5-5-v1:0", u=u(666, 77, 888, 99, 11), requested="claude-opus-5-5")
    s.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    son, hai = under(data, "sonnet-5-5"), under(data, "haiku-5-5")
    for x in (1111, 222, 3333, 499):          # cache write = 5 min + 1 h
        assert has(son, x)
    for x in (666, 77, 888, 110):
        assert has(hai, x)
    assert not has(hai, 1111) and not has(son, 666)
    assert "opus" not in json.dumps(data)      # the requested model is not the served one


# rule: CON-038
def test_message_without_model_id_is_counted_as_unknown(e):   # answer 29
    s = Sess(e, "SA", A).say(5, model=None, u=u(909, 0), blocks=text_block())
    s.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    assert has(under(data, "unknown"), 909)


# ---------- CON-039 / CON-040: cost ----------

# rule: CON-039
def test_cost_per_model_and_total_from_pricing_yaml(e):
    s = Sess(e, "SA", A).say(5, model=SONNET, u=u(1000, 200), blocks=text_block())
    s.spawn("builder", A, 10, model="anthropic.claude-haiku-5-5-v1:0", u=u(2000, 1000, 10000, 800, 400))
    s.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    assert has(under(data, "sonnet-5-5"), 2.0)     # 1.00 input + 1.00 output
    assert has(under(data, "haiku-5-5"), 0.98)     # 0.2 + 0.5 + 0.1 + (0.1 + 0.08) cache write of both kinds
    assert has(list(nums(data)), 2.98)


# rule: CON-040
def test_unpriced_messages_add_zero_and_are_counted(e):
    s = Sess(e, "SA", A).say(5, model=SONNET, u=u(1000, 0), blocks=text_block())
    s.say(6, model="claude-mystery-9", u=u(5000, 5000), blocks=text_block())
    s.say(7, model="claude-mystery-9", u=u(6000, 6000), blocks=text_block())
    s.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "unpriced")), 2)
    assert has(list(nums(data)), 1.0) and not has(list(nums(data)), 1.0 + 5000 * 1e-3)   # the unpriced ones add nothing


# rule: CON-040
def test_unpriced_count_is_also_given_per_model(e):
    s = Sess(e, "SA", A).say(5, model=SONNET, u=u(1000, 0), blocks=text_block())
    s.say(6, model="claude-mystery-9", u=u(5000, 5000), blocks=text_block())
    s.say(7, model="claude-mystery-9", u=u(6000, 6000), blocks=text_block())
    s.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    assert has(under(data["a"], "claude-mystery-9"), 2)


# ---------- CON-041 / CON-042: wall and active time ----------

# rule: CON-041
def test_wall_time_is_first_to_last_record_over_all_files(e):
    s1 = Sess(e, "S1", A).say(100, blocks=text_block())
    s1.spawn("builder", A, 3000, dur=1930)          # the last record of the ticket: second 4930, in a sub-agent file
    s1.write()
    s2 = Sess(e, "S2", A, prompt="[AAA-1] again")
    s2.recs[0]["timestamp"] = at(20000)
    s2.say(20100, blocks=text_block()).write()
    main_only(e, "SB", B, u(5, 5), end=50)
    data = cli_json(e, A, B)
    vals = list(nums(data))
    assert has(vals, 20100)                          # first record (0) to the last (20100), not the sum of the sessions' spans
    assert not has(vals, 4930 + 100)


# rule: CON-042
def test_active_role_time_adds_up_parallel_runs(e):
    s = Sess(e, "SA", A).say(5, blocks=text_block())
    s.spawn("builder", A, 100, dur=300)
    s.spawn("reviewer", A, 150, dur=420)             # overlaps the first
    s.write()
    main_only(e, "SB", B, u(5, 5), end=50)
    data = cli_json(e, A, B)
    vals = list(nums(data))
    assert has(vals, 720) and not has(vals, 470)


# ---------- CON-043 .. CON-046: waiting ----------

def _wait_world(e, build):
    s = Sess(e, "SA", A)
    build(s)
    s.write()
    main_only(e, "SB", B, u(5, 5), end=20)
    return cli_json(e, A, B)


# rule: CON-043
def test_wait_threshold_gaps_under_60_s_are_zero_and_long_gaps_count(e):
    def build(s):
        s.say(10, blocks=text_block()).human(10 + 59)                 # 59 s: zero
        s.say(100, blocks=text_block()).human(100 + 60)               # 60 s: counts
        s.say(200, blocks=text_block()).human(200 + 300)              # 300 s
        s.say(600, blocks=text_block()).human(600 + 8000)             # over 2 h: counts as waiting, not parked
    data = _wait_world(e, build)
    vals = list(nums(data))
    assert has(vals, 8360)
    assert not has(vals, 59) and not has(vals, 8359)


# rule: CON-045
def test_extra_figure_is_the_part_of_the_wait_over_two_hours(e):
    def build(s):
        s.say(10, blocks=text_block()).human(310)           # 300 s
        s.say(400, blocks=text_block()).human(400 + 8000)   # 8000 s, a gap over 2 h
    data = _wait_world(e, build)
    vals = list(nums_at(data, "wait"))
    assert has(vals, 8300) and has(vals, 8000)


# rule: CON-045
def test_gap_of_exactly_two_hours_is_not_over_two_hours(e):
    def build(s):
        s.say(10, blocks=text_block()).human(10 + 7200)       # exactly 2 h: a wait, but not "over 2 h"
    data = _wait_world(e, build)
    assert has(list(nums_at(data, "wait")), 7200)
    over = list(nums_at(data, "wait", "2h"))
    assert over and set(over) <= {0, 0.0}


# rule: CON-044
def test_only_end_turn_and_ask_user_question_are_stops_for_the_person(e):
    def build(s):
        s.say(10, blocks=text_block(), stop="end_turn").human(310)                                  # 300 s: counts
        s.say(320, blocks=text_block(), stop="tool_use").human(320 + 311)                           # not a stop
        s.say(640, blocks=text_block(), stop="stop_sequence").human(640 + 173)                      # not a stop
        s.say(820, stop="tool_use", blocks=[tool_use("ask-1", "AskUserQuestion", questions=[])])
        s.raw(result("ask-1", 820 + 240, "SA", "answer", string_result=True))                       # the answer ends the gap: 240 s
        s.say(1100, blocks=text_block(), stop="tool_use")
    data = _wait_world(e, build)
    vals = list(nums(data))
    assert has(vals, 540)
    assert not has(vals, 311) and not has(vals, 173)


# rule: CON-043
def test_machine_written_user_records_do_not_end_a_wait(e):   # answer 24
    def build(s):
        s.say(10, blocks=text_block())
        s.human(110, text="<task-notification>", origin="task-notification")
        s.human(410)                                            # the person types: the gap is 400 s
    data = _wait_world(e, build)
    vals = list(nums(data))
    assert has(vals, 400) and not has(vals, 100)


# rule: CON-046
def test_sub_agent_runs_give_no_waits(e):
    def build(s):
        s.say(10, blocks=text_block()).human(310)                                       # main: 300 s
        s.spawn("builder", A, 400, dur=100, tail=lambda ag: [human(500 + 913, "SA", agent=ag)])   # sub: stop, then a prompt 913 s later
    data = _wait_world(e, build)
    vals = list(nums(data))
    assert has(vals, 300) and not has(vals, 913)


# ---------- CON-047 / CON-048: share and "no main session" ----------

# rule: CON-047
def test_share_is_main_cost_over_sub_agent_cost(e):
    s = Sess(e, "SA", A).say(5, u=u(1000, 200), blocks=text_block())                       # main 2.00
    s.spawn("builder", A, 10, model=HAIKU, u=u(2000, 1000, 10000, 800, 400))               # sub 0.98
    s.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "share")), 2.0 / 0.98)


# rule: CON-047
def test_share_without_sub_agents_says_so(e):
    two_simple(e)
    p = cli(e, A, B, text=True)
    assert p.returncode == 0 and "no sub-agents" in p.stdout.lower()
    raw = cli(e, A, B, "--json").stdout
    assert "Infinity" not in raw and "NaN" not in raw
    assert get_page(e, A, B).text.lower().count("no sub-agents") >= 1


def _no_main_world(e):
    s = Sess(e, "SX", A)
    for i, role in enumerate(["planner", "builder", "reviewer", "tester"]):
        s.spawn(role, A, 10 + 100 * i)
    s.spawn("analyst", C, 600, u=u(321, 0))      # 4 of 5 children carry A: the main session is A's, ticket C has no main session
    s.write()
    main_only(e, "SB", B, u(5, 5))


# rule: CON-048
def test_ticket_without_main_session_says_so_in_the_main_rows(e):
    _no_main_world(e)
    text = cli_text(e, C, B)
    assert text.lower().count("no main session") >= 4     # wait, main tokens, main cost, share
    page_text = get_page(e, C, B).text.lower()
    assert page_text.count("no main session") >= 4


# rule: CON-048
def test_ticket_totals_show_real_values_without_a_main_session(e):
    _no_main_world(e)
    data = cli_json(e, C, B)
    assert has(list(nums_at(data, "run", "total")), 1)
    assert has(list(nums(data)), 321)                      # the run's tokens are in the ticket total


# rule: CON-048
def test_several_main_sessions_are_summed(e):
    s1 = Sess(e, "S1", A).say(5, u=u(1000, 0), blocks=text_block()).human(5 + 300)
    s1.write()
    s2 = Sess(e, "S2", A).say(5, u=u(2000, 0), blocks=text_block()).human(5 + 500)
    s2.write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    vals = list(nums(data))
    assert has(vals, 3000) and has(vals, 800) and has(vals, 3.0)    # tokens, wait seconds, cost (3.00 USD)


# ---------- CON-049: third column ----------

# rule: CON-049
def test_difference_and_ratio_b_over_a(e):
    two_simple(e)                      # A costs 2.00, B costs 5.00
    data = cli_json(e, A, B)
    vals = list(nums(data))
    assert has(vals, 3.0) and has(vals, 2.5)
    text = cli_text(e, A, B)
    assert re.search(r"(?<![\d.])2\.50(?!\d)", text)    # ratio with two decimals (answer 26)


# rule: CON-049
def test_ratio_and_difference_are_na_when_a_value_is_missing(e):
    _no_main_world(e)
    text = cli_text(e, C, B)
    assert text.lower().count("n/a") >= 4              # main rows: difference and ratio need both sides
    s = Sess(e, "SZ", D).spawn("builder", D, 10, stop="tool_use")   # D: one failed run; A below has none
    s.write()
    main_only(e, "SA", A, u(5, 5))
    assert "n/a" in cli_text(e, A, D).lower()           # a = 0 failed runs: the ratio is n/a


# ---------- CON-050: rounding ----------

def _rounding_world(e):
    s = Sess(e, "SA", A).say(2830, u=u(0, 0, 123457), blocks=text_block())     # 123457 cache-read tokens = 12.3457 USD; 47 min 10 s
    s.write()
    main_only(e, "SB", B, u(0, 0, 370371), end=100)                             # exactly 3x: ratio 3.00


# rule: CON-050
@pytest.mark.parametrize("where", ["cli", "page"])
def test_text_output_is_rounded_the_same_way(e, where):
    _rounding_world(e)
    text = cli_text(e, A, B) if where == "cli" else get_page(e, A, B).text
    assert re.search(r"(?<![\d.,])123(?![\d])", text) and "123457" not in text and "123,457" not in text      # tokens to thousands
    assert re.search(r"(?<![\d.])12\.35(?!\d)", text) and "12.3457" not in text                                 # dollars to cents
    assert re.search(r"(?<![\d.,])47(?![\d.])", text) and "2830" not in text                                    # minutes
    assert re.search(r"(?<![\d.])3\.00(?!\d)", text)                                                            # ratio, two decimals


# rule: CON-050
@pytest.mark.parametrize("where", ["cli", "page"])
def test_negative_difference_that_rounds_to_zero_is_never_minus_zero(e, where):   # answer 34
    main_only(e, "SA", A, u(0, 0, 1040), end=120)      # 1040 cache-read tokens, 120 s
    main_only(e, "SB", B, u(0, 0, 1000), end=100)      # B is 40 tokens (0.004 USD) and 20 s lower: all round to zero
    text = cli_text(e, A, B) if where == "cli" else get_page(e, A, B).text
    assert not re.search(r"(?<!\w)-\s*\$?0(\.0+)?(k| min)?(?![\d.])", text)
    assert re.search(r"(?<![\d.])0k", text) and "$0.00" in text and re.search(r"(?<![\d.])0 min", text)


# rule: CON-050
def test_json_keeps_raw_values(e):
    _rounding_world(e)
    vals = list(nums(cli_json(e, A, B)))
    assert has(vals, 123457) and has(vals, 12.3457) and has(vals, 2830)


# ---------- CON-051: stable JSON ----------

def _sorted_everywhere(o):
    if isinstance(o, dict):
        return list(o) == sorted(o) and all(_sorted_everywhere(v) for v in o.values())
    if isinstance(o, list):
        return all(_sorted_everywhere(v) for v in o)
    return True


# rule: CON-051
def test_json_keys_are_sorted_and_the_output_is_repeatable(e):
    s = Sess(e, "SA", A).say(5, model=SONNET, u=u(1, 1), blocks=text_block())
    s.spawn("builder", A, 10, model=HAIKU, u=u(2, 2)).spawn("zeta", A, 100, model="claude-mystery-9")
    s.write()
    main_only(e, "SB", B, u(5, 5))
    first, second = cli(e, A, B, "--json"), cli(e, A, B, "--json")
    assert first.returncode == 0 and first.stdout == second.stdout
    assert _sorted_everywhere(json.loads(first.stdout))


# ======================================================================================================================
# Round 3 (re-plan): rules CON-032, 035, 037, 038, 043, 044, 050, 051, 053, 054, 055 after answers 24-38 and reviewer F11, F12
# ======================================================================================================================

def _bare_spawn(s, role, key, sec, tid, with_result=None):
    """A sub-agent spawn that has NO run file. with_result: None = no tool result at all, False = ok result, True = error result."""
    s.raw(amsg(s.mid(), sec, s.sid, SONNET, usage(0, 0), [tool_use(tid, "Agent", subagent_type=role, description=f"{key} work", prompt="p")],
               "tool_use", base=s.base))
    if with_result is not None:
        s.raw(result(tid, sec + 1, s.sid, "SENTINEL-DENY refused" if with_result else "SENTINEL-REPLY started", err=with_result,
                     string_result=with_result, base=s.base))
    return s


def _line(text, label):
    return next(ln for ln in text.splitlines() if ln.strip().startswith(label))


# ---------- CON-035 (F11, F12): what decides a failed run ----------

def _denied_last(deny):
    return lambda ag: [result("bash-9", 300, "SA", deny, err=True, string_result=True, agent=ag)]


# rule: CON-035
@pytest.mark.parametrize("deny", [DENY1, DENY2], ids=["wording_permission_for_this", "wording_user_doesnt_want"])
def test_denied_result_after_the_last_normal_reply_fails_a_run_that_ended_with_end_turn(e, deny):   # F11
    data = _failed_case(e, dict(blocks=text_block(), stop="end_turn", tail=_denied_last(deny)))
    assert has(list(nums_at(data, "fail")), 1)


# rule: CON-035
def test_non_denial_error_result_after_the_last_reply_does_not_fail_an_end_turn_run(e):   # F11 and the string toolUseResult form
    data = _failed_case(e, dict(blocks=text_block(), tail=lambda ag: [result("t9", 300, "SA", "exit code 1: boom", err=True, string_result=True, agent=ag)]))
    assert set(nums_at(data, "fail")) and set(nums_at(data, "fail")) <= {0, 0.0}


# rule: CON-035
def test_denial_that_is_not_an_error_result_does_not_fail_the_run(e):   # the denial wording alone is not enough: is_error must be true
    data = _failed_case(e, dict(blocks=text_block(), tail=lambda ag: [result("t9", 300, "SA", DENY1, err=False, string_result=True, agent=ag)]))
    assert set(nums_at(data, "fail")) and set(nums_at(data, "fail")) <= {0, 0.0}


# rule: CON-035
def test_normal_reply_after_a_denial_clears_it(e):   # final state decides (answer 37). CONFLICT noted in the report: F11 vs this reading
    data = _failed_case(e, dict(stop="tool_use", blocks=[tool_use("bash-9", "Bash", command="x")], tail=lambda ag: [
        result("bash-9", 150, "SA", DENY1, err=True, string_result=True, agent=ag),
        amsg("ok-3", 400, "SA", SONNET, usage(5, 5), text_block("SENTINEL-REPLY again"), "end_turn", agent=ag)]))
    assert set(nums_at(data, "fail")) and set(nums_at(data, "fail")) <= {0, 0.0}


# rule: CON-035
def test_synthetic_record_that_is_not_an_api_error_does_not_clear_an_api_error(e):   # F12 (does not clear)
    def syn(ag):
        return [amsg("syn-1", 400, "SA", "<synthetic>", usage(0, 0), text_block("SENTINEL-REPLY note"), "end_turn", agent=ag)]
    data = _failed_case(e, dict(blocks=text_block(), tail=lambda ag: _api_assistant(ag) + syn(ag)))
    assert has(list(nums_at(data, "fail")), 1)


# rule: CON-035
def test_synthetic_record_that_is_not_an_api_error_does_not_fail_a_finished_run(e):   # F12 (does not set)
    data = _failed_case(e, dict(blocks=text_block(), tail=lambda ag: [
        amsg("syn-1", 400, "SA", "<synthetic>", usage(0, 0), [{"type": "text", "text": "SENTINEL-REPLY note"}], "stop_sequence", agent=ag)]))
    assert set(nums_at(data, "fail")) and set(nums_at(data, "fail")) <= {0, 0.0}


# rule: CON-035
def test_run_with_a_missing_stop_reason_is_failed(e):
    def no_stop(ag):
        r = amsg("ns-1", 400, "SA", SONNET, usage(1, 1), text_block(), "end_turn", agent=ag)
        del r["message"]["stop_reason"]
        return [r]
    data = _failed_case(e, dict(stop="tool_use", blocks=[tool_use("x-1", "Read", file_path="/x")], tail=no_stop))
    assert has(list(nums_at(data, "fail")), 1)


# rule: CON-035
def test_run_whose_log_file_is_gone_is_not_failed(e):
    s = Sess(e, "SA", A).spawn("builder", A, 10).spawn("reviewer", A, 200, stop="tool_use", blocks=text_block())   # this one would be failed
    s.write()
    main_only(e, "SB", B, u(5, 5))
    cli_json(e, A, B)                                             # builds the index
    for p in e.root.rglob("agent-SAa2.jsonl"):
        p.unlink()
    data = cli_json(e, A, B)
    assert set(nums_at(data, "fail")) <= {0, 0.0}


# ---------- CON-037 / CON-053: spawns without a run file ----------

# rule: CON-037, CON-053
def test_non_error_spawn_without_a_run_file_counts_as_a_run_and_is_not_failed(e):   # answer 35, item 44
    s = Sess(e, "SA", A).spawn("builder", A, 10)
    _bare_spawn(s, "builder", A, 100, "tu-bare-1", with_result=False)
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "run", "total")), 2)
    assert has(list(nums_at(data, "repeat")), 1)                   # it takes a number in the role's order
    assert set(nums_at(data, "fail")) <= {0, 0.0}


# rule: CON-037, CON-053
def test_spawn_with_neither_result_nor_run_file_is_not_counted(e):   # answer 33
    s = Sess(e, "SA", A).spawn("builder", A, 10)
    _bare_spawn(s, "builder", A, 100, "tu-bare-2", with_result=None)
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "run", "total")), 1)
    assert set(nums_at(data, "repeat")) <= {0, 0.0} and set(nums_at(data, "fail")) <= {0, 0.0}


# rule: CON-037, CON-053
def test_error_spawn_without_a_run_file_counts_as_a_run_and_as_failed(e):
    s = Sess(e, "SA", A).spawn("builder", A, 10)
    _bare_spawn(s, "builder", A, 100, "tu-bare-3", with_result=True)
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "run", "total")), 2) and has(list(nums_at(data, "fail")), 1) and has(list(nums_at(data, "repeat")), 1)


# rule: CON-037
def test_spawn_with_a_run_file_is_not_counted_twice(e):
    s = Sess(e, "SA", A).spawn("builder", A, 10).spawn("reviewer", A, 100)
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    assert has(list(nums_at(data, "run", "total")), 2)


# rule: CON-037
def test_several_refused_spawns_each_count_with_their_own_id(e):   # answer 38
    s = Sess(e, "SA", A)
    for i in range(3):
        s.spawn("builder", A, 10 + 10 * i, refuse=DENY1)
    s.write()
    Sess(e, "SB", B).spawn("builder", B, 10).write()
    data = cli_json(e, A, B)
    ids = [r["message"]["content"][0]["tool_use_id"] for r in s.recs if r.get("toolUseResult") is not None]
    assert len(set(ids)) == 3
    assert has(list(nums_at(data, "run", "total")), 3) and has(list(nums_at(data, "fail")), 3) and has(list(nums_at(data, "repeat")), 2)


# rule: CON-037, CON-032
def test_a_refused_spawn_that_names_the_key_makes_the_key_known(e):
    s = Sess(e, "SX", None).say(5, blocks=text_block())            # a main session with no key
    s.spawn("builder", "ZZZ-7", 10, refuse=DENY1)
    s.write()
    main_only(e, "SB", B, u(5, 5))
    p = cli(e, "ZZZ-7", B, "--json")
    assert p.returncode == 0, p.stderr[-300:]
    data = json.loads(p.stdout)
    assert has(list(nums_at(data, "run", "total")), 1) and has(list(nums_at(data, "fail")), 1)
    assert get_page(e, "ZZZ-7", B).status_code == 200


# ---------- CON-032: unknown key ----------

# rule: CON-032
def test_page_unknown_key_is_http_404_and_names_the_key(e):
    two_simple(e)
    for a, b in ((A, "NOPE-9"), ("NOPE-9", A)):
        r = get_page(e, a, b)
        assert r.status_code == 404 and "NOPE-9" in r.text and "unknown" in r.text.lower()
    r = get_page(e, "NOPE-8", "NOPE-9")
    assert r.status_code == 404 and "NOPE-8" in r.text and "NOPE-9" in r.text


# ---------- CON-054: missing keys, no length limit ----------

# rule: CON-054
@pytest.mark.parametrize("params", [{}, {"a": A}, {"b": B}, {"a": "", "b": B}, {"a": A, "b": ""}, {"a": "", "b": ""}])
def test_page_missing_or_empty_key_is_422_with_one_message_and_no_form(e, params):
    two_simple(e)
    client, _, _ = page(e, A, B)
    r = client.get("/compare", params=params)
    low = r.text.lower()
    assert r.status_code == 422
    assert "<form" not in low and "<input" not in low and "swap" not in low and "<a " not in low and "<table" not in low
    assert low.count("<p>") == 1


# rule: CON-054
@pytest.mark.parametrize("args", [[], [A], [A, B, C]])
def test_cli_wrong_number_of_keys_prints_usage_and_exits_2(e, args):
    two_simple(e)
    p = cli(e, *args)
    assert p.returncode == 2 and p.stdout.strip() == "" and "usage" in p.stderr.lower()


# rule: CON-054
def test_a_long_key_is_not_refused_for_its_length(e):   # the earlier 60-character guard is gone: a long key is just an unknown key
    two_simple(e)
    huge = "X" * 300
    r = get_page(e, huge, B)
    assert r.status_code == 404 and huge in r.text
    p = cli(e, huge, B, "--json")
    assert p.returncode == 2 and huge in p.stderr and "Traceback" not in p.stderr
    r = get_page(e, "Y" * 61, B)
    assert r.status_code == 404                                    # not 422/400 for a key over 60 characters


# ---------- CON-055: no case folding ----------

# rule: CON-055
def test_a_key_in_the_wrong_case_is_unknown_when_only_the_other_case_has_runs(e):
    main_only(e, "SU", "ABC-1", u(222, 0))
    main_only(e, "SB", B, u(5, 5))
    assert cli(e, "abc-1", B, "--json").returncode == 2


# ---------- CON-038: the unknown model ----------

# rule: CON-038
def test_a_message_without_a_model_id_is_shown_under_unknown_in_the_page_and_json(e):
    Sess(e, "SA", A).say(5, model=None, u=u(909, 3), blocks=text_block()).write()
    main_only(e, "SB", B, u(5, 5))
    data = cli_json(e, A, B)
    assert "unknown" in data["a"]["tokens_by_model"] and "unknown" in data["difference"]["tokens_by_model"]
    assert has(under(data["a"]["tokens_by_model"], "unknown"), 909)
    assert "unknown" in get_page(e, A, B).text


# ---------- CON-043 / CON-044: waiting ----------

# rule: CON-043
def test_a_gap_of_exactly_60_s_counts_and_59_s_is_zero(e):
    d60 = _wait_world(e, lambda s: s.say(10, blocks=text_block()).human(70))
    assert has(list(nums_at(d60, "a", "wait_s")), 60) or has(list(nums_at(d60["a"], "wait")), 60)


# rule: CON-043
def test_a_gap_of_59_s_counts_as_zero(e):
    d59 = _wait_world(e, lambda s: s.say(10, blocks=text_block()).human(69))
    w = list(nums_at(d59["a"], "main", "wait"))
    assert w and set(w) <= {0, 0.0}


# rule: CON-043
def test_gap_just_over_two_hours_counts_in_the_extra_figure_and_exactly_two_hours_does_not(e):   # strictly more than 7200 s
    over = _wait_world(e, lambda s: s.say(10, blocks=text_block()).human(10 + 7201))
    assert has(list(nums_at(over["a"], "main", "2h")), 7201) and has(list(nums_at(over["a"], "main", "wait")), 7201)


# rule: CON-043
@pytest.mark.parametrize("record", [
    dict(text="<local-command-stdout>ok</local-command-stdout>", origin=None),
    dict(text="[Request interrupted by user]", origin=None),
    dict(text="<task-notification>x</task-notification>", origin=None),
    dict(text="<system-reminder>x</system-reminder>", origin=None),
    dict(text="anything", origin="task-notification"),
    dict(text="anything", origin="system"),
], ids=["local_command_no_origin", "interrupt_marker_no_origin", "task_notification_no_origin", "system_reminder_no_origin",
        "origin_task_notification", "origin_system"])
def test_machine_records_do_not_end_a_gap(e, record):   # answers 24, 30; no-origin detection (Agent decision)
    def build(s):
        s.say(10, blocks=text_block())
        s.human(110, text=record["text"], origin=record["origin"])
        s.human(410)                                            # typed: the gap is 400 s
    data = _wait_world(e, build)
    vals = list(nums_at(data["a"], "main", "wait"))
    assert has(vals, 400) and not has(vals, 100)


# rule: CON-043
@pytest.mark.parametrize("origin", [None, "human"])
def test_a_typed_slash_command_ends_a_gap(e, origin):
    def build(s):
        s.say(10, blocks=text_block())
        s.human(250, text="/clear", origin=origin)
    data = _wait_world(e, build)
    assert has(list(nums_at(data["a"], "main", "wait")), 240)


# rule: CON-043
def test_a_tool_result_does_not_end_a_gap(e):
    def build(s):
        s.say(10, blocks=text_block())
        s.raw(result("t-1", 100, "SA", "out", string_result=True))
        s.human(410)
    data = _wait_world(e, build)
    vals = list(nums_at(data["a"], "main", "wait"))
    assert has(vals, 400) and not has(vals, 90)


# rule: CON-043, CON-044
def test_rejected_permission_prompt_gap_ends_at_the_next_typed_message(e):   # answers 24, 30
    def build(s):
        s.say(10, stop="tool_use", blocks=[tool_use("bash-1", "Bash", command="x")])
        s.raw(result("bash-1", 20, "SA", DENY2, err=True, string_result=True))        # the rejection is a tool result: not a typed message
        s.say(30, blocks=text_block("SENTINEL-REPLY stopped"))                         # the turn stops here and waits on the person
        s.human(30 + 400, text="[Request interrupted by user for tool use]", origin=None)   # interrupt marker: not typed
        s.human(30 + 500, text="please go on")                                         # typed
    data = _wait_world(e, build)
    vals = list(nums_at(data["a"], "main", "wait"))
    assert has(vals, 500) and not has(vals, 400) and not has(vals, 10)


# rule: CON-044
def test_a_turn_that_ends_with_an_ask_user_question_waits_for_its_answer_only(e):
    def build(s):
        s.say(10, stop="tool_use", blocks=[tool_use("ask-9", "AskUserQuestion", questions=[])])
        s.raw(result("t-x", 50, "SA", "something else", string_result=True))      # a different tool result: does not end the gap
        s.raw(result("ask-9", 10 + 300, "SA", "the answer", string_result=True))
        s.say(400, blocks=text_block(), stop="tool_use")
    data = _wait_world(e, build)
    vals = list(nums_at(data["a"], "main", "wait"))
    assert has(vals, 300) and not has(vals, 40)


# ---------- CON-050: rounding ----------

def _tokens_total_line(e, a_tokens, b_tokens, label="Tokens: total"):
    main_only(e, "SA", A, u(0, 0, a_tokens))
    main_only(e, "SB", B, u(0, 0, b_tokens))
    return _line(cli_text(e, A, B), label)


# rule: CON-050
def test_tokens_are_shown_as_12k_with_ties_away_from_zero_and_the_sign_kept(e):
    ln = _tokens_total_line(e, 12000, 13500)       # 12k, 13.5k -> 14k, difference 1500 -> 2k
    assert re.search(r"(?<![\d.,])12k", ln) and re.search(r"(?<![\d.,])14k", ln) and re.search(r"(?<![\d.,])2k", ln)
    assert "12,000" not in ln and "12 k" not in ln


# rule: CON-050
def test_negative_difference_rounds_its_size_the_same_way_and_keeps_the_sign(e):
    ln = _tokens_total_line(e, 13500, 12000)
    assert re.search(r"-2k", ln)                   # -1500 -> -2k (tie away from zero)


# rule: CON-050
def test_ratio_tie_rounds_away_from_zero(e):
    ln = _tokens_total_line(e, 1000, 1005)         # ratio 1.005
    assert re.search(r"(?<![\d.])1\.01(?!\d)", ln)


# rule: CON-050
def test_time_is_whole_minutes_and_hours_stay_in_minutes(e):
    main_only(e, "SA", A, u(1, 0), end=8100)       # 135 min
    main_only(e, "SB", B, u(1, 0), end=90)         # 1.5 min -> 2 min (tie away from zero)
    ln = _line(cli_text(e, A, B), "Wall time")
    assert "135 min" in ln and "2 min" in ln and "-134 min" in ln     # 90 s = 1.5 min -> 2; -133.5 -> -134
    assert not re.search(r"\d+\s*h\b", ln)


# rule: CON-050
def test_dollars_always_have_two_decimals_and_a_negative_zero_is_shown_without_minus(e):
    main_only(e, "SA", A, u(0, 0, 5000))           # 0.50 USD
    main_only(e, "SB", B, u(0, 0, 4999))           # 0.4999 -> 0.50, difference -0.0001 -> $0.00
    ln = _line(cli_text(e, A, B), "Cost")
    assert "$0.50" in ln and "$0.00" in ln and "-$0.00" not in ln and "$-0.00" not in ln and "-0.00" not in ln


# ---------- CON-051: the JSON shape ----------

# rule: CON-051
def test_json_shape_is_fixed(e):
    s = Sess(e, "SA", A).say(5, model=SONNET, u=u(1, 1), blocks=text_block())
    s.spawn("builder", A, 10, model=HAIKU, u=u(2, 2))
    s.write()
    main_only(e, "SB", B, u(3, 3))
    data = cli_json(e, A, B)
    assert set(data) == {"a", "b", "difference", "ratio"}
    col = {"key", "role_runs", "tokens", "tokens_by_model", "cost_usd", "unpriced_messages", "wall_s", "active_role_s", "main_session",
           "sub_agents_cost_usd", "main_share_of_sub_cost"}
    assert set(data["a"]) == col and set(data["b"]) == col
    assert data["a"]["key"] == A and data["b"]["key"] == B
    assert set(data["a"]["role_runs"]) == {"total", "failed", "repeat"}
    assert isinstance(data["a"]["main_session"], dict) and isinstance(data["b"]["main_session"], dict)
    assert HAIKU.replace("claude-", "") in " ".join(data["a"]["tokens_by_model"]) or any("haiku" in k for k in data["a"]["tokens_by_model"])
    dm, rm = data["difference"]["tokens_by_model"], data["ratio"]["tokens_by_model"]
    hk = next(k for k in dm if "haiku" in k)                                   # a model on one side only: null
    assert all(v is None for v in dm[hk].values()) and all(v is None for v in rm[hk].values())


# rule: CON-051
def test_json_main_session_is_null_when_there_is_none_and_na_values_are_null(e):
    _no_main_world(e)
    data = cli_json(e, C, B)
    assert data["a"]["main_session"] is None and isinstance(data["b"]["main_session"], dict)
    assert data["difference"]["main_tokens_total"] is None and data["ratio"]["main_tokens_total"] is None
    assert data["a"]["main_share_of_sub_cost"] is None
