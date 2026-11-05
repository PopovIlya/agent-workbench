#!/bin/bash
# Claude Code SessionStart hook (user level, installed by install.sh): make sure the agent console answers, print its URL,
# and tell Claude to mark the session with a ticket key so the console tracks it.
# Never blocks and never fails a session: always exits 0. Problems go to ~/.agent-console/start.log.
# Set AGENT_CONSOLE_MARKING=0 to leave out the marking instruction.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
START="$HERE/../console/start.sh"
LOG="${AGENT_CONSOLE_HOME:-$HOME/.agent-console}/start.log"
if [ ! -x "$START" ]; then
  mkdir -p "${LOG%/*}" 2>/dev/null
  printf '%s hook: %s missing or not executable (moved checkout? re-run install.sh)\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$START" >>"$LOG" 2>/dev/null
  exit 0
fi
out="$("$START" "$@")"
[ -n "$out" ] && printf '%s\n' "$out"
# The instruction goes out only when the console answers for this folder (start.sh printed its URL line).
if [ "${AGENT_CONSOLE_MARKING:-1}" != 0 ]; then
  case "$out" in
    *"NOT answering"*) ;;
    "Agent console: "*)
      printf '%s\n' "Console tracking: this session is tracked by a ticket key. If the user's first message does not start with [KEY] (for example [PROJ-123]), ask once, before any other work, which ticket key to use, or 'none' to skip. With a key: begin every sub-agent description with '[KEY] ' and keep work notes in docs/agents/work/KEY/. If the first message already starts with [KEY], do not ask."
      ;;
  esac
fi
exit 0
