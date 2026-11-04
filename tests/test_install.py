"""install.sh / uninstall.sh in a throwaway HOME (no LaunchAgent: --no-service): links, hook merge, idempotency, foreign files kept."""

import json
import os
import pty
import select
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(home: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(["/bin/bash", *args], env=env, capture_output=True, text=True, timeout=120)


def snapshot(home: Path) -> dict[str, str]:
    out = {}
    for p in sorted(home.rglob("*")):
        rel = str(p.relative_to(home))
        out[rel] = ("link:" + os.readlink(p)) if p.is_symlink() else ("dir" if p.is_dir() else p.read_text(errors="replace"))
    return out


def test_install_twice_is_idempotent_and_uninstall_leaves_only_foreign_things(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "agents").mkdir(parents=True)
    foreign = {"model": "sonnet", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo other"}]}]}}
    (home / ".claude" / "settings.json").write_text(json.dumps(foreign))
    (home / ".claude" / "agents" / "kit-builder.md").write_text("someone else's file")       # not ours: must survive
    r = sh(home, str(ROOT / "install.sh"), "--only", "all", "--no-service")
    assert r.returncode == 0, r.stdout + r.stderr
    agents = home / ".claude" / "agents"
    assert (agents / "reviewer.md").is_symlink() and os.readlink(agents / "reviewer.md") == str(ROOT / "roles-22" / "agents" / "reviewer.md")
    assert (agents / "kit-builder.md").read_text() == "someone else's file" and "SKIPPED" in r.stdout
    s = json.loads((home / ".claude" / "settings.json").read_text())
    assert s["model"] == "sonnet" and s["hooks"]["Stop"] == foreign["hooks"]["Stop"]
    assert s["hooks"]["SessionStart"][0]["hooks"][0]["command"] == f'"{ROOT}/hooks/session-start.sh"'
    assert s["permissions"]["additionalDirectories"] == [str(ROOT)]       # sessions in any repo may read the roles and templates
    assert s["env"]["AGENT_WORKBENCH"] == str(ROOT)                         # how the roles find the workbench
    assert len(list((home / ".claude" / "backups").glob("settings.json.*"))) == 3
    before = snapshot(home)
    r2 = sh(home, str(ROOT / "install.sh"), "--only", "all", "--no-service")
    assert r2.returncode == 0 and snapshot(home) == before and "hook: unchanged" in r2.stdout and "read access: unchanged" in r2.stdout and "env AGENT_WORKBENCH: unchanged" in r2.stdout   # the second run changes nothing
    r3 = sh(home, str(ROOT / "uninstall.sh"))
    assert r3.returncode == 0, r3.stdout + r3.stderr
    left = [p.name for p in agents.iterdir()]
    assert left == ["kit-builder.md"]
    s = json.loads((home / ".claude" / "settings.json").read_text())
    assert s == foreign
    r4 = sh(home, str(ROOT / "uninstall.sh"))
    assert r4.returncode == 0 and "none of ours" in r4.stdout


def test_only_kit_is_the_default(tmp_path):
    home = tmp_path / "home"
    r = sh(home, str(ROOT / "install.sh"), "--no-service", "--no-hooks")
    assert r.returncode == 0, r.stdout + r.stderr
    names = sorted(p.name for p in (home / ".claude" / "agents").iterdir())
    assert names == sorted(p.name for p in (ROOT / "kit" / "agents").glob("*.md"))
    assert not (home / ".claude" / "settings.json").exists()


def test_an_agent_workbench_pointing_elsewhere_is_left_alone(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({"env": {"AGENT_WORKBENCH": "/somewhere/else"}}))
    r = sh(home, str(ROOT / "install.sh"), "--no-service")
    assert r.returncode == 1 and "AGENT_WORKBENCH: SKIPPED" in r.stdout
    assert json.loads((home / ".claude" / "settings.json").read_text())["env"]["AGENT_WORKBENCH"] == "/somewhere/else"
    sh(home, str(ROOT / "uninstall.sh"))
    assert json.loads((home / ".claude" / "settings.json").read_text())["env"]["AGENT_WORKBENCH"] == "/somewhere/else"


def install_in_tty(home: Path, answer: str) -> tuple[int, str]:
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["HOME"] = str(home)
        os.execv("/bin/bash", ["/bin/bash", str(ROOT / "install.sh"), "--no-service"])
    out, sent = b"", False
    while True:
        r, _, _ = select.select([fd], [], [], 60)
        if not r:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if not sent and b"[y/N]" in out:
            os.write(fd, (answer + "\n").encode())
            sent = True
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace")


def test_log_retention_is_asked_only_in_a_terminal_and_raised_only_on_yes(tmp_path):
    home = tmp_path / "home"
    r = sh(home, str(ROOT / "install.sh"), "--no-service")
    assert r.returncode == 0 and "not asked (no terminal)" in r.stdout
    assert "cleanupPeriodDays" not in json.loads((home / ".claude" / "settings.json").read_text())
    code, out = install_in_tty(home, "n")
    assert code == 0 and "[y/N]" in out and "cleanupPeriodDays" not in json.loads((home / ".claude" / "settings.json").read_text())
    code, out = install_in_tty(home, "y")
    s = json.loads((home / ".claude" / "settings.json").read_text())
    assert code == 0 and s["cleanupPeriodDays"] == 365 and s["env"]["AGENT_WORKBENCH"] == str(ROOT)
    r = sh(home, str(ROOT / "install.sh"), "--no-service")
    assert "cleanupPeriodDays is 365, unchanged" in r.stdout
