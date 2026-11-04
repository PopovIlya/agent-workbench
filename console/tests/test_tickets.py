"""Ticket key derivation: each source is found and labelled; the order of precedence holds."""

import subprocess

import pytest

from agent_console import tickets
from agent_console.store import Store
from conftest import PROJECT, add_sub, assistant, tool_use, usage, user_prompt, write_jsonl


@pytest.mark.parametrize("cwd,key", [
    ("/work/worktrees/app-PROJ-60024-additional-links", "PROJ-60024"),
    ("/private/tmp/proj60027-verify", None), ("/x/team_3003_fix", None),
    ("/work/worktrees/app-order-details-readonly", None), ("/x/PROJ-12", "PROJ-12"), ("/x/UTF-8", None), (None, None)])
def test_dir_key(cwd, key):
    assert tickets.dir_key(cwd) == key


@pytest.mark.parametrize("cwd,key", [
    ("/work/worktrees/app-PROJ-60024-additional-links", "PROJ-60024"),
    ("/private/tmp/proj60027-verify", "PROJ-60027"), ("/x/team_3003_fix", "TEAM-3003"), ("/x/aproj60027", None), ("/x/OTHER-12", None)])
def test_dir_key_with_configured_prefixes(cwd, key):
    try:
        tickets.configure(["PROJ", "TEAM"])
        assert tickets.dir_key(cwd) == key
    finally:
        tickets.configure([])


@pytest.mark.parametrize("text,key", [("[PROJ-600000] x", "PROJ-600000"), ("PROJ-3006: x", "PROJ-3006"), ("  TEAM-3000 go", "TEAM-3000"),
                                      ("do PROJ-3006", None), ("PROJ-12", "PROJ-12"), ("SHA-256 sum", None), (None, None)])
def test_lead_key(text, key):
    assert tickets.lead_key(text) == key


def test_resolve_follows_the_documented_order():
    allhits = {s: f"PROJ-{i:04d}" for i, s in enumerate(tickets.ORDER, start=1000)}
    for i, src in enumerate(tickets.ORDER):
        t, s = tickets.resolve(allhits)
        assert (t, s) == (f"PROJ-{1000 + i}", src)
        allhits[src] = None
    assert tickets.resolve(allhits) == (None, "unknown")


def test_worktree_branches_only_linked_worktrees(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(main), *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q", "-b", "master")
    run("-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i")
    wt = tmp_path / "wt-one"
    run("worktree", "add", "-q", "-b", "PROJ-60039-some-work", str(wt))
    got = tickets.worktree_branches(main)
    assert got == {str(wt.resolve()) if str(wt.resolve()) in got else str(wt): "PROJ-60039-some-work"}
    path = next(iter(got))
    assert tickets.worktree_branch_key(path + "/sub/dir", got) == "PROJ-60039" and tickets.worktree_branch_key("/elsewhere", got) is None


def q(store):
    db = store.reader()
    try:
        return {r["run_id"]: (r["ticket"], r["ticket_src"]) for r in db.execute("SELECT run_id, ticket, ticket_src FROM runs")}
    finally:
        db.close()


def one_main(env, blocks=None, prompt="go", cwd="/work/app", branch="HEAD"):
    recs = [user_prompt(prompt, t=1), assistant("m1", t=2, blocks=blocks, branch=branch)]
    recs[0]["cwd"] = cwd
    write_jsonl(env.root / PROJECT / "S1.jsonl", recs)
    s = Store()
    s.ingest()
    return q(s)["S1"]


def test_source_prompt_lead(env):
    assert one_main(env, prompt="[PROJ-60045] please") == ("PROJ-60045", "prompt_lead")


def test_source_change_file_path(env):
    blk = [tool_use("e", "Edit", file_path="/work/worktrees/w/docs/requirements/changes/PROJ-60048.md", old_string="a", new_string="b")]
    assert one_main(env, blocks=blk) == ("PROJ-60048", "change_file")


def test_source_git_command(env):
    assert one_main(env, blocks=[tool_use("g", "Bash", command="git switch PROJ-60051-x")]) == ("PROJ-60051", "git_command")


def test_source_worktree_dir(env):
    assert one_main(env, cwd="/work/worktrees/app-PROJ-60054-thing") == ("PROJ-60054", "worktree_dir")


def test_source_worktree_branch(env):
    repo = env.repo
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
    run("init", "-q", "-b", "master")
    run("-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i")
    wt = env.tmp / "linked"
    run("worktree", "add", "-q", "-b", "PROJ-60057-feature", str(wt))
    assert one_main(env, cwd=str(wt.resolve())) == ("PROJ-60057", "worktree_branch")


def test_source_spawn_lead_beats_text_and_children_inherit(env):
    spawn = [tool_use("toolu_a1", "Agent", subagent_type="builder", description="[PROJ-60060] build, see PROJ-60096", prompt="p")]
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go", t=1), assistant("main1", blocks=spawn, t=2)])
    add_sub(env.root, "S1", "a1", "builder", [assistant("a1m", agent="a1", t=5, u=usage(1, 1))], "toolu_a1")
    s = Store()
    s.ingest()
    r = q(s)
    assert r["S1:a1"] == ("PROJ-60060", "spawn_lead") and r["S1"] == (None, "unknown")


def test_only_the_first_prompt_counts_as_leading(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("hello", t=1), user_prompt("[PROJ-60063] now this", t=2), assistant("m1", t=3)])
    s = Store()
    s.ingest()
    assert q(s)["S1"] == ("PROJ-60063", "prompt")  # a later leading key is only a weak "prompt" hint


