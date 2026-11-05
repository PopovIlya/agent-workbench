"""EXP1-R22C: the `python -m agent_console compare` command (CON-011, CON-027, CON-031, CON-034, CON-035).

Main goal: show the compare CLI prints one table or the JSON, refuses a foreign index, and writes nothing it must not.
Tests call `compare_cli.main(argv)` in process (capsys); a few run `python -m agent_console compare` as a subprocess.
Modules under test are imported inside each test, so a missing module fails that test (never a skip).
Every test uses the `env` fixture: tmp home, tmp log root, never ~/.agent-console or ~/.claude.
"""

from __future__ import annotations

import ast
import gc
import hashlib
import importlib
import json
import os
import re
import runpy
import shutil
import sqlite3
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from conftest import PROJECT, add_sub, api_error, assistant, tool_result, tool_use, ts, usage, user_prompt, write_jsonl

CONSOLE = Path(__file__).resolve().parents[1]
HEADING = "Difference b - a (ratio b / a)"
USAGE_HEAD = "usage: python -m agent_console compare [-h] [--json] KEY_A KEY_B\n"
PX = ("regional_multiplier: 1.0\nmodels:\n"
      "  m-one: {input: 1.00, output: 2.00, cache_write_5m: 3.00, cache_write_1h: 4.00, cache_read: 0.50}\n"
      "  m-two: {input: 10.00, output: 20.00, cache_write_5m: 30.00, cache_write_1h: 40.00, cache_read: 5.00}\n"
      "tier_defaults: {sonnet: m-one}\n")


# ---------- helpers (local to this file) ----------

def cli():
    return importlib.import_module("agent_console.compare_cli")


