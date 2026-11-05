"""service.sh: LaunchAgent install/uninstall (files only, launchd is never touched), the SessionStart hook and start.sh in service mode."""

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CONSOLE = Path(__file__).resolve().parents[1]
SERVICE = CONSOLE / "service.sh"
START = CONSOLE / "start.sh"
HOOK = CONSOLE.parent / "hooks" / "session-start.sh"


@pytest.fixture
def box(tmp_path):
    """State dir and LaunchAgents dir with a SPACE in the path."""
    home, agents, repo = tmp_path / "my home" / ".agent-console", tmp_path / "Launch Agents", tmp_path / "main checkout"
    (repo / ".git").mkdir(parents=True)
    env = {**{k: v for k, v in os.environ.items() if not k.startswith("AGENT_CONSOLE_")}, "AGENT_CONSOLE_HOME": str(home), "AGENT_CONSOLE_LAUNCHAGENTS": str(agents), "AGENT_CONSOLE_PYTHON": sys.executable,
           "AGENT_CONSOLE_REPO": str(repo), "AGENT_CONSOLE_PORT": "8799", "SERVICE_NO_LAUNCHCTL": "1", "HOME": str(tmp_path)}

    # A fake launchctl first on PATH: even a bug in service.sh cannot reach the real launchd (the label is shared with the
    # real service; once a test replaced it). Every call is recorded.
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "launchctl").write_text('#!/bin/bash\necho "$@" >> "' + str(tmp_path / "launchctl.calls") + '"\nexit 1\n')
    (fake / "launchctl").chmod(0o755)
    env["PATH"] = f"{fake}:{env['PATH']}"

    def sh(script, *args, **over):
        return subprocess.run(["/bin/bash", str(script), *args], env={**env, **over}, capture_output=True, text=True, timeout=60)

    return type("Box", (), {"home": home, "agents": agents, "repo": repo, "env": env, "sh": staticmethod(sh), "tmp": tmp_path,
                            "plist": agents / "local.agent-console.plist"})


def test_install_writes_a_foreground_keepalive_plist_that_runs_from_this_checkout(box):
    r = box.sh(SERVICE, "install")
    assert r.returncode == 0, r.stderr
    p = plistlib.loads(box.plist.read_bytes())
    assert p["Label"] == "local.agent-console" and p["RunAtLoad"] is True and p["KeepAlive"] is True
    assert p["ProgramArguments"] == [sys.executable, "-m", "agent_console"]          # foreground: no nohup, no &, no daemon flag
    assert p["WorkingDirectory"] == str(CONSOLE)                                      # console/ of this checkout, no copy
    assert p["StandardOutPath"] == p["StandardErrorPath"] == str(box.home / "server.log")
    e = p["EnvironmentVariables"]
    assert e["AGENT_CONSOLE_HOME"] == str(box.home) and e["AGENT_CONSOLE_PORT"] == "8799" and e["AGENT_CONSOLE_REPO"] == str(CONSOLE.parent)
    assert not (box.home / "app").exists()


def test_install_twice_changes_nothing(box):
    assert box.sh(SERVICE, "install").returncode == 0
    before = box.plist.read_bytes()
    r = box.sh(SERVICE, "install")
    assert r.returncode == 0 and "Unchanged" in r.stdout and box.plist.read_bytes() == before


def test_a_second_instance_has_its_own_label_port_and_home(box):
    other = box.tmp / "second home"
    assert box.sh(SERVICE, "install").returncode == 0
    assert box.sh(SERVICE, "install", AGENT_CONSOLE_LABEL="local.agent-console.8798", AGENT_CONSOLE_PORT="8798", AGENT_CONSOLE_HOME=str(other)).returncode == 0
    p2 = plistlib.loads((box.agents / "local.agent-console.8798.plist").read_bytes())
    assert p2["Label"] == "local.agent-console.8798" and p2["EnvironmentVariables"]["AGENT_CONSOLE_PORT"] == "8798"
    assert p2["EnvironmentVariables"]["AGENT_CONSOLE_HOME"] == str(other) and box.plist.is_file()


def test_install_refuses_a_port_held_by_something_else_and_names_the_fix(box):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    try:
        r = box.sh(SERVICE, "install", AGENT_CONSOLE_PORT=port)
    finally:
        s.close()
    # The script must stop before writing anything and say how to free the port; it never kills.
    assert r.returncode == 1 and "is held by pid" in r.stderr and "AGENT_CONSOLE_PORT" in r.stderr and not box.plist.exists()


