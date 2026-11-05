# Agent workbench

Personal tool set for running Claude Code agents on any repo, and for seeing what they cost and how well they did.

A personal project, not affiliated with or endorsed by any employer. MIT licensed, see [LICENSE](LICENSE).

## What is inside

| Folder | What |
|---|---|
| `kit/` | Six `kit-*` roles and `PLAYBOOK.md`: a light route the main session follows (analyst, test designer, builder, reviewer, security, verifier). Plus `tools/rule_coverage.py`. |
| `roles-22/` | The 22 roles of the full test process, led by the `coordinator`. `SHARED-RULES.md` is their safety floor. |
| `templates/` | `PROJECT.md` (the one project profile every role reads), the requirement-map format, the work-folder report formats. |
| `console/` | The agent console: a local web app (127.0.0.1:8790) that reads `~/.claude/projects` and shows cost, time, scores and flags per ticket, role and session. |
| `hooks/` | The SessionStart hook that makes sure the console runs. |
| `tools/` | `ai_models.py` (show and switch the model mapping, a person only), `lint_roles.py`, `settings_hooks.py`. |
| `docs/` | Install, project set-up, how to run, sanitisation notes. |

Role files hold only the way of working. Everything project-specific (paths, commands, people, gates) comes from the repo's `docs/agents/PROJECT.md`.

## Five-minute quick start

```bash
git clone <your remote> ~/code/agent-workbench
cd ~/code/agent-workbench
./install.sh
```

(In the clean-machine check the clone came from the local checkout; the remote is added at the first push.) That links the six kit roles into `~/.claude/agents/`, adds the SessionStart hook, read access and `AGENT_WORKBENCH` to `~/.claude/settings.json` (merged, with a backup), creates `console/.venv` and starts the console as a LaunchAgent. Open http://127.0.0.1:8790.

Then make a repo ready ([docs/SETUP-A-PROJECT.md](docs/SETUP-A-PROJECT.md)) and run a ticket ([docs/HOW-TO-RUN.md](docs/HOW-TO-RUN.md)).

## Tell Claude how to mark a session

The console groups cost and time by ticket key. A session is tracked reliably only when Claude knows its key. Two things carry the key:

- the first message starts with the key in brackets, for example `[PROJ-123] Add the empty-cart state`;
- every sub-agent description starts with the same `[PROJ-123] `, and the work notes live in `docs/agents/work/PROJ-123/`.

Claude needs to be told to do this. The SessionStart hook installed by `./install.sh` does it for you: in each new session it prints the console URL and one more line, an instruction to Claude. If the first message does not start with `[KEY]`, Claude asks once which key to use (or `none` to skip), then marks the sub-agents and work notes with it. If the first message already starts with `[KEY]`, it does not ask.

- Without the hook (another machine, or `./install.sh --no-hooks`): put the same instruction into the project's `CLAUDE.md`. The text is at the end of `hooks/session-start.sh`.
- To switch the instruction off, set `AGENT_CONSOLE_MARKING=0` in the environment of the session.
- Why it matters: a key found only inside a prompt's text can be taken for a ticket. In EXP-1 the rule ids `CON-011` and similar were filed as tickets and the console showed USD 53 for a ticket that cost USD 117 (see [docs/experiments/exp1/README.md](docs/experiments/exp1/README.md)). A leading `[KEY]` is the strongest signal the console reads.

## Docs
- [docs/INSTALL.md](docs/INSTALL.md): prerequisites, install and uninstall, models, updates, the console service.
- [docs/SETUP-A-PROJECT.md](docs/SETUP-A-PROJECT.md): the project profile, field by field.
- [docs/HOW-TO-RUN.md](docs/HOW-TO-RUN.md): the three ways of working, and troubleshooting.

## Tests

The test tools (pytest, ruff) are not in the runtime venv; add them once:

```bash
console/.venv/bin/python -m pip install -q --index-url https://pypi.org/simple -r console/requirements-dev.txt
console/.venv/bin/python -m pytest -q -p no:cacheprovider tests console/tests kit/tests
console/.venv/bin/ruff check .
python3 tools/lint_roles.py
```
