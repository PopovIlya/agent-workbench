#!/bin/bash
# Start the Agent console if it is not running. Used by the SessionStart hook and by `make start`.
#
# Contract (DESIGN.md section 8):
#  - Guard first, with shell builtins only (no fork): if the session cwd is not under one of the guard roots
#    (default: the home directory), exit 0 silently. Target < 100 ms.
#  - Never block and never fail the session: always exit 0. Errors go to ~/.agent-console/start.log.
#  - Idempotent: pid file + health check; a second call prints the same line and starts nothing.
#  - Never kills anything. A foreign process on the port is logged and left alone.
#  - Prints exactly one line on success: "Agent console: http://127.0.0.1:<port>" (no token, ever).
#    (The SessionStart hook, hooks/session-start.sh, adds one marking line after it; start.sh itself still prints one line.)
#
# Env: AGENT_CONSOLE_HOME, AGENT_CONSOLE_PORT, AGENT_CONSOLE_GUARD_ROOT (colon-separated), AGENT_CONSOLE_LABEL,
# AGENT_CONSOLE_FORCE=1 (skip the cwd guard; used by `make start`), AGENT_CONSOLE_PYTHON, AGENT_CONSOLE_LAUNCHAGENTS.
# With the LaunchAgent installed this only checks health and prints the URL (or one line saying it does not answer).

# Colon-separated roots; default: the home directory (every session of this user).
GUARD_ROOTS="${AGENT_CONSOLE_GUARD_ROOT:-$HOME}"
if [ -z "$AGENT_CONSOLE_FORCE" ]; then
  here="${CLAUDE_PROJECT_DIR:-$PWD}"
  ok=""
  rest="$GUARD_ROOTS:"
  while [ -n "$rest" ]; do
    root="${rest%%:*}"
    rest="${rest#*:}"
    case "$here/" in "$root"/*) ok=1 ;; esac
  done
  [ -z "$ok" ] && exit 0
fi

HOME_DIR="${AGENT_CONSOLE_HOME:-$HOME/.agent-console}"
PORT="${AGENT_CONSOLE_PORT:-8790}"
URL="http://127.0.0.1:$PORT"
SELF_DIR="${BASH_SOURCE[0]%/*}"
case "$SELF_DIR" in /*) ;; *) SELF_DIR="$PWD/$SELF_DIR" ;; esac

mkdir -p "$HOME_DIR" 2>/dev/null && chmod 700 "$HOME_DIR" 2>/dev/null
LOG="$HOME_DIR/start.log"
log() { printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" >>"$LOG" 2>/dev/null; }
healthy() { [ "$(curl -s -m 0.4 "$URL/health" 2>/dev/null)" = '{"ok":true,"app":"agent-console"}' ]; }

if healthy; then
  echo "Agent console: $URL"
  exit 0
fi

# Installed as a LaunchAgent (service.sh install): launchd keeps it alive, so this hook only reports. Starting a second
# copy here would fight launchd for the port.
LABEL="${AGENT_CONSOLE_LABEL:-local.agent-console}"
PLIST="${AGENT_CONSOLE_LAUNCHAGENTS:-$HOME/Library/LaunchAgents}/$LABEL.plist"
if [ -f "$PLIST" ]; then
  log "LaunchAgent is installed but /health does not answer on $URL; see $HOME_DIR/server.log (restart: launchctl kickstart -k gui/$(id -u)/$LABEL)"
  echo "Agent console: NOT answering at $URL (LaunchAgent installed; see $HOME_DIR/server.log)"
  exit 0
fi

# The console's own virtualenv (created by install.sh).
PY="${AGENT_CONSOLE_PYTHON:-$SELF_DIR/.venv/bin/python}"
if [ ! -x "$PY" ]; then log "no python at $PY; run install.sh in the workbench"; exit 0; fi

# A port held by something that is not the console: log it and leave it alone.
holder="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1)"
if [ -n "$holder" ]; then log "port $PORT is held by pid $holder and does not answer as the console; not touching it"; exit 0; fi

cd "$SELF_DIR" || { log "cannot cd to $SELF_DIR"; exit 0; }
AGENT_CONSOLE_HOME="$HOME_DIR" AGENT_CONSOLE_PORT="$PORT" nohup "$PY" -m agent_console </dev/null >>"$HOME_DIR/console.log" 2>&1 &
disown 2>/dev/null
for _ in 1 2 3 4 5 6 7 8; do
  sleep 0.1
  healthy && break
done
healthy || log "started pid $! but /health did not answer within 0.8 s (it may still be starting)"
echo "Agent console: $URL"
exit 0
