#!/bin/bash
# Install the agent workbench for this user: role symlinks, the SessionStart hook, the console LaunchAgent.
# Usage: ./install.sh [--only kit|22|all] [--no-hooks] [--no-service]   (--no-hooks: no hook, no read access, no AGENT_WORKBENCH in settings.json)
# Env: AGENT_CONSOLE_PORT (8790), AGENT_CONSOLE_LABEL (local.agent-console), AGENT_CONSOLE_HOME (~/.agent-console),
#      AGENT_WORKBENCH_PYTHON (python3.13). Idempotent: a second run changes nothing. Never overwrites a file that is not ours.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ONLY="kit"
HOOKS=1
SERVICE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    --only=*) ONLY="${1#--only=}"; shift ;;
    --no-hooks) HOOKS=0; shift ;;
    --no-service) SERVICE=0; shift ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "install.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
case "$ONLY" in kit|22|all) ;; *) echo "install.sh: --only must be kit, 22 or all" >&2; exit 2 ;; esac

AGENTS="$HOME/.claude/agents"
SETTINGS="$HOME/.claude/settings.json"
PY="${AGENT_WORKBENCH_PYTHON:-python3.13}"
FAIL=0
say() { printf '%s\n' "$*"; }

say "Agent workbench: $REPO"
say "Roles: $ONLY · hooks: $([ $HOOKS = 1 ] && echo yes || echo no) · console service: $([ $SERVICE = 1 ] && echo yes || echo no)"

command -v "$PY" >/dev/null 2>&1 || { say "ERROR: $PY not found (Python 3.13 is needed for the console; set AGENT_WORKBENCH_PYTHON)"; exit 1; }
command -v git >/dev/null 2>&1 || { say "ERROR: git not found"; exit 1; }

dirs=""
case "$ONLY" in kit) dirs="kit/agents" ;; 22) dirs="roles-22/agents" ;; all) dirs="kit/agents roles-22/agents" ;; esac
mkdir -p "$AGENTS"
for d in $dirs; do
  for src in "$REPO/$d"/*.md; do
    name="$(basename "$src")"
    dst="$AGENTS/$name"
    if [ -L "$dst" ]; then
      cur="$(readlink "$dst")"
      if [ "$cur" = "$src" ]; then say "role $name: unchanged"; continue; fi
      say "role $name: SKIPPED, $dst is a link to $cur (not ours; remove it yourself to use ours)"; continue
    fi
    if [ -e "$dst" ]; then say "role $name: SKIPPED, $dst is a file that is not ours"; continue; fi
    ln -s "$src" "$dst" && say "role $name: linked"
  done
done
for f in "$AGENTS"/*.md; do
  [ -L "$f" ] || continue
  t="$(readlink "$f")"
  case "$t" in "$REPO"/*) ;; *) continue ;; esac
  keep=0
  for d in $dirs; do case "$t" in "$REPO/$d/"*) keep=1 ;; esac; done
  [ $keep = 1 ] || say "role $(basename "$f"): still linked from an earlier install (uninstall.sh removes it)"
done

if [ $HOOKS = 1 ]; then
  /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" add "\"$REPO/hooks/session-start.sh\"" || FAIL=1
  /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" add-dir "$REPO" || FAIL=1
  /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" set-env AGENT_WORKBENCH "$REPO" || FAIL=1
  days="$(/usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" get cleanupPeriodDays)"
  if [ -n "$days" ] && [ "$days" -ge 365 ] 2>/dev/null; then
    say "log retention: cleanupPeriodDays is $days, unchanged"
  elif [ -t 0 ] && [ -t 1 ]; then
    printf 'Claude Code deletes session logs older than cleanupPeriodDays (now %s). The console can then no longer re-read them.\nRaise it to 365 in %s (merged, with a backup)? [y/N] ' "${days:-30, the default}" "$SETTINGS"
    read -r answer
    case "$answer" in
      y|Y|yes) /usr/bin/env python3 -I "$REPO/tools/settings_hooks.py" --settings "$SETTINGS" set-int cleanupPeriodDays 365 || FAIL=1 ;;
      *) say "log retention: left at ${days:-30, the default}" ;;
    esac
  else
    say "log retention: cleanupPeriodDays is ${days:-30, the default}; not asked (no terminal). Run ./install.sh in a terminal to be asked."
  fi
fi

VENV="$REPO/console/.venv"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import fastapi, uvicorn, yaml' 2>/dev/null; then
  say "console venv: unchanged ($VENV)"
else
  say "console venv: creating $VENV (packages from PyPI: console/requirements.txt)"
  "$PY" -m venv "$VENV" && "$VENV/bin/python" -m pip install -q --disable-pip-version-check --index-url https://pypi.org/simple -r "$REPO/console/requirements.txt" || { say "ERROR: venv or pip install failed"; FAIL=1; }
fi

if [ $SERVICE = 1 ] && [ $FAIL = 0 ]; then
  bash "$REPO/console/service.sh" install || FAIL=1
fi

if [ $FAIL = 0 ]; then say "Done."; else say "Done, with errors above."; fi
exit $FAIL
