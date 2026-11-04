"""tools/lint_roles.py on the real tree (must be clean) and on small broken copies (each error is caught)."""

import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lint_roles", ROOT / "tools" / "lint_roles.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def test_the_workbench_role_files_pass():
    assert L.run() == []


LINE = (ROOT / "tools" / "resolve-workbench.line").read_text().strip()


def fake_tree(tmp_path, monkeypatch, body="You are r. Read `docs/agents/PROJECT.md`.\n", fm="name: r\ndescription: d\ntools: Read\nmodel: sonnet", resolver=True):
    for d in ("roles-22/agents", "roles-22/criteria", "kit/agents", "kit/criteria", "templates", "kit", "tools"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "resolve-workbench.line").write_text(LINE + "\n")
    if resolver:
        body += "\n```bash\n" + LINE + "\n```\n"
    (tmp_path / "roles-22" / "SHARED-RULES.md").write_text("rules\n")
    (tmp_path / "kit" / "PLAYBOOK.md").write_text("playbook\n")
    role = tmp_path / "roles-22" / "agents" / "r.md"
    role.write_text(f"---\n{fm}\n---\n\n{body}")
    (tmp_path / "roles-22" / "criteria" / "r.md").write_text(f"Source: x (blob {L.blob(role)}).\n")
    monkeypatch.setattr(L, "ROOT", tmp_path)
    return role


def test_a_clean_fake_role_passes(tmp_path, monkeypatch):
    fake_tree(tmp_path, monkeypatch)
    assert L.run() == []


def test_each_kind_of_error_is_caught(tmp_path, monkeypatch):
    fake_tree(tmp_path, monkeypatch, resolver=False, fm="name: other\ndescription: d\nmodel: gpt", body=(
        "Read /Users/someone/x and ~/notes.\nCall api.internal-tools.com.\nMail a.b@example.org.\nSee TEAM-42.\n"
        "Use `<workbench>/templates/missing.md`.\n"))
    errs = "\n".join(L.run())
    for needle in ("name 'other'", "'tools' missing", "model 'gpt'", "absolute path", "host name", "e-mail", "ticket key TEAM-42", "missing.md", "resolver line"):
        assert needle in errs, needle


def test_placeholders_and_rule_ids_are_not_errors(tmp_path, monkeypatch):
    fake_tree(tmp_path, monkeypatch, body="Key `PROJ-123`, rule ORD-REF-004, `UTF-8`, host app.example.com, scratch /tmp/verify.py.\n")
    assert L.run() == []


def test_the_deny_list_lives_outside_the_repo(tmp_path, monkeypatch):
    fake_tree(tmp_path, monkeypatch, body="Built for Acmeco.\n")
    deny = tmp_path / "deny.txt"
    deny.write_text("# one word per line\nacmeco\n")
    monkeypatch.setenv("AGENT_WORKBENCH_DENYLIST", str(deny))
    assert any("deny list" in e for e in L.run())


def test_refresh_hashes_rewrites_a_stale_blob(tmp_path, monkeypatch):
    role = fake_tree(tmp_path, monkeypatch)
    role.write_text(role.read_text() + "more\n")
    assert any("stale" in e for e in L.run())
    L.run(refresh=True)
    assert L.run() == []
    shutil.rmtree(tmp_path / "roles-22")


def test_a_role_that_still_asks_for_kit_path_is_an_error(tmp_path, monkeypatch):
    fake_tree(tmp_path, monkeypatch, body="Read `kit_path` from the profile.\n")
    assert any("kit_path" in e for e in L.run())
