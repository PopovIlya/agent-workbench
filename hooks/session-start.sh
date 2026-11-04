#!/bin/bash
# Claude Code SessionStart hook (user level, installed by install.sh): make sure the agent console answers and print its URL.
# Never blocks and never fails a session: always exits 0. Problems go to ~/.agent-console/start.log.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
START="$HERE/../console/start.sh"
LOG="${AGENT_CONSOLE_HOME:-$HOME/.agent-console}/start.log"
if [ ! -x "$START" ]; then
  mkdir -p "${LOG%/*}" 2>/dev/null
  printf '%s hook: %s missing or not executable (moved checkout? re-run install.sh)\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$START" >>"$LOG" 2>/dev/null
  exit 0
fi
exec "$START" "$@"
