"""The /compare page (EXP1-R22C): one table for two ticket keys, the 422/503/404 pages, the strict-CSP rules, no write path, no log text.

Cases: EP-/DT-/BVA- ids of EXP1-R22C. Markup and texts: CON-027, CON-033, CON-034, CON-035.
Fixtures are written with the conftest helpers (nothing is changed in conftest); the tmp home and log root come from the `env` fixture.
"""

import hashlib
import html
import datetime
import json
import os
import re
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from agent_console import config, server
from agent_console.pricing import Pricing
from agent_console.store import Store
from conftest import PROJECT, add_sub, api_error, assistant, flat_routes, tool_result, tool_use, usage, user_prompt, write_jsonl

HTML_CT = "text/html; charset=utf-8"
NO_MAIN = "no main session"
MAIN_IDS = ["tokens.main.input", "tokens.main.output", "tokens.main.cache_write", "tokens.main.cache_read",
            "cost_usd.main", "time_s.wait", "time_s.wait_over_2h", "cost_share"]
BUILDING = "The console is updating its index. Reload this page later."
POST_LITERAL = {"/api/show/{run_id:path}", "/api/flags/check", "/api/rescan", "/api/verdict", "/api/defect", "/api/flags/decide"}   # as test_server.py


# ---------------------------------------------------------------- fixtures (log builders)

def build(env, sess, key, children=(), main_input=None, day=None):
    """One main session `sess` with own key `key` and one spawn per child (the B5 recipe).

    child = (child_key, role, what[, model]); what = int input tokens (a run file) | "error" (error result, no file) | "open" (no result, no file).
    """
    recs = [user_prompt(f"[{key}] go", t=0, session=sess)]
    if main_input is not None:
        recs.append(assistant(f"{sess}-main", u=usage(main_input, 0), t=5, session=sess))
    results, subs = [], []
    for i, child in enumerate(children):
        ck, role, what = child[:3]
        model = child[3] if len(child) > 3 else None
        tid, agent = f"{sess}-t{i}", f"{sess}-ag{i}"
        recs.append(assistant(f"{sess}-m{i}", u=usage(0, 0), t=1 + i, session=sess,
                              blocks=[tool_use(tid, "Agent", subagent_type=role, description=f"[{ck}] x", prompt="p")]))
        if what != "open":
            results.append(tool_result(tid, what == "error", t=100 + i, session=sess))
        if isinstance(what, int):
            sub = assistant(f"{sess}-s{i}", agent=agent, session=sess, t=10 + i, u=usage(what, 0), **({"model": model} if model else {}))
            subs.append((agent, role, [sub], tid))
    recs += results

    def old(rs):
        if day:
            for r in rs:
                r["timestamp"] = r["timestamp"].replace("2026-10-20", day)
        return rs
    write_jsonl(env.root / PROJECT / f"{sess}.jsonl", old(recs))
    for agent, role, rs, tid in subs:
        add_sub(env.root, sess, agent, role, old(rs), tid)


def nomain(env, key, day=None, extra=()):
    """NOMAIN(key): key has a sub run and no main session; ABC-9 owns main S9 with two runs (2 of 3 children keyed ABC-9 < 80 percent)."""
    build(env, "S9", "ABC-9", [("ABC-9", "builder", 1000), ("ABC-9", "tester", 1000), (key, "reviewer", 1000), *extra], day=day)


def simple(env):
    build(env, "S1", "ABC-1", [("ABC-1", "builder", 1000)])
    build(env, "S2", "ABC-2", [("ABC-2", "builder", 1000), ("ABC-2", "tester", 1000)])


