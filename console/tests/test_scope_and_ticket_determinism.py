"""Scope reasons (tree / worktree / repo remote / parent session) and deterministic ticket keys."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


from agent_console.store import Store
from conftest import PROJECT, add_sub, assistant, tool_use, user_prompt, write_jsonl

PROJECT_DIR = "/work/app"
WT = "/work/worktrees"
PKG = Path(__file__).resolve().parents[1]


def scopes(s):
    db = s.reader()
    try:
        return {r["run_id"]: (r["scope"], r["scope_reason"]) for r in db.execute("SELECT run_id, scope, scope_reason FROM runs")}
    finally:
        db.close()


def session(env, sid, cwd, d=PROJECT):
    write_jsonl(env.root / d / f"{sid}.jsonl", [user_prompt("x", session=sid, cwd=cwd), assistant(f"{sid}-m", session=sid, cwd=cwd)])


def test_reasons_tree_worktree_other(env):
    session(env, "T", f"{PROJECT_DIR}/sub dir")
    session(env, "W", f"{WT}/app-x/sub", d="-wt")
    session(env, "O", "/home/dev/elsewhere", d="-oth")
    s = Store()
    s.ingest()
    assert scopes(s) == {"T": ("project", "tree"), "W": ("project", "worktree"), "O": ("other", "other")}


def make_checkout(path: Path, url: str) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", url], check=True, capture_output=True)


def test_repo_remote_checkout_outside_the_trees_counts_as_project_and_is_remembered(env):
    co = env.tmp / "snapshot-checkout"
    make_checkout(co, "git@git.example.internal:team/example-app.git")
    foreign = env.tmp / "foreign-checkout"
    make_checkout(foreign, "git@github.com:someone/else.git")
    session(env, "R", str(co / "api"), d="-r")
    session(env, "F", str(foreign), d="-f")
    s = Store()
    s.ingest()
    assert scopes(s) == {"R": ("project", "repo remote"), "F": ("other", "other")}
    shutil.rmtree(co)  # temp checkouts are deleted later: the remote seen earlier is remembered
    s2 = Store()
    s2.rescan(wait=True, min_interval=0)
    assert scopes(s2)["R"] == ("project", "repo remote")


def test_worktree_with_a_git_file_resolves_its_origin_through_commondir(env):
    main = env.tmp / "main"
    make_checkout(main, "git@git.example.internal:team/example-app.git")
    subprocess.run(["git", "-C", str(main), "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"], check=True, capture_output=True)
    linked = env.tmp / "linked"
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", "-b", "x", str(linked)], check=True, capture_output=True)
    assert (linked / ".git").is_file()
    session(env, "L", str(linked), d="-l")
    s = Store()
    s.ingest()
    assert scopes(s)["L"] == ("project", "repo remote")


def test_subagent_with_a_temp_cwd_counts_with_the_session_that_spawned_it(env):
    session(env, "S1", f"{PROJECT_DIR}/sub dir")
    add_sub(env.root, "S1", "a1", "builder", [assistant("a1m", agent="a1", cwd="/private/tmp/gone-checkout")], "toolu_1")
    s = Store()
    s.ingest()
    assert scopes(s)["S1:a1"] == ("project", "parent session")
    session(env, "X", "/home/dev/elsewhere", d="-oth")
    add_sub(env.root, "X", "x1", "builder", [assistant("x1m", agent="x1", session="X", cwd="/private/tmp/gone-checkout")], "toolu_2", )
    s.ingest()
    assert scopes(s)["X:x1"] == ("other", "other")


# ---------- deterministic ticket keys ----------
def build_ticket_fixture(root: Path, names: list[str]) -> None:
    """A parent session with tied git evidence, a two-key command, and sub-runs spawned at different times."""
    spawn = [tool_use("toolu_early", "Agent", subagent_type="builder", description="no key here", prompt="p"),
             tool_use("toolu_late", "Agent", subagent_type="builder", description="no key here either", prompt="p")]
    recs = [user_prompt("work on PROJ-60012 please", t=0, day="2026-10-22"),
            assistant("e", t=5, day="2026-10-22", blocks=[spawn[0]]),
            assistant("g1", t=0, day="2026-10-23", blocks=[tool_use("g1", "Bash", command="git checkout PROJ-60018 && git merge PROJ-60042")]),
            assistant("g2", t=1, day="2026-10-23", blocks=[tool_use("g2", "Bash", command="git switch PROJ-60042")]),
            assistant("g3", t=2, day="2026-10-23", blocks=[tool_use("g3", "Bash", command="git switch PROJ-60018")]),
            assistant("l", t=5, day="2026-10-24", blocks=[spawn[1]])]
    files = {"S1.jsonl": recs, "S2.jsonl": [user_prompt("again PROJ-60066", session="S2", day="2026-10-20"), assistant("s2", session="S2")],
             "S3.jsonl": [user_prompt("third", session="S3"), assistant("s3", session="S3")]}
    for name in names:
        write_jsonl(root / PROJECT / name, files[name])
    add_sub(root, "S1", "early", "builder", [assistant("early-m", agent="early", day="2026-10-22", t=10)], "toolu_early")
    add_sub(root, "S1", "late", "builder", [assistant("late-m", agent="late", day="2026-10-24", t=10)], "toolu_late")


def tickets_json(root: Path, home: Path, seed: str) -> dict:
    code = ("import json,sys; sys.path.insert(0, %r); from agent_console.store import Store; s=Store(); s.ingest(); db=s.reader(); "
            "print(json.dumps({r['run_id']:[r['ticket'],r['ticket_src'],r['ticket_via']] for r in db.execute('SELECT * FROM runs')}, sort_keys=True))") % str(PKG)
    env = {**os.environ, "PYTHONHASHSEED": seed, "AGENT_CONSOLE_LOG_ROOT": str(root), "AGENT_CONSOLE_HOME": str(home), "AGENT_CONSOLE_NO_FETCH": "1"}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_same_files_any_order_any_hash_seed_give_identical_keys(env, tmp_path):
    runs = []
    for i, (names, seed) in enumerate([(["S1.jsonl", "S2.jsonl", "S3.jsonl"], "0"), (["S3.jsonl", "S2.jsonl", "S1.jsonl"], "1"),
                                       (["S2.jsonl", "S3.jsonl", "S1.jsonl"], "12345")]):
        root = tmp_path / f"root{i}"
        build_ticket_fixture(root, names)
        runs.append(tickets_json(root, tmp_path / f"home{i}", seed))
        runs.append(tickets_json(root, tmp_path / f"home{i}", seed))  # and indexing a second time on the same state
    assert all(r == runs[0] for r in runs)
    assert runs[0]["S1"][0] == "PROJ-60018"  # two tied keys (22222 x2 vs 33333 x2): the smaller key wins, always


def test_subrun_takes_the_key_in_force_when_it_started_not_the_session_majority(env):
    build_ticket_fixture(env.root, ["S1.jsonl"])
    s = Store()
    s.ingest()
    db = s.reader()
    r = {x["run_id"]: dict(x) for x in db.execute("SELECT * FROM runs")}
    assert (r["S1:early"]["ticket"], r["S1:early"]["ticket_src"], r["S1:early"]["ticket_via"]) == ("PROJ-60012", "parent", "prompt")
    assert (r["S1:late"]["ticket"], r["S1:late"]["ticket_src"], r["S1:late"]["ticket_via"]) == ("PROJ-60018", "parent", "git_command")
    assert r["S1"]["ticket_src"] == "git_command"  # the session as a whole keeps its majority/tie-broken key
