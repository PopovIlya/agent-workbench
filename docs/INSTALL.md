# Install

## Prerequisites

Each has the command that checks it. Run them in VS Code's terminal (Terminal › New Terminal) or in Terminal.app.

| Need | Check | Expect |
|---|---|---|
| macOS (the console runs as a LaunchAgent) | `sw_vers -productVersion` | a version number |
| Claude Code | `claude --version` | a version number |
| The VS Code extension (for the VS Code way) | `code --list-extensions \| grep anthropic.claude-code` | `anthropic.claude-code` |
| Python 3.13 (the console's venv) | `python3.13 --version` | `Python 3.13.x` |
| git | `git --version` | a version number |
| Model access: Bedrock **or** the Anthropic API | see "Models" below | a one-word reply |
| zsh accepts `#` comments on the command line | `setopt \| grep interactivecomments` | `interactivecomments` |

Not run in the clean-machine check: these read the machine itself (a throwaway `HOME` has no extensions and no `.zshrc`); they were run on the Mac the repo was built on.

Without `interactivecomments`, a pasted line with a trailing `# comment` fails. The command blocks in these docs carry no comments, so it is optional. To turn it on, add this line to `~/.zshrc`:

```bash
setopt interactivecomments
```

Not run here: it belongs in your own `~/.zshrc`.

## Install

VS Code: open the workbench folder (File › Open Folder), open a terminal (Terminal › New Terminal) and run the commands below. CLI: the same commands in Terminal.app.

```bash
cd ~/code/agent-workbench
./install.sh
```

Options:
- `--only kit` (default) links the six `kit-*` roles; `--only 22` the 22 roles; `--only all` both.
- `--no-hooks` leaves `~/.claude/settings.json` alone; `--no-service` does not install the LaunchAgent.

What it does, and prints line by line:
1. Links each role file into `~/.claude/agents/` (a symlink into this checkout). A file or a link that is not ours is left alone and reported as `SKIPPED`.
2. Adds the SessionStart hook `"<checkout>/hooks/session-start.sh"`, the checkout to `permissions.additionalDirectories`, and `env.AGENT_WORKBENCH` = the checkout to `~/.claude/settings.json`, by merging; the old file is copied to `~/.claude/backups/settings.json.<time>` first. Nothing else in the file changes. The read access lets a session in any repo read the playbook, the shared rules and the templates (without it, Claude Code asks for, or in `-p` mode refuses, every read outside the repo). `AGENT_WORKBENCH` is how every role finds the workbench; an `AGENT_WORKBENCH` that already points to another checkout is left alone and reported. New sessions see it; restart an open one. The hook also tells Claude to mark each session with a ticket key (see the README, "Tell Claude how to mark a session"); `AGENT_CONSOLE_MARKING=0` switches that line off.
3. Creates `console/.venv` with Python 3.13 and installs `console/requirements.txt` from PyPI.
4. Writes `~/Library/LaunchAgents/local.agent-console.plist` and loads it. The console answers on http://127.0.0.1:8790.

5. Asks, in a terminal only, whether to raise `cleanupPeriodDays` in `~/.claude/settings.json` to 365 (merged, with a backup). See "Log retention" below. Without a terminal it only prints the current value.

Running it again changes nothing ("unchanged" on every line).

## Log retention

Claude Code deletes session logs older than `cleanupPeriodDays` (30 days when the setting is absent). The console keeps what it has already read: a run whose log is gone stays in its index, marked "log deleted", also when a new console version rebuilds the index. But a deleted log can never be re-read, so its texts cannot be shown and a later scorer cannot look at it again. Keeping logs for a year (365) costs disk space (`du -sh ~/.claude/projects` shows how much) and keeps the full history. `uninstall.sh` leaves the setting as it is.

## Uninstall

```bash
./uninstall.sh
```

It removes only what is ours: the links in `~/.claude/agents/` that point into this checkout, our SessionStart hook, our `additionalDirectories` entry and `AGENT_WORKBENCH` while it still points here (with a backup first), and the LaunchAgent if its plist runs this checkout. The console's data in `~/.agent-console/` stays. To delete that too:

```bash
./uninstall.sh --remove-state
```

## Models

The main session runs **Sonnet** by default: set `"model": "sonnet"` in `~/.claude/settings.json`. Each role's tier is its role file's `model:` line (the 22 roles: 13 opus, 8 sonnet, 1 haiku; the six kit roles: sonnet). A project can override a role's tier in its profile's "Model tiers" table.

Claude Code turns a tier into a model id with three settings, in the `env` block of `~/.claude/settings.json`: `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL`. Leave one out to use the provider's default for that tier.

**Bedrock.** In the `env` block: `CLAUDE_CODE_USE_BEDROCK` = `1`, `AWS_PROFILE` = your profile name, `AWS_REGION` = your region, and the three tier settings = the model or inference-profile ids your account may call. Sign in with your usual AWS command before a session. No value of these belongs in this repo.

**Anthropic API.** No `CLAUDE_CODE_USE_BEDROCK`. Put `ANTHROPIC_API_KEY` in your shell's environment from your keychain (never in a file in a repo). The tier settings are optional.

Check access with one short call (it uses your settings as they are):

```bash
claude -p "Reply with the single word OK" --model sonnet < /dev/null
```

**Opus roles fail with 403 where opus is not enabled.** Thirteen of the 22 roles ask for opus. On an account without opus, their spawn fails with a 403 and the coordinator stops (it never swaps the model itself). A person switches the opus tier to the sonnet model:

```bash
python3 tools/ai_models.py show
python3 tools/ai_models.py use no-opus
```

Not run here: a switch needs a person at a terminal by design, and `show` would have read the throwaway settings. `tests/test_ai_models.py` runs `show` without a terminal and every switch on a pseudo-terminal, against a throwaway settings file.

`use restore` puts the earlier mapping back; `set <opus|sonnet|haiku|main> <model id>` sets one. `show` only reads and runs anywhere (an agent may run it to propose a switch). A switch (`use`, `set`) refuses to run without an interactive terminal and has no `--yes` flag: it shows the change and waits for you to type `yes`. It backs up `settings.json` to `~/.claude/backups/ai_models/` first. Start a new session afterwards.

## After a `git pull`

```bash
cd ~/code/agent-workbench
git pull
./install.sh
console/.venv/bin/python -m pip install -q --index-url https://pypi.org/simple -r console/requirements.txt
bash console/service.sh restart
```

`./install.sh` links any new role and leaves the rest. The pip line matters only when `console/requirements.txt` changed. The restart loads the new console code (the service runs this checkout directly).

## The console service

| What | Command |
|---|---|
| Status | `bash console/service.sh status` |
| Start (install and load) | `bash console/service.sh install` |
| Stop (unload; the plist is removed, the data stays) | `bash console/service.sh uninstall` |
| Restart | `bash console/service.sh restart` |
| Logs | `tail -n 50 ~/.agent-console/server.log` |
| Hook log (written only when something is wrong) | `tail -n 20 ~/.agent-console/start.log` |
| Port | 8790; another one with `AGENT_CONSOLE_PORT` at install |

KeepAlive restarts a killed console; stop it with `uninstall`, not `kill`. Without the service, `make -C console start` runs it in the background from a terminal, and `make -C console stop` stops it.

Settings are environment variables, read at start (`console/agent_console/config.py`):

| Variable | Default | What |
|---|---|---|
| `AGENT_CONSOLE_HOME` | `~/.agent-console` | state: index, scores, verdicts, defects, logs |
| `AGENT_CONSOLE_PORT` | `8790` | port on 127.0.0.1 |
| `AGENT_CONSOLE_TREE_ROOTS` | your home folder | folders whose sessions count as "project" scope (colon-separated) |
| `AGENT_CONSOLE_WORKTREE_ROOTS` | none | folders that hold git worktrees |
| `AGENT_CONSOLE_PROJECT_REMOTE` | none | a checkout whose `origin` URL contains this text counts as project scope |
| `AGENT_CONSOLE_KEY_PREFIXES` | none (any `ABC-123`) | ticket key prefixes, space-separated |
| `AGENT_CONSOLE_KEY_PATTERNS` | none | extra full-match patterns for a leading `[KEY]` |
| `AGENT_CONSOLE_DEFAULT_PROJECT` | none | checkout to score a run against when its folder is gone |
| `AGENT_CONSOLE_CLAIMS_REPO` | none | a project that uses the `claims` and `impact_map` gates |
| `AGENT_CONSOLE_TZ` | the Mac's zone | the day boundary |

To give the LaunchAgent a variable, add it to the plist's `EnvironmentVariables` block and run `bash console/service.sh restart`. `service.sh install` rewrites the plist, so keep your additions noted.

## A second console instance on another port

A second instance needs its own label, port and state folder:

```bash
AGENT_CONSOLE_LABEL=local.agent-console.8792 AGENT_CONSOLE_PORT=8792 AGENT_CONSOLE_HOME="$HOME/.agent-console-8792" bash console/service.sh install
AGENT_CONSOLE_LABEL=local.agent-console.8792 AGENT_CONSOLE_PORT=8792 AGENT_CONSOLE_HOME="$HOME/.agent-console-8792" bash console/service.sh status
AGENT_CONSOLE_LABEL=local.agent-console.8792 AGENT_CONSOLE_PORT=8792 AGENT_CONSOLE_HOME="$HOME/.agent-console-8792" bash console/service.sh uninstall
```
