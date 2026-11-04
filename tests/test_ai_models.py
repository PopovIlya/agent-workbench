"""tools/ai_models.py: `show` reads anywhere; a switch refuses without a terminal, has no --yes, shows the change, writes only after `yes`, backs up, restores."""

import json
import os
import pty
import select
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "ai_models.py"
SETTINGS = {"env": {"CLAUDE_CODE_USE_BEDROCK": "1", "AWS_PROFILE": "placeholder-profile",
                    "ANTHROPIC_DEFAULT_OPUS_MODEL": "model-o", "ANTHROPIC_DEFAULT_SONNET_MODEL": "model-s",
                    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "model-h"},
            "model": "sonnet", "hooks": {"SessionStart": []}, "permissions": {"allow": ["Read"]}}


def write(tmp: Path) -> Path:
    p = tmp / "settings.json"
    p.write_text(json.dumps(SETTINGS))
    return p


def in_tty(args: list[str], answer: str | None = None, timeout: float = 10) -> tuple[int, str]:
    """Run the tool on a pseudo-terminal (stdin and stdout are a tty), type `answer` when it asks."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execv(sys.executable, [sys.executable, "-I", str(TOOL), *args])
    out, sent = b"", False
    while True:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            break
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if answer is not None and not sent and b"Type yes" in out:
            os.write(fd, (answer + "\n").encode())
            sent = True
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace")


def test_a_switch_refuses_without_a_terminal_and_changes_nothing(tmp_path):
    p = write(tmp_path)
    before = p.read_text()
    for args in (["use", "no-opus"], ["use", "restore"], ["set", "opus", "x-model"], ["set", "main", "opus"]):
        r = subprocess.run([sys.executable, "-I", str(TOOL), "--settings", str(p), *args], stdin=subprocess.DEVNULL, capture_output=True, text=True)
        assert r.returncode == 2 and "no interactive terminal" in r.stderr, args
    assert p.read_text() == before and not (tmp_path / "backups").exists()


def test_show_runs_without_a_terminal_and_writes_nothing(tmp_path):
    p = write(tmp_path)
    before = p.read_text()
    r = subprocess.run([sys.executable, "-I", str(TOOL), "--settings", str(p), "show"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert r.returncode == 0 and "model-o" in r.stdout and "Main session model: sonnet" in r.stdout and "placeholder-profile" not in r.stdout
    assert p.read_text() == before and not (tmp_path / "backups").exists()


def test_there_is_no_yes_flag():
    src = TOOL.read_text()
    assert '"--yes"' not in src and "'--yes'" not in src and "-y" not in [w.strip("\"',") for w in src.split()]
    r = subprocess.run([sys.executable, "-I", str(TOOL), "use", "no-opus", "--yes"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert r.returncode != 0


def test_show_prints_the_mapping_and_no_account_values(tmp_path):
    p = write(tmp_path)
    code, out = in_tty(["--settings", str(p), "show"])
    assert code == 0 and "model-o" in out and "model-s" in out and "Bedrock" in out and "Main session model: sonnet" in out
    assert "placeholder-profile" not in out


def test_no_opus_needs_yes_backs_up_keeps_other_keys_and_restore_puts_it_back(tmp_path):
    p = write(tmp_path)
    code, out = in_tty(["--settings", str(p), "use", "no-opus"], answer="no")
    assert code == 1 and "model-o  ->  model-s" in out and json.loads(p.read_text()) == SETTINGS
    code, out = in_tty(["--settings", str(p), "use", "no-opus"], answer="yes")
    s = json.loads(p.read_text())
    assert code == 0 and s["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "model-s"
    assert s["hooks"] == SETTINGS["hooks"] and s["permissions"] == SETTINGS["permissions"] and s["env"]["AWS_PROFILE"] == "placeholder-profile"
    backups = list((tmp_path / "backups" / "ai_models").glob("settings.json.*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == SETTINGS
    code, out = in_tty(["--settings", str(p), "use", "restore"], answer="yes")
    assert code == 0 and json.loads(p.read_text())["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] == "model-o"


def test_set_one_tier_and_the_main_model(tmp_path):
    p = write(tmp_path)
    assert in_tty(["--settings", str(p), "set", "haiku", "model-h2"], answer="yes")[0] == 0
    assert in_tty(["--settings", str(p), "set", "main", "opus"], answer="yes")[0] == 0
    s = json.loads(p.read_text())
    assert s["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "model-h2" and s["model"] == "opus"
    code, out = in_tty(["--settings", str(p), "set", "main", "opus"])
    assert code == 0 and "No change" in out


def test_the_real_settings_file_is_never_the_test_target():
    assert "~/.claude/settings.json" in TOOL.read_text()   # the default; every test above passes --settings
