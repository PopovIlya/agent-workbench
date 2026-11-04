"""The kit-* roles: user-level role files as a source, the registry entries, and the first-line verdict."""

import sys
from pathlib import Path

import pytest

from agent_console import config, ctq, flags, parser
from agent_console.roles import load_roles, role_files
from agent_console.store import Store
REPO = Path(__file__).resolve().parents[2]   # the workbench
sys.path.insert(0, str(REPO / "console"))

from conftest import assistant, role_file  # noqa: E402
from test_store_and_flags import build_main_with_subs, flags_of, q, sub_recs  # noqa: E402


def kit_file(d, name, model="sonnet", tools="Read, Grep"):
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"---\nname: {name}\ndescription: d\nmodel: {model}\ntools: {tools}\n---\n\nbody\n")
    return p


# ---- discovery
def test_user_dir_is_a_role_source_and_symlinks_are_resolved(env):
    kit = env.tmp / "agent-kit" / "agents"
    real = kit_file(kit, "kit-builder", tools="Read, Write")
    udir = config.user_agents_dir()
    udir.mkdir(parents=True)
    (udir / "kit-builder.md").symlink_to(real)
    roles = load_roles(env.repo)
    assert roles["kit-builder"].tools == ["Read", "Write"] and roles["kit-builder"].model_tier == "sonnet"
    assert role_files(env.repo)["kit-builder"] == real.resolve()


def test_the_workbench_role_wins_on_a_name_clash(env):
    role_file(env.repo, "builder", tools="Read")
    kit_file(config.user_agents_dir(), "builder", tools="Read, Write, Bash")
    assert load_roles(env.repo)["builder"].tools == ["Read"]


def test_broken_symlink_and_missing_user_dir_are_skipped(env):
    role_file(env.repo, "builder")
    assert set(load_roles(env.repo)) == {"builder"}            # the user dir does not exist
    udir = config.user_agents_dir()
    udir.mkdir(parents=True)
    (udir / "kit-gone.md").symlink_to(env.tmp / "nowhere.md")
    assert set(load_roles(env.repo)) == {"builder"}


# ---- registry (g1 = Analysis, g2 = Tests, g3 = Build and checks)
@pytest.mark.parametrize("role,stage", [("kit-analyst", "g1"), ("kit-test-designer", "g2"), ("kit-builder", "g3"),
                                        ("kit-reviewer", "g3"), ("kit-security", "g3"), ("kit-verifier", "g3")])
def test_kit_roles_are_in_their_stage(role, stage):
    assert ctq.STAGE_OF[role] == stage and role in ctq.ROLE_ORDER


def test_kit_gates_are_the_roles_that_send_work_back():
    assert {r for r in flags.GATE_ROLES if r.startswith("kit-")} == {"kit-reviewer", "kit-security", "kit-verifier"}


# ---- verdict on the first line
@pytest.mark.parametrize("text,v", [("FAIL\ndocs/agents/work/X-1/reviewer.md", "FAIL"), ("PASS\npath", "PASS"), ("BLOCKED\np", "BLOCKED"),
                                    ("QUESTIONS\np", "QUESTIONS"), ("\n\n**FAIL**\np", "FAIL"), ("FAIL: 2 findings", "FAIL"),
                                    ("Reviewing now.\nFAIL", None), ("FAILED to start", None), ("Failing tests written", None),
                                    ("REJECT: x", None), ("", None)])
def test_first_line_verdict(text, v):
    assert parser.first_line_verdict(text) == v


def reply_run(agent, role, text, start):
    recs = sub_recs(agent, start=start)
    recs[-1] = assistant(f"{agent}-last", t=start + 9, agent=agent, blocks=[{"type": "text", "text": text}])
    return recs


def test_kit_role_fail_counts_as_reject_and_reject_word_does_not(env):
    build_main_with_subs(env, [
        ("r1", "kit-reviewer", "PROJ-60069 kit-reviewer", reply_run("r1", "kit-reviewer", "FAIL\ndocs/agents/work/PROJ-60069/reviewer.md", 10)),
        ("r2", "kit-reviewer", "PROJ-60072 kit-reviewer", reply_run("r2", "kit-reviewer", "REJECT: not a kit verdict", 30)),
        ("r3", "kit-reviewer", "PROJ-60075 kit-reviewer", reply_run("r3", "kit-reviewer", "PASS\npath", 50)),
        ("v1", "kit-verifier", "PROJ-60078 kit-verifier", reply_run("v1", "kit-verifier", "BLOCKED\npath", 70)),
        ("s1", "kit-security", "PROJ-60081 kit-security", reply_run("s1", "kit-security", "FAIL\npath", 90))])
    s = Store()
    s.ingest()
    assert set(flags_of(s, "reject")) == {"S1:r1", "S1:s1"}
    runs = {r["run_id"]: r for r in q(s, "SELECT run_id, verdict, reject_count FROM runs")}
    assert [runs[k]["verdict"] for k in ("S1:r1", "S1:r2", "S1:r3", "S1:v1")] == ["FAIL", None, "PASS", "BLOCKED"]