def make_app(ingest=True):
    store = Store()
    if ingest:
        store.ingest()
    client = TestClient(server.create_app(store=store, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")
    return store, client


# ---------------------------------------------------------------- page readers

class Page(HTMLParser):
    """rows[id] = {label, a, b, d, diff, ratio}; heads = [(class, text)] of the column headings."""

    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.rows, self.heads, self.tables = {}, [], 0
        self._row = self._cell = self._span = self._head = None
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        if tag == "table" and at.get("class") == "compare":
            self.tables += 1
        elif tag == "tr" and "data-row" in at:
            self._row = self.rows.setdefault(at["data-row"], {"label": "", "a": "", "b": "", "d": "", "diff": "", "ratio": ""})
        elif tag == "th" and at.get("scope") == "row" and self._row is not None:
            self._cell = "label"
        elif tag == "th" and at.get("scope") == "col":
            self._head = [at.get("class", ""), ""]
            self.heads.append(self._head)
        elif tag == "td" and self._row is not None:
            self._cell = at.get("class")
        elif tag == "span" and self._row is not None and at.get("class") in ("diff", "ratio"):
            self._span = at["class"]

    def handle_endtag(self, tag):
        if tag == "tr":
            self._row = self._cell = self._span = None
        elif tag in ("td", "th"):
            self._cell = self._head = None
        elif tag == "span":
            self._span = None

    def handle_data(self, data):
        if self._head is not None:
            self._head[1] += data
        if self._row is not None and self._cell in ("label", "a", "b", "d"):
            self._row[self._cell] += data
        if self._row is not None and self._span:
            self._row[self._span] += data


def page(body):
    p = Page(body)
    for row in p.rows.values():
        for k in row:
            row[k] = row[k].strip()
    return p


def err_texts(body):
    return re.findall(r'<p class="error">(.*?)</p>', body, re.S)


def sha_tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def index_state(env):
    import sqlite3
    out = {}
    for n in ("index.sqlite", "index.sqlite-wal"):
        p = env.home / n
        if p.exists():
            out[n] = hashlib.sha256(p.read_bytes()).hexdigest()
    con = sqlite3.connect((env.home / "index.sqlite").as_uri() + "?mode=ro", uri=True)
    try:
        out["user_version"] = con.execute("PRAGMA user_version").fetchone()[0]
        out["meta"] = sorted(con.execute("SELECT k, v FROM meta"))
    finally:
        con.close()
    return out


def assert_strict_doc(body):
    """One complete document; no inline script or style, no style attribute, nothing from another origin (CON-033)."""
    assert body.lstrip().lower().startswith("<!doctype html") and body.rstrip().endswith("</html>")
    assert not re.search(r"<style", body, re.I)
    assert not re.search(r"\sstyle\s*=", body, re.I)
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", body, re.I | re.S):
        assert re.search(r'\bsrc="/static/', m.group(1)) and not m.group(2).strip(), m.group(0)[:80]
    assert not re.search(r"<script\b(?![^>]*\bsrc=)", body, re.I)
    for m in re.finditer(r'\b(?:src|href|action)\s*=\s*"([^"]*)"', body, re.I):
        assert not re.match(r"(?:https?:)?//", m.group(1)), m.group(0)


def assert_page(r, status):
    """Status, content type, the five security headers and the strict document rules."""
    assert r.status_code == status, r.text[:300]
    assert r.headers["content-type"] == HTML_CT
    for k, v in server.SECURITY_HEADERS.items():
        assert r.headers[k] == v, k
    assert_strict_doc(r.text)
    return r.text


def ok200(client, a, b, runs_a, runs_b, diff_cell, no_main=True):
    """OK200 oracle of the CON-027 cases."""
    body = assert_page(client.get("/compare", params={"a": a, "b": b}), 200)
    p = page(body)
    assert p.tables == 1 and '<table class="compare">' in body
    heads = {c: t.strip() for c, t in p.heads}
    assert heads.get("a") == a and heads.get("b") == b
    row = p.rows["runs.total"]
    assert (row["a"], row["b"], row["d"]) == (runs_a, runs_b, diff_cell)
    if no_main:
        assert p.rows["tokens.main.input"]["a"] == NO_MAIN
    return p


def not_found(client, params, text):
    body = assert_page(client.get("/compare", params=params), 404)
    assert f'<p class="error">{text}</p>' in body and "<table" not in body
    return body


# ================================================================ CON-010: first index

# rule: CON-010
def test_ep_010_01_two_tickets_give_the_table(env):
    simple(env)
    _, client = make_app()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-2"), 200)
    p = page(body)
    assert p.tables == 1 and "Reload this page later" not in body and '<p class="error">' not in body
    assert [t.strip() for _, t in p.heads] == ["Figure", "ABC-1", "ABC-2", "Difference b - a (ratio b / a)"]
    assert [c for c, _ in p.heads][1:3] == ["a", "b"]
    row = p.rows["runs.total"]
    assert (row["label"], row["a"], row["b"], row["diff"], row["ratio"]) == ("Role runs", "1", "2", "1", "2.00")


# rule: CON-010
def test_ep_010_06_the_page_never_scans_or_writes_the_index(env, monkeypatch):
    simple(env)
    store, client = make_app()
    calls = []
    real = {n: getattr(store, n) for n in ("rescan", "ingest")}
    for n in real:
        monkeypatch.setattr(store, n, lambda *a, _n=n, **k: (calls.append(_n), real[_n](*a, **k))[1])
    before = index_state(env)
    assert client.get("/compare?a=ABC-1&b=ABC-2").status_code == 200
    assert client.get("/compare?a=ABC-1&b=ABC-2").status_code == 200
    assert calls == []
    assert index_state(env) == before


# rule: CON-010
def test_dt_010_02_initial_wins_over_everything(env, monkeypatch):
    build(env, "S1", "EXP1-AAA")
    store, client = make_app()
    calls = []
    monkeypatch.setattr(store, "rescan", lambda *a, **k: calls.append("rescan"))
    monkeypatch.setattr(store, "ingest", lambda *a, **k: calls.append("ingest"))
    store.progress["initial"] = True
    body = assert_page(client.get("/compare?a=EXP1-NOPE&b=EXP1-AAA"), 503)
    assert err_texts(body) == [BUILDING]
    assert "EXP1-NOPE" not in body and "EXP1-AAA" not in body and "<table" not in body
    assert not re.search(r"\d|\$|\bmin\b|unknown", err_texts(body)[0], re.I)
    assert calls == []


# rule: CON-010
def test_dt_010_03_no_scan_yet_and_no_runs_is_503(env, monkeypatch):
    store, client = make_app(ingest=False)
    assert "initial" not in store.progress and store.progress["scans"] == 0
    assert store.db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    calls = []
    monkeypatch.setattr(store, "rescan", lambda *a, **k: calls.append("rescan"))
    monkeypatch.setattr(store, "ingest", lambda *a, **k: calls.append("ingest"))
    body = assert_page(client.get("/compare?a=EXP1-AAA&b=EXP1-BBB"), 503)
    assert err_texts(body) == [BUILDING] and "EXP1-AAA" not in body and "EXP1-BBB" not in body and "<table" not in body
    store.progress["initial"] = True        # DT-010-02 gives the same answer
    assert client.get("/compare?a=EXP1-AAA&b=EXP1-BBB").text == body
    assert calls == []


# rule: CON-010
def test_dt_010_04_an_old_index_answers_before_the_first_scan(env, monkeypatch):
    build(env, "S1", "EXP1-AAA")
    build(env, "S2", "EXP1-BBB")
    first = Store()
    first.ingest()
    first.db.close()
    store, client = make_app(ingest=False)
    assert store.progress["scans"] == 0 and "initial" not in store.progress
    assert store.db.execute("SELECT count(*) FROM runs").fetchone()[0] > 0
    calls = []
    monkeypatch.setattr(store, "rescan", lambda *a, **k: calls.append("rescan"))
    monkeypatch.setattr(store, "ingest", lambda *a, **k: calls.append("ingest"))
    body = assert_page(client.get("/compare?a=EXP1-AAA&b=EXP1-BBB"), 200)
    p = page(body)
    assert '<th scope="col" class="a">EXP1-AAA</th>' in body and '<th scope="col" class="b">EXP1-BBB</th>' in body
    assert (p.rows["main_sessions"]["a"], p.rows["main_sessions"]["b"]) == ("1", "1")
    assert calls == []


# rule: CON-010
def test_dt_010_05_after_one_scan_an_empty_index_is_404_not_503(env):
    env.root.mkdir(parents=True, exist_ok=True)
    store, client = make_app()
    assert store.progress["initial"] is False and store.progress["scans"] == 1
    assert store.db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
    body = not_found(client, {"a": "EXP1-NOPE", "b": "EXP1-NOPE2"},
                     "Unknown ticket keys: <code>EXP1-NOPE</code>, <code>EXP1-NOPE2</code>.")
    assert err_texts(body) == ["Unknown ticket keys: <code>EXP1-NOPE</code>, <code>EXP1-NOPE2</code>."]


# rule: CON-010, CON-027
def test_dt_027_14_first_index_wins_over_an_unknown_key(env):
    build(env, "S1", "EXP1-AAA")
    store, client = make_app()
    store.progress["initial"] = True
    body = assert_page(client.get("/compare?a=EXP1-NOPE&b=EXP1-AAA"), 503)
    assert err_texts(body) == [BUILDING] and "EXP1-NOPE" not in body


# ---------------------------------------------------------------- scan in progress (CON-010 v3, answer 47)

DEAD_PID = 4_000_000   # above every pid limit used by macOS (99999) and Linux (4194304 max, never reached here)
PAIR = "/compare?a=EXP1-AAA&b=EXP1-Y5"


def many_files(env):
    """EXP1-Y5: a main session with 45 spawns and 45 sub-agent files (several 20-file commits)."""
    build(env, "SY", "EXP1-Y5", [("EXP1-Y5", "builder", 1000 + i) for i in range(45)])


def hook_after_each_file(monkeypatch, fn):
    orig = Store._ingest_file
    seen = []

    def wrapped(self, *a, **k):
        r = orig(self, *a, **k)
        seen.append(fn())
        return r
    monkeypatch.setattr(Store, "_ingest_file", wrapped)
    return seen


def scan_markers(store):
    return [r[0] for r in store.db.execute("SELECT k FROM meta WHERE k LIKE 'scan:%'")]


def assert_updating(r):
    body = assert_page(r, 503)
    assert err_texts(body) == [BUILDING] and "<table" not in body and "EXP1-" not in body
    return body


# rule: CON-010, CON-027
def test_hv_p20_a_later_scan_answers_only_503_or_the_settled_200(env):
    build(env, "S1", "EXP1-AAA")
    store, client = make_app()
    many_files(env)
    with pytest.MonkeyPatch.context() as hook_patch:   # own patch: undoing it must not undo the env fixture
        seen = hook_after_each_file(hook_patch, lambda: client.get(PAIR))
        store.ingest()
    assert len(seen) > 40
    for r in seen:
        assert_updating(r)
    body = assert_page(client.get(PAIR), 200)
    assert env.tmp.resolve() in config.log_root().resolve().parents   # guard: the fresh ingest must not read the real log root
    fresh = Store(env.tmp / "fresh.sqlite")
    fresh.ingest()
    fclient = TestClient(server.create_app(store=fresh, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")
    assert page(body).rows == page(assert_page(fclient.get(PAIR), 200)).rows


# rule: CON-010
def test_dt_010_06_a_scan_by_another_process_answers_503(env):
    assert env.tmp.resolve() in config.log_root().resolve().parents   # guard: the ingest must not read the real log root
    assert env.tmp.resolve() in config.home().resolve().parents
    build(env, "S1", "EXP1-AAA")
    store, client = make_app()
    many_files(env)
    other = Store()   # the CLI's path: same home, its own progress (idle)
    assert store.progress["state"] == "idle" and other.progress["state"] == "idle"
    with pytest.MonkeyPatch.context() as hook_patch:   # own patch: undoing it must not undo the env fixture
        seen = hook_after_each_file(hook_patch, lambda: client.get(PAIR))
        other.ingest()
    assert seen and all(r.status_code == 503 for r in seen)
    assert_updating(seen[0])
    assert_page(client.get(PAIR), 200)


# rule: CON-010
def test_dt_010_07_a_marker_of_a_dead_process_clears_at_the_next_ingest(env):
    build(env, "S1", "EXP1-AAA")
    build(env, "S2", "EXP1-Y5")
    store, client = make_app()
    with pytest.raises(ProcessLookupError):
        os.kill(DEAD_PID, 0)
    store.db.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (f"scan:{DEAD_PID}", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    store.db.commit()
    assert_updating(client.get(PAIR))
    store.ingest()
    assert scan_markers(store) == []
    assert_page(client.get(PAIR), 200)


# rule: CON-010
def test_dt_010_08_a_marker_of_a_live_process_survives(env):
    build(env, "S1", "EXP1-AAA")
    build(env, "S2", "EXP1-Y5")
    store, client = make_app()
    live = os.getppid()   # alive and not this process (this process's own row is removed by its own ingest)
    assert live != os.getpid()
    os.kill(live, 0)
    key = f"scan:{live}"
    store.db.execute("INSERT OR REPLACE INTO meta VALUES(?, ?)", (key, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    store.db.commit()
    store.ingest()
    assert scan_markers(store) == [key]
    assert_updating(client.get(PAIR))
    store.db.execute("DELETE FROM meta WHERE k=?", (key,))   # the other process ends
    store.db.commit()
    store.ingest()
    assert_page(client.get(PAIR), 200)


# rule: CON-010
def test_dt_010_09_a_failed_scan_keeps_503_until_the_next_successful_scan(env, monkeypatch):
    build(env, "S1", "EXP1-AAA")
    store, client = make_app()
    many_files(env)
    orig = Store._ingest_file
    n = []

    def failing(self, *a, **k):
        n.append(1)
        if len(n) == 25:
            raise ValueError("boom")
        return orig(self, *a, **k)
    monkeypatch.setattr(Store, "_ingest_file", failing)
    store.rescan(wait=True, min_interval=0)
    assert store.progress["error"] == "ValueError"
    assert_updating(client.get(PAIR))
    monkeypatch.setattr(Store, "_ingest_file", orig)
    store.rescan(wait=True, min_interval=0)
    assert store.progress["error"] is None and scan_markers(store) == []
    assert_page(client.get(PAIR), 200)


# ================================================================ CON-011 (page half)

# rule: CON-011
def test_ep_011_01_page_half_main_session_tokens_are_rounded_to_thousands(env):
    build(env, "S1", "ABC-1", main_input=1500)
    build(env, "S2", "ABC-2", main_input=2500)
    _, client = make_app()
    p = page(assert_page(client.get("/compare?a=ABC-1&b=ABC-2"), 200))
    row = p.rows["tokens.main.input"]
    assert (row["label"], row["a"], row["b"], row["diff"], row["ratio"]) == ("Main-session tokens, input", "2k", "3k", "1k", "1.67")


# ================================================================ CON-025: no main session

# rule: CON-025
def test_ep_025_03_page_shows_the_label_in_eight_cells(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    p = page(assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200))
    for rid in MAIN_IDS:
        row = p.rows[rid]
        assert row["a"] == NO_MAIN, rid
        assert row["b"] != NO_MAIN and row["b"] != "0", rid
        assert row["d"] == "n/a (n/a)", rid
    assert sum(1 for r in p.rows.values() if r["a"] == NO_MAIN) == 8


# ================================================================ CON-027: known and unknown keys

# rule: CON-027
def test_ep_027_01_a_key_known_through_a_sub_run_has_no_main_session(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    ok200(client, "ABC-1", "ABC-9", "1", "2", "1 (2.00)")


# rule: CON-027
def test_ep_027_02_the_own_key_of_a_main_session_is_known_with_no_data(env):
    build(env, "S1", "ABC-1", [("ABC-2", "builder", 1000)] * 3)
    store, client = make_app()
    pair = [tuple(r) for r in store.reader().execute("SELECT ticket, ticket_eff FROM runs WHERE kind='main'")]
    assert pair == [("ABC-1", "ABC-2")]      # fixture precondition (CON-002, 3 of 3 children)
    ok200(client, "ABC-1", "ABC-2", "0", "3", "3 (n/a)")


# rule: CON-027
def test_ep_027_03_a_key_on_a_counted_spawn_only_is_known(env):
    nomain(env, "ABC-1", extra=[("ABC-3", "builder", "error")])
    _, client = make_app()
    p = ok200(client, "ABC-3", "ABC-9", "1", "2", "1 (2.00)")
    assert p.rows["time_s.wall"]["a"] == "0 min"


# rule: CON-027
def test_ep_027_04_a_key_whose_run_file_was_deleted_stays_known(env):
    nomain(env, "ABC-1")
    store, client = make_app()
    (env.root / PROJECT / "S9" / "subagents" / "agent-S9-ag2.jsonl").unlink()
    store.rescan(wait=True, min_interval=0)
    ok200(client, "ABC-1", "ABC-9", "1", "2", "1 (2.00)")


# rule: CON-027
def test_ep_027_05_unknown_key_is_a_404_page(env):
    build(env, "S1", "ABC-9", [("ABC-9", "builder", 1000)])
    _, client = make_app()
    body = not_found(client, {"a": "ABC-404", "b": "ABC-9"}, "Unknown ticket key: <code>ABC-404</code>.")
    assert "<title>Ticket comparison</title>" in body and "<h1>Ticket comparison</h1>" in body
    with pytest.raises(ValueError):
        json.loads(body)


# rule: CON-027
def test_ep_027_07_two_unknown_keys_are_named_a_first(env):
    build(env, "S1", "ABC-9", [("ABC-9", "builder", 1000)])
    _, client = make_app()
    not_found(client, {"a": "ABC-404", "b": "ABC-405"}, "Unknown ticket keys: <code>ABC-404</code>, <code>ABC-405</code>.")


# rule: CON-027
def test_ep_027_09_the_same_unknown_key_twice_is_named_once(env):
    from agent_console import compare
    build(env, "S1", "ABC-9", [("ABC-9", "builder", 1000)])
    store, client = make_app()
    body = not_found(client, {"a": "ABC-404", "b": "ABC-404"}, "Unknown ticket key: <code>ABC-404</code>.")
    assert body.count("ABC-404") == 1
    db = store.reader()
    try:
        assert compare.unknown_keys(db, "ABC-404", "ABC-404") == ["ABC-404"]
    finally:
        db.close()


# rule: CON-027
def test_ep_027_10_keys_are_case_sensitive(env):
    build(env, "S1", "ABC-1", [("ABC-1", "builder", 1000)])
    build(env, "S2", "ABC-9", [("ABC-9", "builder", 1000)])
    _, client = make_app()
    not_found(client, {"a": "abc-1", "b": "ABC-9"}, "Unknown ticket key: <code>abc-1</code>.")


# rule: CON-027
def test_ep_027_11_a_spawn_with_no_result_and_no_file_is_not_known(env):
    build(env, "S1", "ABC-9", [("ABC-7", "builder", "open")])
    _, client = make_app()
    not_found(client, {"a": "ABC-7", "b": "ABC-9"}, "Unknown ticket key: <code>ABC-7</code>.")


# rule: CON-027
def test_ep_027_12_old_records_still_count(env):
    nomain(env, "ABC-8", day="2026-03-01")
    _, client = make_app()
    ok200(client, "ABC-8", "ABC-9", "1", "2", "1 (2.00)")


# rule: CON-027, CON-034
def test_dt_027_13_missing_parameter_wins_over_the_first_index_page(env):
    build(env, "S1", "EXP1-AAA")
    store, client = make_app()
    store.progress["initial"] = True
    body = assert_page(client.get("/compare?b=EXP1-AAA"), 422)
    assert err_texts(body) == ["Missing parameter: <code>a</code>."] and BUILDING not in body


# ================================================================ CON-031: read only

# rule: CON-031
def test_ep_031_02_the_page_does_not_touch_the_logs(env):
    simple(env)
    _, client = make_app()
    before = sha_tree(env.root)
    assert before
    assert client.get("/compare?a=ABC-1&b=ABC-2").status_code == 200
    assert client.get("/compare?a=ABC-1&b=ABC-2").status_code == 200
    assert sha_tree(env.root) == before


# rule: CON-031
def test_ep_031_03_compare_is_a_get_only_route_with_no_form(env):
    simple(env)
    _, client = make_app()
    routes = [r for r in flat_routes(client.app) if "compare" in r.path]
    assert routes, "no /compare route"
    assert all(r.methods <= {"GET", "HEAD"} for r in routes)
    assert {r.path for r in flat_routes(client.app) if "POST" in r.methods} - POST_LITERAL == set()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-2"), 200)
    assert not re.search(r"<form|<input|<button", body, re.I) and not re.search(r'method\s*=\s*"?post', body, re.I)


# ================================================================ CON-033: loopback only, strict pages

# rule: CON-033
def test_ep_033_01_a_foreign_host_gets_the_guard_json_not_the_page(env):
    simple(env)
    _, client = make_app()
    assert client.get("/compare?a=ABC-1&b=ABC-2").status_code == 200      # the route exists behind the guard
    r = client.get("/compare?a=ABC-1&b=ABC-2", headers={"host": "evil.example.com"})
    h = client.get("/health", headers={"host": "evil.example.com"})
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")
    assert (r.status_code, r.headers["content-type"], r.content) == (h.status_code, h.headers["content-type"], h.content)
    assert r.json() == {"detail": "Not found."} and "ABC-1" not in r.text


# rule: CON-033
def test_ep_033_02_loopback_host_names_are_served(env):
    simple(env)
    _, client = make_app()
    for host in ("127.0.0.1:8790", "localhost:8790"):
        r = client.get("/compare?a=ABC-1&b=ABC-2", headers={"host": host})
        assert r.status_code == 200 and r.headers["content-type"] == HTML_CT and "ABC-1" in r.text, host


# rule: CON-033
def test_ep_033_04_the_200_page_has_the_table_and_the_headers(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    assert '<table class="compare">' in assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200)


# rule: CON-033
def test_ep_033_05_the_404_page_has_the_error_and_the_headers(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    not_found(client, {"a": "ABC-404", "b": "ABC-9"}, "Unknown ticket key: <code>ABC-404</code>.")


# rule: CON-033
def test_ep_033_06_the_422_page_has_the_headers(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    assert "Missing parameter: <code>b</code>." in assert_page(client.get("/compare?a=ABC-1"), 422)


# rule: CON-033
def test_ep_033_07_the_503_page_has_the_headers(env):
    nomain(env, "ABC-1")
    store, client = make_app()
    store.progress["initial"] = True
    assert f'<p class="error">{BUILDING}</p>' in assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 503)


# rule: CON-033
def test_ep_033_09_every_page_is_one_strict_document(env):
    nomain(env, "ABC-1")
    store, client = make_app()
    bodies = [assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200),
              assert_page(client.get("/compare?a=ABC-404&b=ABC-9"), 404),
              assert_page(client.get("/compare?a=ABC-1"), 422)]
    store.progress["initial"] = True
    bodies.append(assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 503))
    assert len(set(bodies)) == 4


# rule: CON-033
def test_ep_033_10_the_stylesheet_is_a_static_file_the_page_links(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200)
    assert 'href="/static/compare.css"' in body
    r = client.get("/static/compare.css")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/css")
    assert "@import" not in r.text and "url(http" not in r.text and not re.search(r"https?://", r.text)


# rule: CON-033
def test_bva_031_a_wrong_port_or_no_port_is_refused_by_the_host_guard(env):
    build(env, "S1", "EXP1-100")
    _, client = make_app()
    for host in ("127.0.0.1:8789", "127.0.0.1:8791", "localhost:8791", "127.0.0.1"):
        r = client.get("/compare?a=EXP1-100&b=EXP1-100", headers={"host": host})
        assert r.status_code == 404 and r.json() == {"detail": "Not found."} and "<html" not in r.text, host
    for host in ("127.0.0.1:8790", "localhost:8790"):
        r = client.get("/compare?a=EXP1-100&b=EXP1-100", headers={"host": host})
        assert r.status_code == 200 and r.headers["content-type"] == HTML_CT and '<table class="compare">' in r.text, host


# ================================================================ CON-034: parameters

# rule: CON-034
def test_dt_034_01_a_missing_names_a_only(env):
    build(env, "S1", "EXP1-BBB")
    _, client = make_app()
    body = assert_page(client.get("/compare?b=EXP1-BBB"), 422)
    assert err_texts(body) == ["Missing parameter: <code>a</code>."]
    assert "<code>b</code>" not in body and '"detail"' not in body
    assert not re.search(r"<form|<a |swap|compare with", body, re.I)


# rule: CON-034
def test_dt_034_02_b_missing_names_b_only(env):
    build(env, "S1", "EXP1-AAA")
    _, client = make_app()
    body = assert_page(client.get("/compare?a=EXP1-AAA"), 422)
    assert err_texts(body) == ["Missing parameter: <code>b</code>."] and "<code>a</code>" not in body


# rule: CON-034
def test_dt_034_03_both_missing_names_both(env):
    build(env, "S1", "EXP1-AAA")
    _, client = make_app()
    body = assert_page(client.get("/compare"), 422)
    assert err_texts(body) == ["Missing parameters: <code>a</code>, <code>b</code>."]


# rule: CON-034
def test_dt_034_04_an_empty_value_is_missing(env):
    build(env, "S2", "EXP1-BBB")
    _, client = make_app()
    body = assert_page(client.get("/compare?a=&b=EXP1-BBB"), 422)
    assert err_texts(body) == ["Missing parameter: <code>a</code>."] and "<table" not in body


# rule: CON-034
def test_dt_034_05_only_spaces_is_missing_not_unknown(env):
    build(env, "S2", "EXP1-BBB")
    _, client = make_app()
    body = assert_page(client.get("/compare?a=%20%20&b=EXP1-BBB"), 422)
    assert err_texts(body) == ["Missing parameter: <code>a</code>."] and "<table" not in body


# rule: CON-034
def test_ep_034_06_a_key_is_not_trimmed(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    body = assert_page(client.get("/compare?a=%20ABC-1&b=ABC-9"), 404)
    assert "Unknown ticket key: <code> ABC-1</code>." in body


# rule: CON-034, CON-031
def test_ep_034_12_a_third_parameter_is_ignored(env):
    for s, k in (("S1", "ABC-1"), ("S2", "ABC-9"), ("S3", "ABC-77")):
        build(env, s, k, [(k, "builder", 1000)])
    _, client = make_app()
    r1, r2, r3 = (client.get(u) for u in ("/compare?a=ABC-1&b=ABC-9&c=X", "/compare?a=ABC-1&b=ABC-9", "/compare?a=ABC-1&b=ABC-9&c=ABC-77"))
    assert (r1.status_code, r2.status_code, r3.status_code) == (200, 200, 200)
    assert r1.text == r2.text == r3.text and '<table class="compare">' in r2.text
    assert ">X<" not in r1.text and "ABC-77" not in r3.text


# rule: CON-034
def test_ep_034_13_the_last_repeated_value_wins(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    r1 = client.get("/compare?a=ABC-404&a=ABC-1&b=ABC-9")
    r2 = client.get("/compare?a=ABC-1&b=ABC-9")
    r3 = client.get("/compare?a=ABC-1&a=ABC-404&b=ABC-9")
    assert r1.status_code == 200 and r1.text == r2.text
    assert r3.status_code == 404 and "ABC-404" in r3.text


# rule: CON-034
def test_ep_034_14_no_form_swap_or_link_to_another_comparison(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200)
    assert not re.search(r"<form|<input|<button", body, re.I)
    assert "compare with" not in body.lower() and "swap" not in body.lower()
    assert not re.search(r'href="[^"]*/compare\?', body)


# rule: CON-034
def test_ep_034_15_the_422_page_is_html_not_the_json_handler(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    r = client.get("/compare?b=ABC-9")
    body = assert_page(r, 422)
    with pytest.raises(ValueError):
        json.loads(body)
    assert '"detail"' not in body
    assert '<p class="error">Missing parameter: <code>a</code>.</p>' in body and "<code>b</code>" not in body


# ================================================================ CON-035: no log text, escaped output

def write_sent(env):
    main = [user_prompt("[ABC-1] go SENT-USER-9f3a", t=0, session="S1"),
            assistant("S1-say", t=1, session="S1", blocks=[{"type": "text", "text": "SENT-ASSIST-9f3a"}]),
            assistant("S1-bash", t=2, session="S1", blocks=[tool_use("bash1", "Bash", command="SENT-TOOLIN-9f3a")]),
            assistant("S1-spawn", t=4, session="S1", u=usage(0, 0),
                      blocks=[tool_use("sp1", "Agent", subagent_type="builder", description="[ABC-1] x", prompt="SENT-PROMPT-9f3a")])]
    res = tool_result("bash1", t=3, session="S1")
    res["message"]["content"][0]["content"] = "SENT-TOOLRES-9f3a"
    write_jsonl(env.root / PROJECT / "S1.jsonl", main + [res, tool_result("sp1", t=100, session="S1")])
    add_sub(env.root, "S1", "ag1", "builder", [assistant("S1-sub", agent="ag1", session="S1", t=10, u=usage(1000, 0),
                                                         blocks=[{"type": "text", "text": "SENT-SUBTEXT-9f3a"}])], "sp1")
    build(env, "S2", "ABC-9", [("ABC-9", "builder", 1000)])


# rule: CON-035
def test_ep_035_03_the_page_carries_no_log_text(env):
    write_sent(env)
    _, client = make_app()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200)
    assert "SENT-" not in body and page(body).rows["runs.total"]["a"] == "1"


# rule: CON-035
def test_ep_035_04_failure_texts_never_reach_a_page(env):
    deny = tool_result("sp1", True, t=100, session="S1")
    deny["message"]["content"][0]["content"] = "Permission to use Bash has been denied SENT-DENY-9f3a The user doesn't want to proceed"
    write_jsonl(env.root / PROJECT / "S1.jsonl", [
        user_prompt("[ABC-1] go", t=0, session="S1"),
        assistant("S1-sp1", t=1, session="S1", u=usage(0, 0), blocks=[tool_use("sp1", "Agent", subagent_type="builder", description="[ABC-1] x", prompt="p")]),
        assistant("S1-sp2", t=2, session="S1", u=usage(0, 0), blocks=[tool_use("sp2", "Agent", subagent_type="tester", description="[ABC-1] x", prompt="p")]),
        deny, tool_result("sp2", False, t=101, session="S1")])
    add_sub(env.root, "S1", "ag1", "builder", [assistant("S1-s1", agent="ag1", session="S1", t=10, u=usage(1000, 0))], "sp1")
    add_sub(env.root, "S1", "ag2", "tester", [assistant("S1-s2", agent="ag2", session="S1", t=11, u=usage(1000, 0)),
                                              api_error(t=12, session="S1", message="SENT-APIERR-9f3a arn:aws:sts::000000000000:assumed-role/x")], "sp2")
    build(env, "S2", "ABC-9", [("ABC-9", "builder", 1000)])
    _, client = make_app()
    bodies = [assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200),
              assert_page(client.get("/compare?a=ABC-404&b=ABC-9"), 404),
              assert_page(client.get("/compare?a=ABC-1"), 422)]
    assert page(bodies[0]).rows["runs.total"]["a"] == "2"
    for body in bodies:
        for bad in ("SENT-", "Permission to use", "The user doesn't want to proceed", "arn:aws"):
            assert bad not in body, bad


# rule: CON-035
def test_ep_035_05_a_key_is_escaped(env):
    nomain(env, "ABC-1")
    _, client = make_app()
    r = client.get("/compare", params={"a": "<script>x</script>", "b": "ABC-9"})
    body = assert_page(r, 404)
    assert "Unknown ticket key: <code>&lt;script&gt;x&lt;/script&gt;</code>." in body
    assert "<script>x</script>" not in body


# rule: CON-035
def test_ep_035_06_model_names_are_escaped_in_text_and_attributes(env):
    evil = "mod<b>RAW9f</b>"
    build(env, "S1", "ABC-1", [("ABC-1", "role<b>RAW9f</b>", 1000, evil)])
    build(env, "S2", "ABC-9", [("ABC-9", "builder", 1000)])
    _, client = make_app()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200)
    esc = html.escape(evil, quote=True)
    assert f'data-row="tokens.by_model.{esc}.input"' in body
    assert f"Tokens, {esc}, input" in body
    assert "<b>RAW9f" not in body


# rule: CON-035
def test_ep_035_07_quotes_in_a_model_name_are_escaped_in_the_attribute(env):
    evil = "mod\"q'x"
    build(env, "S1", "ABC-1", [("ABC-1", "builder", 1000, evil)])
    build(env, "S2", "ABC-9", [("ABC-9", "builder", 1000)])
    _, client = make_app()
    body = assert_page(client.get("/compare?a=ABC-1&b=ABC-9"), 200)
    assert 'data-row="tokens.by_model.mod&quot;q&#x27;x.input"' in body
    assert f'data-row="tokens.by_model.{evil}.input"' not in body


# rule: CON-035
def test_ep_035_08_the_column_heading_keys_are_escaped(env):
    from agent_console import compare, compare_page
    build(env, "S1", "ABC-1", [("ABC-1", "builder", 1000)])
    build(env, "S2", "ABC-9", [("ABC-9", "builder", 1000)])
    store, _ = make_app()
    db = store.reader()
    try:
        tree = compare.compare(db, Pricing.load(config.pricing_path()), "ABC-1", "ABC-9")
    finally:
        db.close()
    tree["a"]["key"], tree["b"]["key"] = "A<i>1", 'B"<u>2'
    body = compare_page.render(tree)
    assert '<th scope="col" class="a">A&lt;i&gt;1</th>' in body
    assert '<th scope="col" class="b">B&quot;&lt;u&gt;2</th>' in body
    assert "<i>" not in body and "<u>" not in body


# ================================================================ EXP1-R22C security findings (confirmation)

def _bad_main_page(env, variant):
    recs = [user_prompt("[ABC-7] start", t=0, session="SB")]
    stop = assistant("sb-1", u=usage(10, 0), t=5, session="SB")
    stop["message"]["stop_reason"] = "end_turn"
    if variant == "uuid":
        stop["uuid"] = ["x"]
    elif variant == "timestamp":
        stop["timestamp"] = 12345
    else:
        stop["message"]["content"] = [tool_use(["x"], "AskUserQuestion", q="q")]
    recs.append(stop)
    late = user_prompt("go on", t=3000, session="SB")
    late["uuid"] = "up-late"
    if variant == "timestamp":
        late["timestamp"] = ["bad"]
    recs.append(late)
    write_jsonl(env.root / PROJECT / "SB.jsonl", recs)


@pytest.mark.parametrize("variant", ["uuid", "timestamp", "tool_id"])
# rule: CON-011
# rule: CON-033
def test_sec_1_page_malformed_main_record_keeps_status_and_security_headers(env, variant):
    """SEC-1: a malformed main record -> 200 (record skipped) or an HTML error, always with the five security headers; never a bare 500."""
    simple(env)
    _bad_main_page(env, variant)
    store = Store()
    try:
        store.ingest()
    except Exception:
        pass                                    # ingest abort is another finding (INFO-1); the page must still answer
    client = TestClient(server.create_app(store=store, pricing=Pricing.load(config.pricing_path()), port=8790),
                        base_url="http://127.0.0.1:8790", raise_server_exceptions=False)
    r = client.get("/compare?a=ABC-1&b=ABC-7")
    for k, v in server.SECURITY_HEADERS.items():
        assert r.headers.get(k) == v, (r.status_code, k)
    assert r.status_code in (200, 404, 422, 500, 503)
    assert r.headers["content-type"] == HTML_CT, r.status_code


# rule: CON-033
def test_con_033_unexpected_error_gives_the_html_500_page(env, monkeypatch):
    """CON-033 v2 / CON-035: an unexpected error is the HTML 500 page, fixed text, no detail, the five headers."""
    nomain(env, "ABC-1")
    _, client = make_app()

    def boom(*args, **kwargs):
        raise RuntimeError("SECRET-DETAIL")
    monkeypatch.setattr(server.compare, "compare", boom)
    r = client.get("/compare", params={"a": "ABC-1", "b": "ABC-9"})
    assert r.status_code == 500
    assert r.headers["content-type"] == HTML_CT
    assert '<p class="error">The comparison could not be built. Try again later.</p>' in r.text
    assert "SECRET-DETAIL" not in r.text and "Traceback" not in r.text and "RuntimeError" not in r.text
    for k, v in server.SECURITY_HEADERS.items():
        assert r.headers[k] == v, k


# ---------------------------------------------------------------- code review 6: a malformed record is skipped, not a 500 (BD4)

# rule: CON-022
# rule: CON-033
def test_bd4_a_list_uuid_record_is_skipped_and_the_page_is_200_with_the_exact_wait(env):
    build(env, "S1", "EXP1-AAA", main_input=100)
    recs = [user_prompt("[EXP1-BAD] start", t=0, session="SB")]
    stop = assistant("sb-1", u=usage(10, 0), t=5, session="SB")
    stop["message"]["stop_reason"] = "end_turn"
    stop["uuid"] = ["x"]
    late = user_prompt("go on", t=3000, session="SB")
    write_jsonl(env.root / PROJECT / "SB.jsonl", recs + [stop, late])
    _, client = make_app()
    p = page(assert_page(client.get("/compare?a=EXP1-AAA&b=EXP1-BAD"), 200))
    assert p.rows["time_s.wait"]["a"] == "0 min"
    assert p.rows["time_s.wait"]["b"] == "50 min"          # 2995 s = 49.9 min, rounded half up
    assert p.rows["time_s.wait_over_2h"]["b"] == "0 min"