def run(args, capsys):
    """In-process CLI call: (return value, stdout, stderr)."""
    rc = cli().main(list(args))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def run_proc(args):
    """Subprocess CLI call; env copied after the env fixture set its variables (never an empty env).

    AGENT_CONSOLE_PORT is a free port picked here, so a red run (old code starting the console) can never
    bind the default 8790; short timeout, the child is killed and the test fails with a clear message.
    """
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    child_env = os.environ.copy()
    child_env["AGENT_CONSOLE_PORT"] = str(port)
    p = subprocess.Popen([sys.executable, "-m", "agent_console", "compare", *args], cwd=CONSOLE, env=child_env,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = p.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        raise AssertionError("compare subprocess did not exit within 15 s (killed); the CLI must not start the console server")
    return p.returncode, out, err


def px(env):
    (env.tmp / "pricing.yaml").write_text(PX)


def usage_err(reason):
    return USAGE_HEAD + f"python -m agent_console compare: error: {reason}\n"


def differ(db_path, names):
    return (f"compare: refused: the index at {db_path} was built with another {names}; "
            "run compare with the console's settings (nothing written)\n")


def missing(db_path, names):
    return (f"compare: refused: the index at {db_path} does not record its {names}; "
            "start the console once with this checkout, then retry (nothing written)\n")


def build_main(env, session, key, *, main_in=None, main_out=0, children=(), day="2026-10-20", extra=(), prompt=None):
    """One main session file (own key = effective key = `key` unless children outvote it) plus sub-agent run files.
    A child is a key or a dict(key, file=True, result="ok"|"err"|None, inp=10, role="builder", prompt="p", text="ok").
    Ids are unique per session. Spawn records carry usage(0, 0), so only the stated tokens count."""
    recs = [user_prompt(prompt or f"[{key}] start", t=0, session=session, day=day)]
    if main_in is not None:
        recs.append(assistant(f"{session}-main", model="m-one", u=usage(main_in, main_out), t=10, session=session, day=day))
    recs += list(extra)
    subs = []
    for i, ch in enumerate(children):
        ch = {"key": ch} if isinstance(ch, str) else dict(ch)
        tid, agent = f"{session}-t{i}", f"{session}-ag{i}"
        role = ch.get("role", "builder")
        recs.append(assistant(f"{session}-sp{i}", model="m-one", u=usage(0, 0), t=1 + i, session=session, day=day,
                              blocks=[tool_use(tid, "Agent", subagent_type=role, description=f"[{ch['key']}] x", prompt=ch.get("prompt", "p"))]))
        res = ch.get("result", "ok")
        if res is not None:
            rec = tool_result(tid, res == "err", t=100 + i, session=session)
            rec["timestamp"] = ts(100 + i, day)
            recs.append(rec)
        if ch.get("file", True):
            sub = [assistant(f"{agent}-n", model="m-one", u=usage(ch.get("inp", 10), 0), t=10 + i, session=session, agent=agent, day=day,
                             blocks=[{"type": "text", "text": ch.get("text", "ok")}])]
            subs.append(add_sub(env.root, session, agent, role, sub, tid))
    write_jsonl(env.root / PROJECT / f"{session}.jsonl", recs)
    return subs


def nomain(env, key):
    """NOMAIN(key): key has one sub run and no main session; ABC-9 (main M in S9, 2 runs) keeps its own key (2/3 < 0.8)."""
    return build_main(env, "S9", "ABC-9", children=["ABC-9", "ABC-9", key])


def scan(env):
    from agent_console.store import Store
    st = Store()
    st.ingest()
    st.db.close()


def table(out):
    return [[c.strip() for c in ln.split("|")] for ln in out.rstrip("\n").split("\n")]


def row(out, label):
    for cells in table(out)[1:]:
        if cells[0] == label:
            return cells
    raise AssertionError(f"no line labelled {label!r} in:\n{out}")


def data(key, capsys):
    """DATA(K): the tree of one ticket, taken from the CLI itself (compare K K --json)."""
    rc, out, err = run([key, key, "--json"], capsys)
    assert rc == 0, err
    return json.loads(out)["a"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def file_hashes(home):
    return {n: (sha(Path(home) / n) if (Path(home) / n).exists() else None) for n in ("index.sqlite", "index.sqlite-wal")}


def db_state(home):
    p = Path(home) / "index.sqlite"
    if not p.exists():
        return None
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        has_meta = con.execute("SELECT count(*) FROM sqlite_master WHERE name='meta'").fetchone()[0]
        return {"user_version": con.execute("PRAGMA user_version").fetchone()[0],
                "meta": dict(con.execute("SELECT k, v FROM meta").fetchall()) if has_meta else None,
                "runs": con.execute("SELECT count(*) FROM runs").fetchone()[0] if con.execute(
                    "SELECT count(*) FROM sqlite_master WHERE name='runs'").fetchone()[0] else None}
    finally:
        con.close()


def tree_hash(root):
    return {str(p): sha(p) for p in sorted(Path(root).rglob("*")) if p.is_file()}


def snapshot(env, home=None):
    gc.collect()
    home = home or env.home
    state = db_state(home)          # first: a read-only open may create an empty -wal, so hash the files after it
    return file_hashes(home), state, tree_hash(env.root)


def baseline(env, capsys):
    """BASELINE-INDEX: KEYED(KA) + one sub run for KA + KEYED(KB); one good CLI call builds home/index.sqlite."""
    build_main(env, "S1", "EXP1-AAA", main_in=100, children=["EXP1-AAA"])
    build_main(env, "S2", "EXP1-BBB", main_in=100)
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    assert rc == 0, err
    assert (env.home / "index.sqlite").exists()
    return env.home / "index.sqlite"


def expect_refusal(env, capsys, expected, home=None, args=("EXP1-AAA", "EXP1-BBB")):
    before = snapshot(env, home)
    rc, out, err = run(list(args), capsys)
    assert rc == 2
    assert out == ""
    assert err == expected
    assert snapshot(env, home) == before


def delete_meta(env, *keys):
    con = sqlite3.connect(env.home / "index.sqlite")
    con.executemany("DELETE FROM meta WHERE k=?", [(k,) for k in keys])
    con.commit()
    con.close()


# ---------- CON-011: output, entry point, index ----------

# rule: CON-011
def test_ep_011_01_text_table_through_module_entry_point(env):
    """EP-011-01 (CLI half; page half is in test_compare_page.py): subprocess, text table, 1500 vs 2500 -> 2k / 3k / 1k (1.67)."""
    build_main(env, "S1", "ABC-1", main_in=1500)
    build_main(env, "S2", "ABC-2", main_in=2500)
    rc, out, err = run_proc(["ABC-1", "ABC-2"])
    assert (rc, err) == (0, "")
    assert table(out)[0] == ["Figure", "ABC-1", "ABC-2", HEADING]
    assert row(out, "Main-session tokens, input") == ["Main-session tokens, input", "2k", "3k", "1k (1.67)"]


# rule: CON-011
def test_ep_011_02_json_output_is_only_the_tree(env):
    """EP-011-02: subprocess --json prints only the JSON tree, raw numbers, version 1."""
    build_main(env, "S1", "ABC-1", main_in=1500)
    build_main(env, "S2", "ABC-2", main_in=2500)
    rc, out, err = run_proc(["ABC-1", "ABC-2", "--json"])
    assert (rc, err) == (0, "")
    tree = json.loads(out)
    assert set(tree) == {"a", "b", "diff", "version"}
    assert tree["version"] == 1
    assert (tree["a"]["key"], tree["b"]["key"]) == ("ABC-1", "ABC-2")
    assert (tree["a"]["tokens"]["main"]["input"], tree["b"]["tokens"]["main"]["input"]) == (1500, 2500)
    assert out == json.dumps(tree, sort_keys=True, indent=2) + "\n"


# rule: CON-011
def test_ep_011_03_no_argument_starts_the_console_not_the_cli(env, monkeypatch, capsys):
    """EP-011-03: argv without arguments -> server.main() once, compare_cli.main never."""
    from agent_console import server
    cmod = cli()
    started, compared = [], []
    monkeypatch.setattr(server, "main", lambda *a, **k: started.append((a, k)))
    monkeypatch.setattr(cmod, "main", lambda *a, **k: compared.append((a, k)))
    monkeypatch.setattr(sys, "argv", ["agent_console"])
    runpy.run_module("agent_console", run_name="__main__")
    assert started == [((), {})]
    assert compared == []
    cap = capsys.readouterr()
    assert (cap.out, cap.err) == ("", "")


# rule: CON-011
def test_ep_011_04_other_argument_starts_the_console_as_today(env, monkeypatch):
    """EP-011-04: argv[1] other than `compare` -> server.main() once, compare_cli.main never."""
    from agent_console import server
    cmod = cli()
    started, compared = [], []
    monkeypatch.setattr(server, "main", lambda *a, **k: started.append((a, k)))
    monkeypatch.setattr(cmod, "main", lambda *a, **k: compared.append((a, k)))
    monkeypatch.setattr(sys, "argv", ["agent_console", "serve"])
    runpy.run_module("agent_console", run_name="__main__")
    assert started == [((), {})]
    assert compared == []


# rule: CON-011
def test_ep_011_17_cli_never_fetches_the_claims_branch(env, monkeypatch):
    """EP-011-17: with fetching allowed again, the CLI still runs no git fetch and sets AGENT_CONSOLE_NO_FETCH=1 itself."""
    from agent_console import scope
    build_main(env, "S1", "ABC-1", main_in=1500)
    build_main(env, "S2", "ABC-2", main_in=2500)
    scan(env)                                                    # built while NO_FETCH=1 (env default)
    claims = env.tmp / "claims"
    claims.mkdir()
    subprocess.run(["git", "-C", str(claims), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(claims), "remote", "add", "origin", str(env.tmp / "no-such-remote")], check=True)
    monkeypatch.setenv("AGENT_CONSOLE_CLAIMS_REPO", str(claims))
    monkeypatch.delenv("AGENT_CONSOLE_NO_FETCH")
    monkeypatch.setattr(scope, "_last_fetch", 0.0)
    seen = []
    real = subprocess.run

    def spy(argv, *a, **k):
        seen.append(list(argv))
        return real(argv, *a, **k)

    monkeypatch.setattr(scope.subprocess, "run", spy)
    scope.refresh_claims(claims)                                 # positive control: the set-up can see a fetch
    assert any("fetch" in argv for argv in seen), "fixture cannot see a fetch"
    seen.clear()
    monkeypatch.setattr(scope, "_last_fetch", 0.0)
    assert cli().main(["ABC-1", "ABC-2"]) == 0
    assert not any("fetch" in argv for argv in seen)
    assert os.environ["AGENT_CONSOLE_NO_FETCH"] == "1"


# rule: CON-011
def test_ep_011_20_locked_index_exits_1_with_one_line(env, monkeypatch, capsys):
    """EP-011-20: Store() raising OperationalError -> exit 1, one exact line, no sqlite text, index untouched."""
    build_main(env, "S1", "ABC-1", main_in=1500)
    build_main(env, "S2", "ABC-2", main_in=2500)
    scan(env)
    cmod = cli()

    def raiser(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(cmod, "Store", raiser)
    before = snapshot(env)
    rc, out, err = run(["ABC-1", "ABC-2"], capsys)
    assert rc == 1
    assert out == ""
    assert err == f"compare: error: the index at {env.home / 'index.sqlite'} could not be opened or refreshed (OperationalError)\n"
    assert "database is locked" not in err
    assert snapshot(env) == before


# rule: CON-011
def test_ep_011_21_file_that_is_not_a_database_exits_1(env):
    """EP-011-21: subprocess, index.sqlite holds text -> exit 1, DatabaseError line, file unchanged."""
    build_main(env, "S1", "ABC-1", main_in=1500)
    build_main(env, "S2", "ABC-2", main_in=2500)
    env.home.mkdir(parents=True, exist_ok=True)
    db = env.home / "index.sqlite"
    db.write_bytes(b"this is not a sqlite file" * 10)
    before = sha(db)
    rc, out, err = run_proc(["ABC-1", "ABC-2"])
    assert rc == 1
    assert out == ""
    assert err == f"compare: error: the index at {db} could not be opened or refreshed (DatabaseError)\n"
    assert "file is not a database" not in err
    assert sha(db) == before


# rule: CON-011
def test_ep_011_22_scan_error_names_only_the_class(env, monkeypatch, capsys):
    """EP-011-22: a scan that fails inside rescan -> exit 1, the class name from progress["error"], no details."""
    from agent_console.store import Store
    build_main(env, "S1", "ABC-1", main_in=1500)
    build_main(env, "S2", "ABC-2", main_in=2500)

    def boom(self, *a, **k):
        raise ValueError("secret-detail-xyz")

    monkeypatch.setattr(Store, "ingest", boom)
    rc, out, err = run(["ABC-1", "ABC-2"], capsys)
    assert rc == 1
    assert out == ""
    assert err == f"compare: error: the index at {env.home / 'index.sqlite'} could not be opened or refreshed (ValueError)\n"
    assert "secret-detail-xyz" not in err
    assert "Traceback" not in err


# rule: CON-011
def test_ep_011_23_cli_never_writes_the_logs(env, capsys):
    """EP-011-23: text and --json runs leave every file under the log root byte-identical."""
    build_main(env, "S1", "ABC-1", main_in=1500, children=["ABC-1"])
    build_main(env, "S2", "ABC-2", main_in=2500)
    before = tree_hash(env.root)
    assert before
    assert run(["ABC-1", "ABC-2"], capsys)[0] == 0
    assert run(["ABC-1", "ABC-2", "--json"], capsys)[0] == 0
    assert tree_hash(env.root) == before


# ---------- CON-011: the guard (decision table DT-011-05 .. 13) ----------

# rule: CON-011
def test_dt_011_05_other_time_zone_is_refused(env, monkeypatch, capsys):
    """DT-011-05: tz differs -> exit 2, exact line naming `time zone`, nothing written."""
    db = baseline(env, capsys)
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    expect_refusal(env, capsys, differ(db, "time zone"))


# rule: CON-011
def test_dt_011_06_other_key_patterns_are_refused(env, monkeypatch, capsys):
    """DT-011-06: key patterns differ -> exit 2, exact line naming `key patterns`."""
    db = baseline(env, capsys)
    monkeypatch.setenv("AGENT_CONSOLE_KEY_PATTERNS", "[Q]+-[0-9]+")
    expect_refusal(env, capsys, differ(db, "key patterns"))


# rule: CON-011
def test_dt_011_07_index_copied_from_another_home_is_refused(env, monkeypatch, capsys):
    """DT-011-07: an index copied into home B (recorded home A) -> exit 2 naming `console home`; A and B unchanged."""
    baseline(env, capsys)
    gc.collect()
    home_b = env.tmp / "home_b"
    home_b.mkdir()
    for n in ("index.sqlite", "index.sqlite-wal"):
        if (env.home / n).exists():
            shutil.copy(env.home / n, home_b / n)
    monkeypatch.setenv("AGENT_CONSOLE_HOME", str(home_b))
    a_before = file_hashes(env.home)
    expect_refusal(env, capsys, differ(home_b / "index.sqlite", "console home"), home=home_b)
    assert file_hashes(env.home) == a_before


# rule: CON-011
def test_dt_011_08_other_checkout_is_refused(env, monkeypatch, capsys):
    """DT-011-08: AGENT_CONSOLE_REPO differs -> exit 2 naming `checkout`."""
    db = baseline(env, capsys)
    other = env.tmp / "other-checkout"
    other.mkdir()
    monkeypatch.setenv("AGENT_CONSOLE_REPO", str(other))
    expect_refusal(env, capsys, differ(db, "checkout"))


# rule: CON-011
def test_dt_011_09_other_schema_version_is_refused_without_a_reset(env, capsys):
    """DT-011-09: user_version != SCHEMA_VERSION -> exit 2 naming `schema version`; no reset of derived rows."""
    from agent_console.store import SCHEMA_VERSION
    db = baseline(env, capsys)
    gc.collect()
    con = sqlite3.connect(db)
    con.execute(f"PRAGMA user_version={SCHEMA_VERSION - 1}")
    con.close()
    before = db_state(env.home)
    assert before["user_version"] == SCHEMA_VERSION - 1 and before["runs"] > 0
    expect_refusal(env, capsys, differ(db, "schema version"))
    assert db_state(env.home) == before


# rule: CON-011
def test_dt_011_10_missing_home_and_checkout_rows_are_refused(env, capsys):
    """DT-011-10: meta rows home and repo_root absent -> exit 2, the `does not record` line, rows still absent."""
    db = baseline(env, capsys)
    gc.collect()
    delete_meta(env, "home", "repo_root")
    expect_refusal(env, capsys, missing(db, "console home, checkout"))
    assert not {"home", "repo_root"} & set(db_state(env.home)["meta"])


# rule: CON-011
def test_dt_011_11_one_differs_one_missing_names_both(env, monkeypatch, capsys):
    """DT-011-11: tz differs and home row missing -> the `built with another` form, fixed order."""
    db = baseline(env, capsys)
    gc.collect()
    delete_meta(env, "home")
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    expect_refusal(env, capsys, differ(db, "time zone, console home"))


# rule: CON-011
def test_dt_011_12_two_differences_are_both_named(env, monkeypatch, capsys):
    """DT-011-12: tz and checkout differ -> both named, fixed order."""
    db = baseline(env, capsys)
    other = env.tmp / "other-checkout"
    other.mkdir()
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    monkeypatch.setenv("AGENT_CONSOLE_REPO", str(other))
    expect_refusal(env, capsys, differ(db, "time zone, checkout"))


# rule: CON-011
def test_dt_011_13_matching_index_is_refreshed_not_refused(env, capsys):
    """DT-011-13: all five match -> the CLI refreshes from the logs (runs 1 -> 2), exit 0, logs untouched."""
    build_main(env, "S1", "EXP1-AAA", main_in=100, children=["EXP1-AAA"])
    build_main(env, "S2", "EXP1-BBB", main_in=100)
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB", "--json"], capsys)
    assert (rc, err) == (0, "")
    assert json.loads(out)["a"]["runs"]["total"] == 1
    build_main(env, "S1", "EXP1-AAA", main_in=100, children=["EXP1-AAA", "EXP1-AAA"])   # one more child, appended
    logs = tree_hash(env.root)
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB", "--json"], capsys)
    assert (rc, err) == (0, "")
    assert json.loads(out)["a"]["runs"]["total"] == 2
    meta = db_state(env.home)["meta"]
    assert meta["home"] == str(env.home.resolve())
    assert meta["repo_root"] == str(Path(env.repo).resolve())
    assert tree_hash(env.root) == logs


# ---------- CON-011: state transitions (ST-01 .. 03) ----------

# rule: CON-011
def test_tc_st_01_no_index_yet_is_built_and_printed(env, capsys):
    """TC-ST-01 (CI-011-14): no index in the console's own home -> built, table printed, exit 0, rows home / repo_root recorded."""
    build_main(env, "S1", "EXP1-AAA", main_in=100, children=["EXP1-AAA"])
    build_main(env, "S2", "EXP1-BBB", main_in=100, children=["EXP1-BBB"])
    assert not (env.home / "index.sqlite").exists()
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    assert rc == 0
    assert err == ""
    assert table(out)[0] == ["Figure", "EXP1-AAA", "EXP1-BBB", HEADING]
    meta = db_state(env.home)["meta"]
    assert meta["home"] == str(env.home.resolve())
    assert meta["repo_root"] == str(Path(env.repo).resolve())


# rule: CON-011
def test_tc_st_02_another_home_gets_its_own_index(env, monkeypatch, capsys):
    """TC-ST-02 (CI-011-15): home B has no index -> built there; home A's index stays byte-identical."""
    build_main(env, "S1", "EXP1-AAA", main_in=100, children=["EXP1-AAA"])
    build_main(env, "S2", "EXP1-BBB", main_in=100, children=["EXP1-BBB"])
    assert run(["EXP1-AAA", "EXP1-BBB"], capsys)[0] == 0
    gc.collect()
    a_state = db_state(env.home)
    a_before = (file_hashes(env.home), a_state)
    home_b = env.tmp / "home_b"
    monkeypatch.setenv("AGENT_CONSOLE_HOME", str(home_b))
    assert not (home_b / "index.sqlite").exists()
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    assert (rc, err) == (0, "")
    assert table(out)[0][1:3] == ["EXP1-AAA", "EXP1-BBB"]
    assert db_state(home_b)["meta"]["home"] == str(home_b.resolve())
    gc.collect()
    state = db_state(env.home)
    assert (file_hashes(env.home), state) == a_before


# rule: CON-011
def test_tc_st_03_old_index_refused_then_console_start_then_cli_works(env, capsys):
    """TC-ST-03 (CI-011-16): index without home / repo_root rows -> refused, untouched; Store() writes the rows; CLI then exits 0."""
    from agent_console.store import Store
    build_main(env, "S1", "EXP1-AAA", main_in=100, children=["EXP1-AAA"])
    build_main(env, "S2", "EXP1-BBB", main_in=100)
    assert run(["EXP1-AAA", "EXP1-BBB"], capsys)[0] == 0
    db = env.home / "index.sqlite"
    gc.collect()
    delete_meta(env, "home", "repo_root")
    runs_before = db_state(env.home)["runs"]
    expect_refusal(env, capsys, missing(db, "console home, checkout"))
    st = Store()                                               # console start
    st.db.close()
    state = db_state(env.home)
    assert {"home", "repo_root"} <= set(state["meta"])
    assert state["runs"] == runs_before
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    assert (rc, err) == (0, "")
    assert table(out)[0][1:3] == ["EXP1-AAA", "EXP1-BBB"]


# ---------- CON-027: unknown keys and keys known without a main session ----------

def ok200(out, a, b, runs_a, runs_b, diff_cell, no_main=True):
    """OK200 for the CLI: header, `Role runs` line, and the `no main session` cell of the main rows."""
    assert table(out)[0] == ["Figure", a, b, HEADING]
    assert row(out, "Role runs") == ["Role runs", runs_a, runs_b, diff_cell]
    if no_main:
        assert row(out, "Main-session tokens, input")[1] == "no main session"


# rule: CON-027
def test_ep_027_01_key_known_through_a_sub_run_only(env, capsys):
    """EP-027-01 (CLI half): ABC-1 only has a sub run -> 1 run, no main session."""
    nomain(env, "ABC-1")
    rc, out, err = run(["ABC-1", "ABC-9"], capsys)
    assert (rc, err) == (0, "")
    ok200(out, "ABC-1", "ABC-9", "1", "2", "1 (2.00)")
    a = data("ABC-1", capsys)
    assert (a["runs"]["total"], a["main_sessions"]) == (1, 0)


# rule: CON-027
def test_ep_027_02_own_key_of_a_main_that_belongs_elsewhere(env, capsys):
    """EP-027-02 (CLI half): ABC-1 is only the own key of a main whose effective key is ABC-2 -> 0 runs, no main session."""
    build_main(env, "S1", "ABC-1", children=["ABC-2", "ABC-2", "ABC-2"])
    scan(env)
    con = sqlite3.connect(env.home / "index.sqlite")
    assert con.execute("SELECT ticket, ticket_eff FROM runs WHERE kind='main'").fetchall() == [("ABC-1", "ABC-2")]
    con.close()
    rc, out, err = run(["ABC-1", "ABC-2"], capsys)
    assert (rc, err) == (0, "")
    ok200(out, "ABC-1", "ABC-2", "0", "3", "3 (n/a)")
    a = data("ABC-1", capsys)
    assert (a["runs"]["total"], a["main_sessions"]) == (0, 0)
    assert a["tokens"]["main"] == "no main session"


# rule: CON-027
def test_ep_027_03_key_known_only_from_a_counted_spawn_without_a_run_file(env, capsys):
    """EP-027-03 (CLI half): ABC-3 is on one spawn with an error result and no run file -> 1 run, wall 0 min."""
    build_main(env, "S9", "ABC-9", children=["ABC-9", "ABC-9", "ABC-1", {"key": "ABC-3", "file": False, "result": "err"}])
    assert data("ABC-9", capsys)["runs"]["total"] == 2
    rc, out, err = run(["ABC-3", "ABC-9"], capsys)
    assert (rc, err) == (0, "")
    ok200(out, "ABC-3", "ABC-9", "1", "2", "1 (2.00)")
    assert row(out, "Wall time")[1] == "0 min"
    a = data("ABC-3", capsys)
    assert (a["runs"]["total"], a["time_s"]["wall"]) == (1, 0)


# rule: CON-027
def test_ep_027_04_key_stays_known_after_its_run_file_is_deleted(env, capsys):
    """EP-027-04 (CLI half): the run file of ABC-1 deleted after a scan -> still known, 1 run, not failed."""
    subs = nomain(env, "ABC-1")
    scan(env)
    subs[2].unlink()                                           # ABC-1 is child 2
    rc, out, err = run(["ABC-1", "ABC-9"], capsys)
    assert (rc, err) == (0, "")
    ok200(out, "ABC-1", "ABC-9", "1", "2", "1 (2.00)")
    a = data("ABC-1", capsys)
    assert (a["runs"]["total"], a["runs"]["failed"]) == (1, 0)


# rule: CON-027
def test_ep_027_06_unknown_key_is_one_line_on_stderr_exit_2(env):
    """EP-027-06: subprocess, text and --json: unknown key -> exit 2, empty stdout, the exact one line."""
    build_main(env, "S9", "ABC-9", main_in=500)
    for extra in ([], ["--json"]):
        rc, out, err = run_proc(["ABC-404", "ABC-9", *extra])
        assert (rc, out) == (2, "")
        assert err == "compare: unknown ticket key: ABC-404\n"


# rule: CON-027
def test_ep_027_08_both_keys_unknown_a_first(env, capsys):
    """EP-027-08: both unknown -> one line naming a then b."""
    build_main(env, "S9", "ABC-9", main_in=500)
    rc, out, err = run(["ABC-404", "ABC-405"], capsys)
    assert (rc, out) == (2, "")
    assert err == "compare: unknown ticket keys: ABC-404, ABC-405\n"


# rule: CON-027
def test_ep_027_09_same_unknown_key_twice_is_named_once(env, capsys):
    """EP-027-09 (CLI half): ABC-404 twice -> singular line; compare.unknown_keys names it once."""
    build_main(env, "S9", "ABC-9", main_in=500)
    rc, out, err = run(["ABC-404", "ABC-404"], capsys)
    assert (rc, out) == (2, "")
    assert err == "compare: unknown ticket key: ABC-404\n"
    from agent_console import compare
    from agent_console.store import Store
    st = Store()
    db = st.reader()
    try:
        assert compare.unknown_keys(db, "ABC-404", "ABC-404") == ["ABC-404"]
    finally:
        db.close()
        st.db.close()


# rule: CON-027
def test_ep_027_10_key_case_matters(env, capsys):
    """EP-027-10 (CLI half): abc-1 is not ABC-1 -> unknown, printed as typed."""
    build_main(env, "S1", "ABC-1", main_in=500)
    build_main(env, "S9", "ABC-9", main_in=500)
    rc, out, err = run(["abc-1", "ABC-9"], capsys)
    assert (rc, out) == (2, "")
    assert err == "compare: unknown ticket key: abc-1\n"


# rule: CON-027
def test_ep_027_11_spawn_without_result_or_run_file_does_not_make_a_key(env, capsys):
    """EP-027-11 (CLI half): ABC-7 only on a spawn with no result and no run file -> unknown."""
    build_main(env, "S9", "ABC-9", main_in=500, children=[{"key": "ABC-7", "file": False, "result": None}])
    rc, out, err = run(["ABC-7", "ABC-9"], capsys)
    assert (rc, out) == (2, "")
    assert err == "compare: unknown ticket key: ABC-7\n"


# rule: CON-027
def test_ep_027_12_old_logs_still_count(env, capsys):
    """EP-027-12 (CLI half): a key whose records are all months old is known; the comparison has no period."""
    old = "2026-03-01"
    build_main(env, "S8", "ABC-9", day=old, children=["ABC-9", "ABC-9", "ABC-8"])
    build_main(env, "S7", "ABC-7", main_in=1, day=old)
    rc, out, err = run(["ABC-8", "ABC-9"], capsys)
    assert (rc, err) == (0, "")
    ok200(out, "ABC-8", "ABC-9", "1", "2", "1 (2.00)")
    assert data("ABC-8", capsys)["runs"]["total"] == 1


# rule: CON-027
# rule: CON-011
def test_dt_027_15_refusal_wins_over_unknown_keys(env, monkeypatch, capsys):
    """DT-027-15: guard refusal and unknown keys together -> the refusal line (exit 2), not the unknown-key line."""
    db = baseline(env, capsys)
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    expect_refusal(env, capsys, differ(db, "time zone"), args=("EXP1-NOPE", "EXP1-NOPE2"))


# ---------- CON-031: read-only, no new dependency ----------

# rule: CON-031
def test_ep_031_04_three_keys_are_a_usage_error(env, capsys):
    """EP-031-04 (CLI half; CI-034-11, DT-034-11): a third key -> exit 2, the two usage lines, nothing on stdout."""
    for s, k in (("S1", "ABC-1"), ("S9", "ABC-9"), ("S7", "ABC-77")):
        build_main(env, s, k, main_in=500)
    rc, out, err = run(["ABC-1", "ABC-9", "ABC-77"], capsys)
    assert (rc, out) == (2, "")
    assert err == usage_err("unrecognized arguments: ABC-77")


# rule: CON-031
def test_tc_cl_02_new_modules_import_only_stdlib_and_known_packages():
    """TC-CL-02 (CI-031-01, automated part): every import in the four new modules is stdlib, the package itself, agent_scoring, or in requirements.txt."""
    pkg = CONSOLE / "agent_console"
    files = [pkg / f"{n}.py" for n in ("compare", "compare_format", "compare_cli", "compare_page")]
    assert [f.name for f in files if not f.exists()] == []
    wanted = {re.split(r"[<>=!~\[; ]", ln.strip(), maxsplit=1)[0].lower().replace("_", "-")
              for ln in (CONSOLE / "requirements.txt").read_text().splitlines() if ln.strip() and not ln.startswith("#")}
    listed = {imp for imp, dists in metadata.packages_distributions().items() if {d.lower().replace("_", "-") for d in dists} & wanted}
    bad = []
    for f in files:
        for node in ast.walk(ast.parse(f.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            for n in names:
                top = n.split(".")[0]
                if top and top not in sys.stdlib_module_names and top not in {"agent_console", "agent_scoring"} | listed:
                    bad.append((f.name, n))
    assert bad == []


# ---------- CON-034: usage errors (argparse runs before the guard and Store) ----------

# rule: CON-034
def test_dt_034_07_no_keys_is_a_usage_error(env, monkeypatch, capsys):
    """DT-034-07: no keys -> exit 2, two exact stderr lines, no index file, console not started."""
    from agent_console import server
    started = []
    monkeypatch.setattr(server, "main", lambda *a, **k: started.append(1))
    rc, out, err = run([], capsys)
    assert (rc, out) == (2, "")
    assert err == usage_err("the following arguments are required: KEY_A, KEY_B")
    assert not (env.home / "index.sqlite").exists()
    assert started == []


# rule: CON-034
def test_dt_034_08_one_key_is_a_usage_error(env, capsys):
    """DT-034-08: one key -> the second key is required."""
    rc, out, err = run(["EXP1-AAA"], capsys)
    assert (rc, out) == (2, "")
    assert err == usage_err("the following arguments are required: KEY_B")
    assert not (env.home / "index.sqlite").exists()


# rule: CON-034
def test_dt_034_09_empty_key_is_a_usage_error(env, capsys):
    """DT-034-09: an empty second key -> `empty key: KEY_B`."""
    rc, out, err = run(["EXP1-AAA", ""], capsys)
    assert (rc, out) == (2, "")
    assert err == usage_err("empty key: KEY_B")
    assert not (env.home / "index.sqlite").exists()


# rule: CON-034
def test_dt_034_10_blank_key_is_a_usage_error(env, capsys):
    """DT-034-10: a second key of only spaces -> `empty key: KEY_B`."""
    rc, out, err = run(["EXP1-AAA", "  "], capsys)
    assert (rc, out) == (2, "")
    assert err == usage_err("empty key: KEY_B")
    assert not (env.home / "index.sqlite").exists()


# ---------- CON-035: no raw log text in the output ----------

def sentinel_fixture(env):
    extra = [assistant("sent-a", model="m-one", u=usage(5, 0), t=4, blocks=[{"type": "text", "text": "SENT-ASSIST-9f3a"}]),
             assistant("sent-b", model="m-one", u=usage(5, 0), t=5, blocks=[tool_use("sb1", "Bash", command="SENT-TOOLIN-9f3a")])]
    res = tool_result("sb1", t=6)
    res["message"]["content"][0]["content"] = "SENT-TOOLRES-9f3a"
    build_main(env, "S1", "ABC-1", extra=[*extra, res], prompt="[ABC-1] go SENT-USER-9f3a",
               children=[{"key": "ABC-1", "prompt": "SENT-PROMPT-9f3a", "text": "SENT-SUBTEXT-9f3a"}])
    build_main(env, "S9", "ABC-9", main_in=500)


# rule: CON-035
def test_ep_035_01_text_output_carries_no_log_text(env, capsys):
    """EP-035-01: sentinels in prompts, answers, tool input and output, sub-agent text never reach the text table."""
    sentinel_fixture(env)
    rc, out, err = run(["ABC-1", "ABC-9"], capsys)
    assert rc == 0
    assert out.strip()
    assert "SENT-" not in out + err


# rule: CON-035
def test_ep_035_02_json_output_carries_no_log_text(env, capsys):
    """EP-035-02: the same for --json."""
    sentinel_fixture(env)
    rc, out, err = run(["ABC-1", "ABC-9", "--json"], capsys)
    assert rc == 0
    assert json.loads(out)["a"]["key"] == "ABC-1"
    assert "SENT-" not in out + err


# rule: CON-035
def test_ep_035_04_denial_and_api_error_text_never_appear(env, capsys):
    """EP-035-04 (CLI half): two failed runs (denied tool, API error) -> counted as failed, none of their text printed."""
    build_main(env, "S1", "ABC-1", main_in=500,
               children=[{"key": "ABC-1", "file": False}, {"key": "ABC-1", "file": False, "role": "tester"}])
    deny = tool_result("b1", True, t=30, session="S1")
    deny["message"]["content"][0]["content"] = "Permission to use Bash has been denied SENT-DENY-9f3a The user doesn't want to proceed"
    err_rec = api_error(t=31, session="S1", message="SENT-APIERR-9f3a arn:aws:sts::000000000000:assumed-role/x")
    for rec in (deny, err_rec):
        rec["isSidechain"] = True
    deny["agentId"], err_rec["agentId"] = "S1-ag0", "S1-ag1"
    add_sub(env.root, "S1", "S1-ag0", "builder", [assistant("s1-a", model="m-one", u=usage(10, 0), t=20, session="S1", agent="S1-ag0",
                                                          blocks=[tool_use("b1", "Bash", command="x")]), deny], "S1-t0")
    add_sub(env.root, "S1", "S1-ag1", "tester", [assistant("s1-b", model="m-one", u=usage(10, 0), t=21, session="S1", agent="S1-ag1"), err_rec], "S1-t1")
    build_main(env, "S9", "ABC-9", main_in=500)
    rc_t, out_t, err_t = run(["ABC-1", "ABC-9"], capsys)
    rc_j, out_j, err_j = run(["ABC-1", "ABC-9", "--json"], capsys)
    rc_u, out_u, err_u = run(["ABC-404", "ABC-9"], capsys)
    assert (rc_t, rc_j, rc_u) == (0, 0, 2)
    assert json.loads(out_j)["a"]["runs"]["failed"] == 2
    for text in (out_t, err_t, out_j, err_j, out_u, err_u):
        for needle in ("SENT-", "Permission to use", "The user doesn't want to proceed", "arn:aws"):
            assert needle not in text


# ---------- EXP1-R22C security and hostile findings (confirmation tests) ----------

def bad_main(env, variant):
    """SEC-1: a main session of EXP1-BAD whose records carry a malformed uuid, timestamp or tool id."""
    sess = "SB"
    recs = [user_prompt("[EXP1-BAD] start", t=0, session=sess)]
    stop = assistant("sb-1", model="m-one", u=usage(10, 0), t=5, session=sess)
    stop["message"]["stop_reason"] = "end_turn"
    if variant == "uuid":
        stop["uuid"] = ["x"]
    elif variant == "timestamp":
        stop["timestamp"] = 12345
    elif variant == "tool_id":
        stop["message"]["content"] = [tool_use(["x"], "AskUserQuestion", q="q")]
        recs.append(stop)
        res = tool_result(["x"], err=True, t=8, session=sess)
        res["message"]["content"][0]["content"] = "rejected"
        stop = res
    recs.append(stop)
    recs.append(user_prompt("go on", t=3000, session=sess))
    recs[-1]["uuid"] = "up-late"
    last = recs[-1]
    if variant == "timestamp":
        last["timestamp"] = ["bad"]
    write_jsonl(env.root / PROJECT / f"{sess}.jsonl", recs)


# rule: CON-011
# rule: CON-033
def test_sec_1_cli_malformed_main_record_uuid_does_not_crash(env, capsys):
    """SEC-1: `uuid` is a list -> exit 0, or exit 1 with exactly one stderr line and no traceback."""
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    bad_main(env, "uuid")
    _sec1_check(capsys)


# rule: CON-011
# rule: CON-033
def test_sec_1_cli_malformed_main_record_timestamp_does_not_crash(env, capsys):
    """SEC-1: a non-string timestamp -> exit 0, or exit 1 with exactly one stderr line and no traceback."""
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    bad_main(env, "timestamp")
    _sec1_check(capsys)


# rule: CON-011
# rule: CON-033
def test_sec_1_cli_malformed_main_record_tool_id_does_not_crash(env, capsys):
    """SEC-1: a tool_use id and a tool_use_id that are lists -> exit 0, or one stderr line, no traceback."""
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    bad_main(env, "tool_id")
    _sec1_check(capsys)


def _sec1_check(capsys):
    try:
        rc, out, err = run(["EXP1-AAA", "EXP1-BAD", "--json"], capsys)
    except Exception as e:      # a traceback is what the finding is about
        raise AssertionError(f"the CLI let {type(e).__name__} escape: {e}") from e
    assert rc in (0, 1), (rc, err)
    if rc == 0:
        json.loads(out)
    else:
        assert out == "" and len(err.splitlines()) == 1 and "Traceback" not in err, err


# rule: CON-011
def test_sec_2_refusal_creates_no_new_file_in_the_home(env, monkeypatch, capsys):
    """SEC-2: a refusal (other time zone) leaves the directory listing of the home as it was (no -wal / -shm)."""
    baseline(env, capsys)
    gc.collect()
    before = sorted(p.name for p in env.home.iterdir())
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    assert rc == 2, err
    gc.collect()
    assert sorted(p.name for p in env.home.iterdir()) == before


# rule: CON-035
def test_sec_3_text_output_shows_no_raw_control_characters_of_a_model_name(env, capsys):
    """SEC-3: a model name with ESC, BEL and a newline is printed without raw control characters and without a forged line."""
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    evil = "m\x1b[2J\x1b[31mRED\x1b]0;TITLE\x07\nFAKE-ROW | 1 | 2"
    recs = [user_prompt("[EXP1-EVIL] start", t=0, session="SE"), assistant("se-1", model=evil, u=usage(50, 5), t=10, session="SE")]
    write_jsonl(env.root / PROJECT / "SE.jsonl", recs)
    rc, out, err = run(["EXP1-AAA", "EXP1-EVIL"], capsys)
    assert rc == 0, err
    assert not re.search(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", out), repr(out)
    assert not any(ln.startswith("FAKE-ROW") for ln in out.splitlines()), out


# rule: CON-011
def test_sec_4_dangling_index_symlink_is_refused_and_creates_nothing(env, capsys):
    """SEC-4: index.sqlite is a dangling symlink -> exit 2, and nothing is created at the link target."""
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    build_main(env, "S2", "EXP1-BBB", main_in=100)
    victim = env.tmp / "victim"
    victim.mkdir()
    target = victim / "planted.sqlite"
    env.home.mkdir(parents=True, exist_ok=True)
    (env.home / "index.sqlite").symlink_to(target)
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    assert not target.exists() and list(victim.iterdir()) == []
    assert rc == 2 and out == "" and len(err.splitlines()) == 1, (rc, err)


# rule: CON-027
# rule: CON-035
def test_hv_2_unknown_key_with_a_newline_is_one_stderr_line(env, capsys):
    """HV-2: a typed key with a newline -> exactly one stderr line, the newline shown as text."""
    baseline(env, capsys)
    rc, out, err = run(["NOPE\nINJECTED-LINE", "EXP1-BBB"], capsys)
    assert rc == 2 and out == ""
    assert err.count("\n") == 1 and err.endswith("\n"), repr(err)
    assert "INJECTED-LINE" in err


# rule: CON-027
# rule: CON-035
def test_hv_2_unknown_key_with_an_escape_is_shown_as_text(env, capsys):
    """HV-2: a typed key with ESC -> one stderr line, no raw control character."""
    baseline(env, capsys)
    rc, out, err = run(["\x1b[2J\x1b[31mFAKE", "EXP1-BBB"], capsys)
    assert rc == 2 and out == ""
    assert err.count("\n") == 1 and not re.search(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", err), repr(err)
    assert "FAKE" in err


# ---------- EXP1-R22C code review 6: BD4 skip, argparse echo, symlink to a valid index, exact escapes ----------

def _bd4_tree(env, capsys, variant):
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    bad_main(env, variant)
    rc, out, err = run(["EXP1-AAA", "EXP1-BAD", "--json"], capsys)
    assert (rc, err) == (0, ""), (rc, err)
    return json.loads(out)


# rule: CON-022
# rule: CON-011
def test_bd4_a_list_uuid_record_is_skipped_and_the_gap_is_counted_exactly(env, capsys):
    """BD4 (review 6, 1): a stop record whose uuid is a list is read as having no uuid: rc 0, wait 5 -> 3000 = 2995.0."""
    tree = _bd4_tree(env, capsys, "uuid")
    assert tree["b"]["time_s"]["wait"] == 2995.0
    assert tree["b"]["time_s"]["wait_over_2h"] == 0.0
    assert tree["a"]["time_s"]["wait"] == 0.0


# rule: CON-027
# rule: CON-035
def test_argparse_error_shows_a_typed_argument_as_text_on_two_lines(env, capsys):
    """Review 6, 2: a third argument with a newline and ESC -> exit 2, exactly 2 stderr lines (usage + error), the characters shown as \\xNN."""
    baseline(env, capsys)
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB", "C\nD\x1b[2J"], capsys)
    assert rc == 2 and out == ""
    assert len(err.split("\n")) == 3 and err.endswith("\n"), repr(err)
    assert err.splitlines()[0] == USAGE_HEAD.rstrip("\n")
    assert "C\\x0aD\\x1b[2J" in err, repr(err)
    assert "\x1b" not in err and err.count("\n") == 2


# rule: CON-011
# rule: CON-027
def test_a_symlink_to_a_valid_matching_index_is_refused_and_the_target_is_unchanged(env, capsys):
    """Review 6, 3: index.sqlite is a symlink to a valid index built with these settings -> exit 2, the exact BD2 line, the target untouched."""
    baseline(env, capsys)
    gc.collect()
    real = env.tmp / "elsewhere"
    real.mkdir()
    link = env.home / "index.sqlite"
    shutil.move(str(link), str(real / "real.sqlite"))
    for side in env.home.glob("index.sqlite-*"):
        shutil.move(str(side), str(real / side.name.replace("index.sqlite", "real.sqlite")))
    link.symlink_to(real / "real.sqlite")
    sha = hashlib.sha256((real / "real.sqlite").read_bytes()).hexdigest()
    listing, home_listing = sorted(p.name for p in real.iterdir()), sorted(p.name for p in env.home.iterdir())
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    gc.collect()
    assert rc == 2 and out == ""
    assert err == f"compare: refused: the index at {link} is a symbolic link (nothing written)\n"
    assert hashlib.sha256((real / "real.sqlite").read_bytes()).hexdigest() == sha
    assert sorted(p.name for p in real.iterdir()) == listing
    assert sorted(p.name for p in env.home.iterdir()) == home_listing


# rule: CON-027
# rule: CON-035
def test_hv_2_exact_unknown_key_line_shows_a_newline_as_backslash_x0a(env, capsys):
    """HV-2 exact: the unknown-key line is `NOPE\\x0aINJECTED-LINE` (not `?`, not removed)."""
    baseline(env, capsys)
    rc, out, err = run(["NOPE\nINJECTED-LINE", "EXP1-BBB"], capsys)
    assert (rc, out) == (2, "")
    assert err == "compare: unknown ticket key: NOPE\\x0aINJECTED-LINE\n"


# rule: CON-027
# rule: CON-035
def test_hv_2_exact_unknown_key_line_shows_escape_as_backslash_x1b(env, capsys):
    """HV-2 exact: ESC is printed as the text `\\x1b`."""
    baseline(env, capsys)
    rc, out, err = run(["\x1b[2J\x1b[31mFAKE", "EXP1-BBB"], capsys)
    assert (rc, out) == (2, "")
    assert err == "compare: unknown ticket key: \\x1b[2J\\x1b[31mFAKE\n"


# rule: CON-035
def test_sec_3_exact_model_name_is_shown_with_backslash_escapes(env, capsys):
    """SEC-3 exact: the model name in a row label is printed with `\\xNN` for ESC, BEL and the newline."""
    px(env)
    build_main(env, "S1", "EXP1-AAA", main_in=100)
    evil = "m\x1b[2J\x1b[31mRED\x1b]0;TITLE\x07\nFAKE-ROW | 1 | 2"
    recs = [user_prompt("[EXP1-EVIL] start", t=0, session="SE"), assistant("se-1", model=evil, u=usage(50, 5), t=10, session="SE")]
    write_jsonl(env.root / PROJECT / "SE.jsonl", recs)
    rc, out, err = run(["EXP1-AAA", "EXP1-EVIL"], capsys)
    assert rc == 0, err
    assert "Tokens, m\\x1b[2J\\x1b[31mRED\\x1b]0;TITLE\\x07\\x0aFAKE-ROW | 1 | 2, input" in out


# rule: CON-011
def test_new_3_refusal_of_a_wal_without_shm_creates_no_file(env, monkeypatch, capsys):
    """NEW-3: a home with index.sqlite and index.sqlite-wal but no -shm, refused (other time zone) -> exit 2, the exact differ line, no new file."""
    baseline(env, capsys)
    gc.collect()
    home2 = env.tmp / "home2"
    home2.mkdir(mode=0o700)
    live = sqlite3.connect(env.home / "index.sqlite")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.execute("INSERT OR REPLACE INTO meta VALUES('probe', '1')")
    live.commit()
    for name in ("index.sqlite", "index.sqlite-wal"):
        shutil.copy(env.home / name, home2 / name)
    live.close()
    assert (home2 / "index.sqlite-wal").stat().st_size > 0 and not (home2 / "index.sqlite-shm").exists()
    before = sorted(p.name for p in home2.iterdir())
    sha = hashlib.sha256((home2 / "index.sqlite-wal").read_bytes()).hexdigest()
    monkeypatch.setenv("AGENT_CONSOLE_HOME", str(home2))
    monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    gc.collect()
    assert rc == 2 and out == "", (rc, err)
    assert err == differ(home2 / "index.sqlite", "time zone, console home")
    assert sorted(p.name for p in home2.iterdir()) == before
    assert hashlib.sha256((home2 / "index.sqlite-wal").read_bytes()).hexdigest() == sha


# rule: CON-011
def test_new_3_a_time_zone_row_only_in_the_wal_is_refused_and_creates_no_file(env, monkeypatch, capsys):
    """Review 7, 3: the differing tz row is only in the -wal (autocheckpoint off, no -shm) -> exit 2, the exact line, no file created."""
    baseline(env, capsys)
    gc.collect()
    home2 = env.tmp / "home3"
    home2.mkdir(mode=0o700)
    live = sqlite3.connect(env.home / "index.sqlite")
    live.execute("PRAGMA wal_autocheckpoint=0")
    live.execute("INSERT OR REPLACE INTO meta VALUES('tz', 'Pacific/Auckland')")
    live.commit()
    for name in ("index.sqlite", "index.sqlite-wal"):
        shutil.copy(env.home / name, home2 / name)
    live.close()
    assert (home2 / "index.sqlite-wal").stat().st_size > 0 and not (home2 / "index.sqlite-shm").exists()
    main_only = sqlite3.connect(f"file:{home2 / 'index.sqlite'}?mode=ro&immutable=1", uri=True)
    assert main_only.execute("SELECT v FROM meta WHERE k='tz'").fetchone()[0] == "Europe/Madrid"   # the main file alone shows no difference
    main_only.close()
    before = sorted(p.name for p in home2.iterdir())
    monkeypatch.setenv("AGENT_CONSOLE_HOME", str(home2))
    rc, out, err = run(["EXP1-AAA", "EXP1-BBB"], capsys)
    gc.collect()
    assert rc == 2 and out == "", (rc, err)
    assert err == differ(home2 / "index.sqlite", "time zone, console home")
    assert sorted(p.name for p in home2.iterdir()) == before
