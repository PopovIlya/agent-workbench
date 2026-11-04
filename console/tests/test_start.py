"""start.sh: cwd guard, idempotency, never kills, never fails, prints one line and no token."""

import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "start.sh"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def sh(tmp_path):
    home, port, guard = tmp_path / "home", free_port(), tmp_path / "tree"
    (guard / "sub").mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    env = {**{k: v for k, v in os.environ.items() if not k.startswith("AGENT_CONSOLE_")}, "AGENT_CONSOLE_HOME": str(home), "AGENT_CONSOLE_PORT": str(port), "AGENT_CONSOLE_GUARD_ROOT": str(guard),
           "AGENT_CONSOLE_PYTHON": sys.executable, "AGENT_CONSOLE_LAUNCHAGENTS": str(tmp_path / "agents"), "AGENT_CONSOLE_LOG_ROOT": str(tmp_path / "logs"), "CLAUDE_PROJECT_DIR": str(guard / "sub")}
    env.pop("AGENT_CONSOLE_FORCE", None)

    def run(**over):
        e = {**env, **over}
        t = time.time()
        r = subprocess.run(["/bin/bash", str(SCRIPT)], env=e, capture_output=True, text=True, timeout=20, cwd=str(tmp_path))
        return r, time.time() - t

    ns = type("Sh", (), {"run": staticmethod(run), "home": home, "port": port, "guard": guard, "env": env})
    yield ns
    pid = (home / "console.pid")
    if pid.exists():
        try:
            os.kill(int(pid.read_text()), signal.SIGTERM)
        except (OSError, ValueError):
            pass


def test_outside_the_tree_it_is_silent_fast_and_starts_nothing(sh):
    r, dt = sh.run(CLAUDE_PROJECT_DIR="/tmp")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert dt < 0.5  # includes python's subprocess spawn; the script alone measures ~20 ms
    assert not (sh.home / "console.pid").exists()


def test_second_root_in_the_guard_list_is_accepted(sh, tmp_path):
    other = tmp_path / "worktrees" / "wt1"
    other.mkdir(parents=True)
    r, _ = sh.run(AGENT_CONSOLE_GUARD_ROOT=f"{sh.guard}:{tmp_path / 'worktrees'}", CLAUDE_PROJECT_DIR=str(other))
    assert r.stdout == f"Agent console: http://127.0.0.1:{sh.port}\n"
    r, _ = sh.run(AGENT_CONSOLE_GUARD_ROOT=f"{sh.guard}:{tmp_path / 'worktrees'}", CLAUDE_PROJECT_DIR=str(tmp_path / "worktrees-evil"))
    assert r.stdout == ""  # a sibling dir with a shared name prefix is not inside the root


def test_the_hook_execs_this_checkouts_start_sh_and_the_guard_still_applies(sh):
    import subprocess as sp
    hook = SCRIPT.parent.parent / "hooks" / "session-start.sh"
    assert hook.stat().st_mode & 0o111
    out = sp.run(["/bin/bash", str(hook)], env={**sh.env, "CLAUDE_PROJECT_DIR": "/tmp"}, capture_output=True, text=True, timeout=10)
    assert (out.returncode, out.stdout) == (0, "")
    out = sp.run(["/bin/bash", str(hook)], env=sh.env, capture_output=True, text=True, timeout=20)
    assert out.stdout == f"Agent console: http://127.0.0.1:{sh.port}\n"


def test_inside_the_tree_it_starts_once_and_prints_one_line(sh):
    r, _ = sh.run()
    assert r.returncode == 0 and r.stdout == f"Agent console: http://127.0.0.1:{sh.port}\n"
    deadline = time.time() + 10
    while not (sh.home / "console.pid").exists() and time.time() < deadline:
        time.sleep(0.1)
    pid1 = (sh.home / "console.pid").read_text()
    # The pid file appears before the server answers. A second call in that gap would start a second copy (slow runners
    # showed it), so the idempotence check begins once /health answers.
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{sh.port}/health", timeout=1)
            break
        except OSError:
            time.sleep(0.2)
    r2, _ = sh.run()
    assert r2.stdout == r.stdout and (sh.home / "console.pid").read_text() == pid1  # idempotent: same process, same line
    ps = subprocess.run(["pgrep", "-f", "agent_console"], capture_output=True, text=True).stdout.split()
    assert pid1 in ps


SLOW_SERVER = """\
import http.server, os
(pathlib := __import__("pathlib")).Path(os.environ["AGENT_CONSOLE_HOME"], "console.pid").write_text(str(os.getpid()))


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok":true,"app":"agent-console"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


http.server.HTTPServer(("127.0.0.1", int(os.environ["AGENT_CONSOLE_PORT"])), H).serve_forever()
"""


def test_start_does_not_wait_for_a_server_that_is_slow_to_come_up(sh, tmp_path):
    """The 1 s rule protects the session: the hook prints its line and returns while the server is still starting."""
    stub = tmp_path / "slow_server.py"
    stub.write_text(SLOW_SERVER)
    slow_python = tmp_path / "slow-python"  # start.sh runs `$PY -m agent_console`; this ignores the arguments
    slow_python.write_text(f'#!/bin/bash\nsleep 6\nexec "{sys.executable}" "{stub}"\n')
    slow_python.chmod(0o755)
    try:
        r, dt = sh.run(AGENT_CONSOLE_PYTHON=str(slow_python))
        assert r.returncode == 0 and r.stdout == f"Agent console: http://127.0.0.1:{sh.port}\n"
        # start.sh itself spends ~1.7-2.0 s here (lsof ~0.6 s on macOS, then its 0.8 s poll). The server needs 6 s, so a script
        # that waited for it could not return in under 3 s.
        assert dt < 3.0
        assert not (sh.home / "console.pid").exists()  # and it is not up yet
        url = f"http://127.0.0.1:{sh.port}/health"
        deadline = time.time() + 20
        answer = ""
        while time.time() < deadline and not answer:
            try:
                answer = urllib.request.urlopen(url, timeout=1).read().decode()
            except OSError:
                time.sleep(0.2)
        assert answer == '{"ok":true,"app":"agent-console"}'  # it does come up afterwards
    finally:
        subprocess.run(["pkill", "-f", str(stub)])  # a failed assertion must not leave the stub on the port


def test_no_token_or_secret_in_output_or_files(sh):
    r, _ = sh.run()
    time.sleep(1.5)
    blob = r.stdout + r.stderr + "".join(p.read_text(errors="replace") for p in sh.home.glob("*.log"))
    assert not re.search(r"token|secret|[A-Za-z0-9_-]{40,}", blob, re.I)


def test_a_foreign_process_on_the_port_is_left_alone(sh):
    with socket.socket() as s:
        s.bind(("127.0.0.1", sh.port))
        s.listen()
        r, _ = sh.run()
        assert r.returncode == 0 and r.stdout == ""
        assert "not touching it" in (sh.home / "start.log").read_text()


def test_never_fails_the_session_when_python_is_missing(sh):
    r, _ = sh.run(AGENT_CONSOLE_PYTHON="/nonexistent/python", HOME=str(sh.home / "nohome"))
    assert r.returncode == 0 and r.stdout == ""
    assert "no python" in (sh.home / "start.log").read_text()
