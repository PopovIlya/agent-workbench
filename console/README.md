# Agent console

Local web UI for your Claude Code sessions: cost, time and quality per ticket, role and session. Design: [DESIGN.md](DESIGN.md).

- Service (LaunchAgent): `make install-service | restart-service | service-status | uninstall-service` (port 8790, 127.0.0.1 only).
- Without the service: `make start`, `make stop`, `make status`.
- Tests and lint: `make test`, `make lint` (uses `console/.venv`).
- State lives in `~/.agent-console/`, never in the repo. Logs are read from `~/.claude/projects/`.
- Every setting is an environment variable; see `agent_console/config.py` and `../docs/INSTALL.md`.

Pages: Overview, Tickets, Ticket, Roles, Role, Sessions, Run. All read `/api/ctq/*`; the period, the scope and the filters live in the
URL hash (`#/overview?p=7d`). Every threshold is a constant in `config.py`; every "?" text is in `static/ctq-help.js`.

Compare two tickets (cost, time and outcome side by side, plus the difference b minus a and the ratio b / a):
- Page: `http://127.0.0.1:8790/compare?a=<KEY>&b=<KEY>`. Server-rendered, same local-only Host and header rules as every page. It only reads the index (no rescan);
  while the console builds its first index it answers 503. A missing `a` or `b` answers 422, an unknown key 404.
- CLI: `python -m agent_console compare <KEY> <KEY> [--json]` (run in `console/` with `.venv/bin/python`). Text table by default; `--json` prints stable, sorted JSON with raw numbers.
  Exit 0 done; 1 the index cannot be opened or refreshed; 2 usage error, refusal or unknown key. With no arguments `python -m agent_console` starts the server as before.
- The CLI refreshes the shared index (`~/.agent-console/index.sqlite`) first and never runs the git fetch. It refuses (exit 2, one line, nothing written) when its time zone,
  key patterns, console home or checkout differ from the ones the index was built with, when the index has another schema version, or when it does not record them yet
  (start the console once with this checkout). Run it with the console's settings. Not compared: `AGENT_CONSOLE_TREE_ROOTS`, `AGENT_CONSOLE_WORKTREE_ROOTS`,
  `AGENT_CONSOLE_PROJECT_REMOTE`, `AGENT_CONSOLE_LOG_ROOT`: with another value of these the refresh rebuilds `runs` with the CLI's values and the running console serves them until its next scan.
- While the CLI refreshes, the console's own scan can meet a locked index and show its scan-error banner until its next good scan (30 s).
- The comparison always uses all logs (no period, no scope). Numbers on the page and in the text are rounded (tokens `12k`, dollars `$1.23`, time `12 min`, ratio 2 decimals); JSON keeps raw values.
