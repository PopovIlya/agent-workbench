#!/bin/bash
# Remove what install.sh installed: role symlinks that point into this checkout, our SessionStart hook, read access and
# AGENT_WORKBENCH in ~/.claude/settings.json, our console LaunchAgent.
# Usage: ./uninstall.sh [--remove-state]   (--remove-state also deletes AGENT_CONSOLE_HOME: index, scores, verdicts, defects)
# Never removes a file that is not ours. Idempotent.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE=0
[ "${1:-}" = "--remove-state" ] && STATE=1
AGENTS="$HOME/.claude/agents"
SETTINGS="$HOME/.claude/settings.json"
LABEL="${AGENT_CONSOLE_LABEL:-local.agent-console}"
PLIST="${AGENT_CONSOLE_LAUNCHAGENTS:-$HOME/Library/LaunchAgents}/$LABEL.plist"
HOME_DIR="${AGENT_CONSOLE_HOME:-$HOME/.agent-console}"
say() { printf '%s\n' "$*"; }

n=0
if [ -d "$AGENTS" ]; then
  for f in "$AGENTS"/*.md; do
    [ -L "$f" ] || continue
    case "$(readlink "$f")" in "$REPO"/*) rm "$f" && say "role $(basename "$f"): unlinked" && n=$((n+1)) ;; esac
  done
fi
[ $n = 0 ] && say "roles: none of ours linked"

if [ -f "$SETTINGS" ]; then
  /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" remove "$REPO/hooks/"
  /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" remove-dir "$REPO"
  /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" unset-env AGENT_WORKBENCH "$REPO"
else
  say "hook: no settings file"
fi

if [ -f "$PLIST" ]; then
  if grep -q "$REPO/console" "$PLIST"; then
    bash "$REPO/console/service.sh" uninstall
  else
    say "service: $PLIST is not ours (it runs another checkout); left alone"
  fi
else
  say "service: $LABEL not installed"
fi

if [ $STATE = 1 ] && [ -d "$HOME_DIR" ]; then
  rm -rf "$HOME_DIR" && say "state: removed $HOME_DIR"
elif [ -d "$HOME_DIR" ]; then
  say "state: kept $HOME_DIR (pass --remove-state to delete it)"
fi
say "Done."
