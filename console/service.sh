#!/bin/bash
# Run the agent console as a macOS LaunchAgent, independent of Claude sessions.
#   service.sh install     write the LaunchAgent plist for this checkout and (re)load it
#   service.sh uninstall   unload and remove the plist (state in AGENT_CONSOLE_HOME stays)
#   service.sh restart     kickstart the loaded service (after a `git pull`)
#   service.sh status      loaded or not, and whether /health answers
# The service runs `python -m agent_console` in the FOREGROUND from this checkout's console/ folder, with console/.venv.
# Env: AGENT_CONSOLE_HOME (state dir, default ~/.agent-console), AGENT_CONSOLE_PORT (default 8790),
# AGENT_CONSOLE_LABEL (default local.agent-console; a second instance needs its own label, port and home),
# AGENT_CONSOLE_PYTHON (default console/.venv/bin/python). Tests: AGENT_CONSOLE_LAUNCHAGENTS (plist folder),
# SERVICE_NO_LAUNCHCTL=1 (write files only, never touch launchd).

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
LABEL="${AGENT_CONSOLE_LABEL:-local.agent-console}"
HOME_DIR="${AGENT_CONSOLE_HOME:-$HOME/.agent-console}"
PORT="${AGENT_CONSOLE_PORT:-8790}"
PLIST="${AGENT_CONSOLE_LAUNCHAGENTS:-$HOME/Library/LaunchAgents}/$LABEL.plist"
LOG="$HOME_DIR/server.log"
DOMAIN="gui/$(id -u)"

die() { echo "service.sh: $*" >&2; exit 1; }
xml() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
launchctl_ok() { [ -z "${SERVICE_NO_LAUNCHCTL:-}" ] && [ -z "${AGENT_CONSOLE_LAUNCHAGENTS:-}" ]; }
service_loaded() { launchctl_ok && launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; }
health() { [ "$(curl -s -m 1 "http://127.0.0.1:$PORT/health" 2>/dev/null)" = '{"ok":true,"app":"agent-console"}' ]; }

find_python() {
  local py="${AGENT_CONSOLE_PYTHON:-$HERE/.venv/bin/python}"
  [ -x "$py" ] || die "no python at $py; create it with: ./install.sh (or python3.13 -m venv console/.venv && console/.venv/bin/pip install -r console/requirements.txt)"
  "$py" -c 'import fastapi, uvicorn, yaml' 2>/dev/null || die "$py lacks fastapi/uvicorn/yaml; run: \"$py\" -m pip install -r \"$HERE/requirements.txt\""
  printf '%s' "$py"
}

install() {
  [ -f "$HERE/agent_console/server.py" ] || die "not an agent-console checkout: $HERE"
  local py
  py="$(find_python)" || exit 1
  if ! service_loaded; then
    local holder
    holder="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1)"
    if [ -n "$holder" ]; then
      echo "Port $PORT is held by pid $holder (not this service). Stop it first, or pick another port with AGENT_CONSOLE_PORT." >&2
      exit 1
    fi
  fi
  mkdir -p "$HOME_DIR" "$(dirname "$PLIST")" || die "cannot create directories"
  chmod 700 "$HOME_DIR" 2>/dev/null
  local tmp="$PLIST.tmp.$$"
  {
    echo '<?xml version="1.0" encoding="UTF-8"?>'
    echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">'
    echo '<plist version="1.0"><dict>'
    echo "  <key>Label</key><string>$(printf '%s' "$LABEL" | xml)</string>"
    echo '  <key>ProgramArguments</key><array>'
    echo "    <string>$(printf '%s' "$py" | xml)</string><string>-m</string><string>agent_console</string>"
    echo '  </array>'
    echo "  <key>WorkingDirectory</key><string>$(printf '%s' "$HERE" | xml)</string>"
    echo '  <key>EnvironmentVariables</key><dict>'
    echo "    <key>AGENT_CONSOLE_HOME</key><string>$(printf '%s' "$HOME_DIR" | xml)</string>"
    echo "    <key>AGENT_CONSOLE_PORT</key><string>$PORT</string>"
    echo "    <key>AGENT_CONSOLE_REPO</key><string>$(printf '%s' "$REPO" | xml)</string>"
    echo "    <key>HOME</key><string>$(printf '%s' "$HOME" | xml)</string>"
    echo '    <key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin</string>'
    echo '  </dict>'
    echo '  <key>RunAtLoad</key><true/>'
    echo '  <key>KeepAlive</key><true/>'
    echo '  <key>ThrottleInterval</key><integer>10</integer>'
    echo "  <key>StandardOutPath</key><string>$(printf '%s' "$LOG" | xml)</string>"
    echo "  <key>StandardErrorPath</key><string>$(printf '%s' "$LOG" | xml)</string>"
    echo '</dict></plist>'
  } >"$tmp" || die "cannot write $tmp"
  if command -v plutil >/dev/null 2>&1; then plutil -lint "$tmp" >/dev/null || { rm -f "$tmp"; die "plist did not lint"; }; fi
  local changed=1
  if [ -f "$PLIST" ] && cmp -s "$tmp" "$PLIST"; then changed=0; rm -f "$tmp"; else mv "$tmp" "$PLIST"; fi
  if launchctl_ok; then
    if [ "$changed" = 1 ] || ! service_loaded; then
      launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1
      launchctl bootstrap "$DOMAIN" "$PLIST" || die "launchctl bootstrap failed"
      echo "Loaded $LABEL from $PLIST"
    else
      echo "Unchanged: $PLIST (already loaded)"
    fi
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do health && break; sleep 0.5; done
    health && echo "Agent console running: http://127.0.0.1:$PORT" || echo "Loaded, but /health does not answer yet; see $LOG" >&2
  else
    [ "$changed" = 1 ] && echo "Wrote $PLIST (launchctl skipped)" || echo "Unchanged: $PLIST (launchctl skipped)"
  fi
}

uninstall() {
  if [ ! -f "$PLIST" ] && ! service_loaded; then echo "Not installed: $PLIST"; return 0; fi
  if launchctl_ok; then launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || launchctl bootout "$DOMAIN" "$PLIST" >/dev/null 2>&1; fi
  rm -f "$PLIST"
  if launchctl_ok; then
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do health || break; sleep 0.5; done
    health && echo "Warning: something still answers on $PORT; see: lsof -nP -iTCP:$PORT -sTCP:LISTEN" >&2
  fi
  echo "Removed $LABEL ($PLIST). State in $HOME_DIR is kept."
}

restart() {
  service_loaded || die "$LABEL is not loaded; run: $0 install"
  launchctl kickstart -k "$DOMAIN/$LABEL" || die "kickstart failed"
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do health && break; sleep 0.5; done
  health && echo "Restarted: http://127.0.0.1:$PORT" || echo "Restarted, but /health does not answer yet; see $LOG" >&2
}

status() {
  if service_loaded; then echo "$LABEL: loaded ($PLIST)"; elif [ -f "$PLIST" ]; then echo "$LABEL: plist present, not loaded"; else echo "$LABEL: not installed"; fi
  health && echo "health: answering on http://127.0.0.1:$PORT" || echo "health: not answering on http://127.0.0.1:$PORT"
  echo "log: $LOG"
}

case "${1:-}" in
  install) install ;;
  uninstall) uninstall ;;
  restart) restart ;;
  status) status ;;
  *) die "usage: service.sh install|uninstall|restart|status" ;;
esac
