# Agent console

Local web UI for your Claude Code sessions: cost, time and quality per ticket, role and session. Design: [DESIGN.md](DESIGN.md).

- Service (LaunchAgent): `make install-service | restart-service | service-status | uninstall-service` (port 8790, 127.0.0.1 only).
- Without the service: `make start`, `make stop`, `make status`.
- Tests and lint: `make test`, `make lint` (uses `console/.venv`).
- State lives in `~/.agent-console/`, never in the repo. Logs are read from `~/.claude/projects/`.
- Every setting is an environment variable; see `agent_console/config.py` and `../docs/INSTALL.md`.

Pages: Overview, Tickets, Ticket, Roles, Role, Sessions, Run. All read `/api/ctq/*`; the period, the scope and the filters live in the
URL hash (`#/overview?p=7d`). Every threshold is a constant in `config.py`; every "?" text is in `static/ctq-help.js`.