def test_uninstall_removes_the_plist_but_keeps_state_and_twice_is_fine(box):
    box.sh(SERVICE, "install")
    (box.home / "scores.jsonl").write_text("{}\n")
    r = box.sh(SERVICE, "uninstall")
    assert r.returncode == 0 and not box.plist.exists() and (box.home / "scores.jsonl").is_file()
    r = box.sh(SERVICE, "uninstall")
    assert r.returncode == 0 and "Not installed" in r.stdout


def test_install_fails_clearly_when_there_is_no_python(box):
    r = box.sh(SERVICE, "install", AGENT_CONSOLE_PYTHON=str(box.tmp / "nope" / "python"))
    assert r.returncode == 1 and "no python at" in r.stderr and not box.plist.exists()


def test_the_session_start_hook_execs_start_sh_and_logs_when_it_is_missing(box):
    fake = box.tmp / "a checkout"
    (fake / "hooks").mkdir(parents=True)
    (fake / "console").mkdir()
    shutil.copy(HOOK, fake / "hooks" / "session-start.sh")
    r = box.sh(fake / "hooks" / "session-start.sh")
    assert (r.returncode, r.stdout) == (0, "") and "missing or not executable" in (box.home / "start.log").read_text()
    (fake / "console" / "start.sh").write_text('#!/bin/bash\necho "started with: $*"\n')
    (fake / "console" / "start.sh").chmod(0o755)
    r = box.sh(fake / "hooks" / "session-start.sh", "arg1")
    assert (r.returncode, r.stdout.strip()) == (0, "started with: arg1")


def test_the_hook_adds_the_marking_instruction_only_when_the_console_answers(box):
    fake = box.tmp / "a checkout"
    (fake / "hooks").mkdir(parents=True)
    (fake / "console").mkdir()
    shutil.copy(HOOK, fake / "hooks" / "session-start.sh")
    start = fake / "console" / "start.sh"
    for line, marked in (("Agent console: http://127.0.0.1:1", True),
                         ("Agent console: NOT answering at http://127.0.0.1:1 (LaunchAgent installed; see x)", False),
                         ("", False)):
        start.write_text(f'#!/bin/bash\n[ -n "{line}" ] && echo "{line}"\nexit 0\n')
        start.chmod(0o755)
        r = box.sh(fake / "hooks" / "session-start.sh")
        assert r.returncode == 0 and ("Console tracking:" in r.stdout) is marked and (not line or r.stdout.startswith(line))
    start.write_text('#!/bin/bash\necho "Agent console: http://127.0.0.1:1"\n')
    assert "Console tracking:" in box.sh(fake / "hooks" / "session-start.sh").stdout
    r = box.sh(fake / "hooks" / "session-start.sh", AGENT_CONSOLE_MARKING="0")
    assert r.stdout == "Agent console: http://127.0.0.1:1\n"


def test_with_the_service_installed_the_hook_only_reports_and_starts_nothing(box):
    box.agents.mkdir(parents=True)
    box.plist.write_text("<plist/>")
    tree = box.tmp / "tree"
    tree.mkdir()
    import socket
    with socket.socket() as sk:          # a port nothing listens on, so a console running on 8791 (or any fixed port) cannot break this test
        sk.bind(("127.0.0.1", 0))
        port = str(sk.getsockname()[1])
    r = box.sh(START, AGENT_CONSOLE_GUARD_ROOT=str(tree), CLAUDE_PROJECT_DIR=str(tree), AGENT_CONSOLE_PORT=port)
    assert r.returncode == 0 and r.stdout.count("\n") == 1 and f"NOT answering at http://127.0.0.1:{port}" in r.stdout
    assert "LaunchAgent is installed" in (box.home / "start.log").read_text()
    assert not (box.home / "console.pid").exists()                     # no second copy started


def test_files_redirected_to_a_temp_dir_never_reach_launchd(box):
    """The tests redirect the plist dir; launchctl must then not be called at all, even if SERVICE_NO_LAUNCHCTL is empty."""
    assert box.sh(SERVICE, "install", SERVICE_NO_LAUNCHCTL="").returncode == 0
    assert box.sh(SERVICE, "uninstall", SERVICE_NO_LAUNCHCTL="").returncode == 0
    assert not (box.tmp / "launchctl.calls").exists()