# ---- leading [KEY] in any project format (a key like PILOT9-RUN is not Jira-shaped) ----

@pytest.mark.parametrize("text,key", [
    ("[PILOT9-RUN] BA: rules", "PILOT9-RUN"), ("[ACME-2026] x", "ACME-2026"), ("[AB-CD] x", "AB-CD"), ("  [PILOT9-RUN] x", "PILOT9-RUN"),
    ("[PROJ-600000] x", "PROJ-600000"),
    # not keys: no hyphen, lower case, nothing after / before the hyphen, two hyphens (needs an extra pattern), too long, not leading
    ("[WIP] x", None), ("[TODO] x", None), ("[Draft] x", None), ("[work-in-progress] x", None), ("[AB-] x", None), ("[-AB] x", None),
    ("[AB-CD-EF] x", None), ("[A" + "B" * 40 + "-C] x", None), ("do [PILOT9-RUN] x", None), ("[PILOT9-RUN x", None),
    ("PILOT9-RUN: x", None), ("[]", None), ("[A]", None)])
def test_bracket_lead_key(text, key):
    assert tickets.lead_key(text) == key


def test_bracket_key_length_limits():
    ok = "A" + "B" * 18 + "-" + "C" * 20  # 40 chars
    assert len(ok) == 40 and tickets.lead_key(f"[{ok}] x") == ok
    assert tickets.lead_key(f"[{ok}C] x") is None  # 41


def test_extra_patterns_from_config_and_a_bad_one_is_ignored(monkeypatch, capsys):
    assert tickets.lead_key("[AB-CD-12] x") is None
    monkeypatch.setenv("AGENT_CONSOLE_KEY_PATTERNS", "[A-Z]+-[A-Z]+-[0-9]+ (unclosed")
    assert tickets.lead_key("[AB-CD-12] x") == "AB-CD-12"
    assert tickets.lead_key("[PILOT9-RUN] x") == "PILOT9-RUN"  # the built-in pattern is always there
    assert "ignoring key pattern" in capsys.readouterr().err
    # extras never loosen the other sources: a bare key in a git command / path still needs the Jira pattern
    assert not tickets.KEY_RE.search("git switch AB-CD-12")


def test_source_prompt_lead_non_jira_key(env):
    assert one_main(env, prompt="[PILOT9-RUN] please") == ("PILOT9-RUN", "prompt_lead")


def test_bracket_key_beats_a_git_command_key(env):
    blocks = [tool_use("g", "Bash", command="git switch PROJ-60051-x")]
    assert one_main(env, prompt="[PILOT9-RUN] go", blocks=blocks) == ("PILOT9-RUN", "prompt_lead")
    assert one_main(env, prompt="go", blocks=blocks) == ("PROJ-60051", "git_command")  # without the bracket the git key still works


@pytest.mark.parametrize("word", ["[WIP]", "[TODO]", "[Draft]"])
def test_ordinary_bracketed_words_are_not_keys(env, word):
    assert one_main(env, prompt=f"{word} please") == (None, "unknown")


def test_spawn_description_bracket_key_is_inherited_by_the_run(env):
    spawn = [tool_use("toolu_a1", "Agent", subagent_type="business-analyst", description="[PILOT9-RUN] BA: rules", prompt="p")]
    git = [tool_use("g", "Bash", command="git switch PROJ-60096-x")]
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("go", t=1), assistant("main1", blocks=spawn, t=2)])
    add_sub(env.root, "S1", "a1", "business-analyst", [assistant("a1m", agent="a1", t=5, u=usage(1, 1), blocks=git)], "toolu_a1")
    s = Store()
    s.ingest()
    assert q(s)["S1:a1"] == ("PILOT9-RUN", "spawn_lead")


def test_existing_runs_are_re_derived_when_the_key_patterns_change(env, monkeypatch):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("[AB-CD-12] go", t=1), assistant("m1", t=2)])
    s = Store()
    s.ingest()
    assert q(s)["S1"] == (None, "unknown")
    s.db.close()
    monkeypatch.setenv("AGENT_CONSOLE_KEY_PATTERNS", "[A-Z]+-[A-Z]+-[0-9]+")
    s2 = Store()  # other patterns -> every derived row is rebuilt from the logs, same keys every time
    s2.ingest()
    assert q(s2)["S1"] == ("AB-CD-12", "prompt_lead")
    s2.db.close()
    s3 = Store()
    s3.ingest()
    assert q(s3)["S1"] == ("AB-CD-12", "prompt_lead")


def test_a_store_from_before_the_bracket_source_is_rebuilt(env):
    write_jsonl(env.root / PROJECT / "S1.jsonl", [user_prompt("[PILOT9-RUN] go", t=1), assistant("m1", t=2)])
    s = Store()
    s.ingest()
    s.db.execute("UPDATE runs SET ticket=NULL, ticket_src='unknown'")  # what the old code stored for this prompt
    s.db.execute("PRAGMA user_version=7")
    s.db.commit()
    s.db.close()
    s2 = Store()
    s2.ingest()
    assert q(s2)["S1"] == ("PILOT9-RUN", "prompt_lead")
