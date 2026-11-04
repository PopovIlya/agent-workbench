"""The workbench resolver line every role runs first (tools/resolve-workbench.line): variable set, unset, a profile with the
obsolete kit_path, a profile with the workbench_path override, no profile."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE = (ROOT / "tools" / "resolve-workbench.line").read_text().strip()


def resolve(repo: Path, profile: str | None, workbench: str | None, home: Path) -> subprocess.CompletedProcess:
    (repo / "docs" / "agents").mkdir(parents=True, exist_ok=True)
    p = repo / "docs" / "agents" / "PROJECT.md"
    if profile is None:
        p.unlink(missing_ok=True)
    else:
        p.write_text(profile)
    env = {k: v for k, v in os.environ.items() if k != "AGENT_WORKBENCH"}
    env["HOME"] = str(home)
    if workbench is not None:
        env["AGENT_WORKBENCH"] = workbench
    return subprocess.run(["/bin/zsh", "-c", LINE], cwd=repo, env=env, capture_output=True, text=True, timeout=20)


def test_the_variable_set(tmp_path):
    r = resolve(tmp_path, "# Project profile: x\n", str(ROOT), tmp_path)
    assert r.returncode == 0 and r.stdout == f"WORKBENCH={ROOT}\n"


def test_the_variable_unset_stops_with_a_clear_message(tmp_path):
    r = resolve(tmp_path, "# Project profile: x\n", None, tmp_path)
    assert r.returncode == 1 and r.stdout.startswith("BLOCKED: workbench not found: AGENT_WORKBENCH is not set (run install.sh")


def test_a_profile_with_kit_path_is_ignored_with_one_line(tmp_path):
    old = tmp_path / "old-kit"
    old.mkdir()
    r = resolve(tmp_path, f"## Kit\n- `kit_path`: {old}\n", str(ROOT), tmp_path)
    assert r.returncode == 0 and r.stdout.splitlines() == ["kit_path is obsolete, using AGENT_WORKBENCH", f"WORKBENCH={ROOT}"]
    r = resolve(tmp_path, f"## Kit\n- `kit_path`: {old}\n", None, tmp_path)
    assert r.returncode == 1 and r.stdout.splitlines()[0] == "kit_path is obsolete, using AGENT_WORKBENCH" and "BLOCKED" in r.stdout


def test_a_profile_with_workbench_path_overrides_the_variable(tmp_path):
    home = tmp_path / "home"
    (home / "wb" / "kit").mkdir(parents=True)
    (home / "wb" / "kit" / "PLAYBOOK.md").write_text("x")
    r = resolve(tmp_path, "- `workbench_path`: ~/wb\n", str(ROOT), home)
    assert r.returncode == 0 and r.stdout == f"WORKBENCH={home}/wb\n"
    r = resolve(tmp_path, "- `workbench_path`: none\n", str(ROOT), home)
    assert r.stdout == f"WORKBENCH={ROOT}\n"


def test_a_wrong_path_and_a_missing_profile_stop(tmp_path):
    r = resolve(tmp_path, "# x\n", str(tmp_path / "nowhere"), tmp_path)
    assert r.returncode == 1 and "BLOCKED: workbench not found" in r.stdout
    r = resolve(tmp_path, None, str(ROOT), tmp_path)
    assert r.returncode == 1 and r.stdout == "BLOCKED: PROJECT.md missing\n"
