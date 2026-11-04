# Agent console. Run from console/. $(CURDIR) keeps a path with spaces whole.
HERE := $(CURDIR)/
HOME_DIR ?= $(HOME)/.agent-console
PORT ?= 8790
PY ?= $(HERE).venv/bin/python

.PHONY: start stop status test lint truth install-service uninstall-service restart-service service-status
start:
	@AGENT_CONSOLE_FORCE=1 AGENT_CONSOLE_HOME="$(HOME_DIR)" AGENT_CONSOLE_PORT="$(PORT)" "$(HERE)start.sh"

stop:
	@pid=$$(cat "$(HOME_DIR)/console.pid" 2>/dev/null); \
	if [ -n "$$pid" ] && ps -p $$pid -o command= 2>/dev/null | grep -q agent_console; then kill $$pid && echo "Stopped agent console (pid $$pid)"; \
	else echo "Agent console is not running from this shell (no pid file, or the pid is not ours). A LaunchAgent is stopped with: make uninstall-service"; fi

status:
	@curl -s -m 1 http://127.0.0.1:$(PORT)/health >/dev/null && echo "running: http://127.0.0.1:$(PORT)" || echo "not running on $(PORT)"

test:
	cd "$(HERE)" && "$(PY)" -m pytest tests -q -p no:cacheprovider

lint:
	cd "$(HERE)" && "$(PY)" -m ruff check .

truth:
	python3 -I "$(HERE)ground_truth.py" $(ARGS)

install-service:
	@AGENT_CONSOLE_HOME="$(HOME_DIR)" AGENT_CONSOLE_PORT="$(PORT)" bash "$(HERE)service.sh" install

uninstall-service:
	@AGENT_CONSOLE_HOME="$(HOME_DIR)" AGENT_CONSOLE_PORT="$(PORT)" bash "$(HERE)service.sh" uninstall

restart-service:
	@AGENT_CONSOLE_HOME="$(HOME_DIR)" AGENT_CONSOLE_PORT="$(PORT)" bash "$(HERE)service.sh" restart

service-status:
	@AGENT_CONSOLE_HOME="$(HOME_DIR)" AGENT_CONSOLE_PORT="$(PORT)" bash "$(HERE)service.sh" status
