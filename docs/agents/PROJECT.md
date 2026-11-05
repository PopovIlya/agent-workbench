# Project profile: agent-workbench

Path in the repo: `docs/agents/PROJECT.md`. Every role reads it first: the six `kit-*` roles and the 22 roles.

## Repo
- Trunk branch: main
- Layout: `console/` (the agent console: `agent_console/` Python package, `static/` UI, `tests/`, `pricing.yaml`), `kit/` (six kit roles, playbook, rule_coverage tool), `roles-22/` (the 22 roles), `tools/` (install helpers), `hooks/`, `templates/`, `tests/` (tests of the install tools), `docs/`
- Packages: `console/agent_console` (the console, FastAPI + stdlib), `tools/` (install helpers), `kit/tools` (rule coverage)
- Commit style: `<KEY> <Sentence>`, e.g. `EXP1-KIT Add the compare page`, `EXP1-R22 Add the compare CLI`
- `protected_branches`: main
- `mr_target`: main
- `release_branch`: none
- `merger`: the repo owner

## People and rulings
- `product_owner`: the repo owner
- `approver`: the repo owner
- `questions`: docs/requirements/QUESTIONS.md

## Documents
- `test_strategy`: none
- `dev_strategy`: none
- `decisions`: none
- `conventions`: `console/DESIGN.md`, `console/README.md`
- `security_rules`: none

## Requirements map
- `requirements`: docs/requirements/*.md
- Format: one block per rule, `### <ID>` with fields (see `<workbench>/templates/requirements-area.md`).
- `rule_marker`: a `# rule: <ID>` comment above each test
- `questions_file`: docs/requirements/QUESTIONS.md

## Work folder
Not committed: `docs/agents/work/` is in `.git/info/exclude`.
- `work_dir`: docs/agents/work/<KEY>/
- `change_file`: docs/agents/work/<KEY>/change.md
- `release_dir`: docs/agents/work/releases/<id>/

## Environment
- Interpreter or virtualenv the commands use: `console/.venv/bin/python` (Python 3.13; a worktree needs its own `console/.venv`, it is not in git). Call `console/.venv/bin/python -m pytest` and `console/.venv/bin/python -m ruff`.
- Packages that are NOT installed in it (so their suites cannot run locally): none
- Commands that must not be run (installs from a new index, deploys): `pip install` of anything not in `console/requirements-dev.txt`; `./install.sh`, `./uninstall.sh`, `make install-service`, `make uninstall-service` (they change `~/.claude` and the LaunchAgent); `git push`; `git worktree`, `git switch`/`git checkout` to another branch, and any `git commit` on a branch other than the ticket's own (worktrees share one `.git`)
- `destructive_commands`: none

## Commands
Run from the directory shown. Give the exact command.

| What | Directory | Command |
|---|---|---|
| Lint | repo root | `console/.venv/bin/python -m ruff check .` |
| Types | | none |
| Tests, package 1 (console) | `console/` | `.venv/bin/python -m pytest tests -q -p no:cacheprovider` |
| Tests, package 2 (install tools and kit) | repo root | `console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider` |
| Touched tests only | `console/` | `.venv/bin/python -m pytest tests/<file> -q -p no:cacheprovider` |
| Local selection before a push | repo root | none (no push in this repo's agent runs) |
| Full suite (the person runs it, not an agent) | | none: the suites above are fast and agents run them |
| Secret scan | | none |
| Route access tests (deny by default) | | none |

## Local lane
- Start: `make start` in `console/` (port 8790, state in `~/.agent-console`). Do not start a second console on another port against `~/.agent-console`; use `AGENT_CONSOLE_PORT=<free port>` and `AGENT_CONSOLE_HOME=/tmp/<name>` for a throwaway copy.
- Health: http://127.0.0.1:8790/health
- Test accounts and seeds: none; the console reads logs from `~/.claude/projects/`; tests use `console/tests/fixtures`
- Must not be touched: `~/.claude/projects` is read-only and may be read (the console reads it); never write to `~/.claude` or `~/.agent-console`; do not stop or restart the running console of the person

## Shared environments
- `environments`: none
- `deploy`: none
- `version_check`: none
- `smoke`: none
- `test_record_prefix`: none

## CI
- Jobs a branch pipeline runs: none (no CI configured)
- Jobs that must not be triggered by agents: none
- `qa_report`: none
- `skip_marker`: none

## Baseline
- Commit: a549ddc569e5690b02d4447d02fcf7cfea0f40fe. The base of the branches is this commit plus the profile commit (docs only); the results below hold.
- Results: ruff clean; console 445 passed; install tools and kit 49 passed

## Scratch services for L2
none

## Test fixtures and their limits
- `console/tests/fixtures`: recorded Claude Code session logs (jsonl); they cannot show a live session or a live clock

## Running tests against a throwaway copy
`cp -R <repo> /tmp/<name>` then run the console tests from `/tmp/<name>/console` with the repo's own `.venv/bin/python` (the package is imported from the current directory, not installed)

## Areas
| Area | Prefix | Map file | Main code paths |
|---|---|---|---|
| console | CON | docs/requirements/console.md | console/agent_console/, console/static/, console/tests/ |

## Limits
- `max_agents`: 20
- `heavy_agents_per_machine`: 3
- `return_rounds`: 2

## Model tiers
none: each role uses the tier in its own role file.

## Optional gates
- `claims`: none
- `impact_map`: none
- `test_case_files`: none
- `rule_guards`: none
- `requirements_master`: none
- `change_files`: none
- `questions_inbox`: none
- `ci_limit`: none
- `tracker`: none
- `suites`: none
- `test_selection`: none
- `coverage_report`: none
- `timing_check`: none

## Project conventions
- No new dependencies. Pricing comes from `console/agent_console/pricing.py` and `console/pricing.yaml`.
- Ticket keys follow the console's own rules (`console/agent_console/tickets.py`).
- Tests for the console go in `console/tests/`.