def test_the_22_roles_are_unchanged(env):
    """A first line FAIL does not reject a project gate; REJECT still does."""
    build_main_with_subs(env, [
        ("g1", "reviewer", "PROJ-60084 review", reply_run("g1", "reviewer", "FAIL\nnot a project verdict", 10)),
        ("g2", "reviewer", "PROJ-60087 review", reply_run("g2", "reviewer", "REJECT: tests missing", 30))])
    s = Store()
    s.ingest()
    assert set(flags_of(s, "reject")) == {"S1:g2"}


def test_returned_after_kit_security_fail(env):
    build_main_with_subs(env, [
        ("b1", "kit-builder", "PROJ-60093 build", sub_recs("b1", start=10)),
        ("s1", "kit-security", "PROJ-60093 security", reply_run("s1", "kit-security", "FAIL\np", 30)),
        ("b2", "kit-builder", "PROJ-60093 fix", sub_recs("b2", start=50))])
    s = Store()
    s.ingest()
    assert set(flags_of(s, "returned")) == {"S1:b2"} and set(flags_of(s, "reject")) == {"S1:s1"}


def test_returned_after_kit_reviewer_fail(env):
    build_main_with_subs(env, [
        ("b1", "kit-builder", "PROJ-60090 build", sub_recs("b1", start=10)),
        ("r1", "kit-reviewer", "PROJ-60090 review", reply_run("r1", "kit-reviewer", "FAIL\np", 30)),
        ("b2", "kit-builder", "PROJ-60090 fix", sub_recs("b2", start=50))])
    s = Store()
    s.ingest()
    assert set(flags_of(s, "returned")) == {"S1:b2"} and set(flags_of(s, "reject")) == {"S1:r1"}


# ---- criteria files and the scorer's fallback to the user-level directory
KIT = ("kit-analyst", "kit-test-designer", "kit-builder", "kit-reviewer", "kit-security", "kit-verifier")


def test_every_kit_role_has_a_criteria_file_with_a_checkable_reply():
    import re
    from agent_scoring import agent_score as A
    cdir = REPO / "kit" / "criteria"
    for name in KIT:
        f = A.parse_criteria((cdir / f"{name}.md").read_text(), name)
        reply = [o for o in f.outputs if o.kind == "reply"]
        assert reply and re.search(reply[0].arg, "PASS\ndocs/agents/work/X-1/x.md") and not re.search(reply[0].arg, "Reviewing the diff.\nPASS"), name
        assert any(o.kind == "write" for o in f.outputs), name
        assert f.gate == (name in ("kit-reviewer", "kit-security", "kit-verifier")), name
        assert "(blob " in (cdir / f"{name}.md").read_text(), name


def test_scorer_falls_back_to_the_user_dir_and_checks_staleness(env):
    import shutil
    import subprocess
    from agent_scoring import agent_score as A
    cdir = env.repo / "kit" / "criteria"
    cdir.mkdir(parents=True)
    src = REPO / "kit" / "criteria" / "kit-builder.md"
    subprocess.run(["git", "-C", str(env.repo), "init", "-q"], check=True)
    udir = env.tmp / "kit"
    real = kit_file(udir, "kit-builder", tools="Read, Write, Bash")
    blob = subprocess.check_output(["git", "-C", str(env.repo), "hash-object", str(real)], text=True).strip()[:7]
    import re
    (cdir / "kit-builder.md").write_text(re.sub(r"\(blob [0-9a-f]{7}\)", f"(blob {blob})", src.read_text()))
    link = env.tmp / "user"
    link.mkdir()
    (link / "kit-builder.md").symlink_to(real)
    got = A.load_roles(env.repo, user_dir=link)["kit-builder"]
    assert got.tools == ["Read", "Write", "Bash"] and got.tier == "sonnet" and got.stale is None
    real.write_text(real.read_text() + "\nmore\n")
    assert "differs" in A.load_roles(env.repo, user_dir=link)["kit-builder"].stale
    shutil.rmtree(link)
    assert A.load_roles(env.repo, user_dir=link)["kit-builder"].stale == "role file not found on this ref"
