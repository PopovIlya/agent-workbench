# Agent console: design

Main goal: see what your Claude Code agents cost, how long they took and how well they did, from the session logs alone.
Does: reads `~/.claude/projects/**` (read-only), indexes it into `~/.agent-console/index.sqlite`, scores each role run, serves a local web UI.
Does not: write to any repo, call a model (the judge stays off unless you switch it on), or listen on anything but `127.0.0.1`.

## 1. Session data

- Layout: `~/.claude/projects/<dir>/<session>.jsonl` (main session) and `<session>/subagents/agent-<id>.jsonl` with `agent-<id>.meta.json`
  (`agentType` = the role, `toolUseId` = the spawning `Agent` call). `<dir>` is the launch path with `/` replaced by `-`; new folders are
  found by scanning, never from a fixed list.
- Fields used (names only): `sessionId`, `timestamp`, `cwd`, `gitBranch`, `message.model`, `message.usage`, `tool_use` / `tool_result`
  blocks, `system` records with `subtype: api_error`.
- Token dedup: one API message is written as several records with the same `usage`. Group by `message.id` (fallback `uuid`), count once.
- The index is a cache. It is rebuilt from the logs when its schema version or the time zone changes.

## 2. Which sessions count ("project" scope)

A main session is in scope when its first `cwd` is under `AGENT_CONSOLE_TREE_ROOTS` (default: your home folder) or
`AGENT_CONSOLE_WORKTREE_ROOTS`, or its checkout's `origin` URL contains `AGENT_CONSOLE_PROJECT_REMOTE`. A sub-agent counts with the
session that spawned it. "all" shows everything.

## 3. Ticket key

First source that yields a key wins; the source is shown in the UI: a leading `[KEY]` in the spawn description or the first prompt,
a change file / kit work folder path, a key in a git command, a key in the cwd folder name, the worktree's branch, any edited path,
then the text. `AGENT_CONSOLE_KEY_PREFIXES` (for example `PROJ OPS`) limits keys to your prefixes; without it any `ABC-123` counts
except common non-ticket tokens (`UTF-8`, `SHA-256`, ...). `AGENT_CONSOLE_KEY_PATTERNS` adds full-match patterns for a leading `[KEY]`.
A main session takes the key of at least 80 % of its keyed sub-agent runs.

## 4. Scores

`agent_scoring/` scores each sub-agent run of a known role (a role with a criteria file in `roles-22/criteria/` or `kit/criteria/`):
see `RUBRIC.md` (v1) and `RUBRIC-v2.md` (v2, the one the console runs). The scorer judges a run against the project it worked in: the
git checkout of the run's `cwd`, and that project's `docs/agents/PROJECT.md` (requirement map, test-case files, change files, trunk
branch). `AGENT_CONSOLE_DEFAULT_PROJECT` names a checkout for runs whose folder is gone. Optional: `AGENT_CONSOLE_CLAIMS_REPO` turns on
the claims / impact-map scope check for a project that uses those gates.

## 5. State and safety

- State: `~/.agent-console/` (mode 0700): index, `scores.jsonl`, the person's `verdicts.jsonl`, `defects.jsonl`, flag decisions,
  `judge.json`, `calibration.json`, logs. Never in the repo.
- Text shown on demand is redacted with `.gitleaks.toml` of the workbench plus built-in rules.
- HTTP: loopback only, a Host header check (DNS rebinding), strict CSP, no write endpoint except the person's own verdicts, defect
  reports, flag decisions and a rescan.
- Cost: `pricing.yaml` holds list prices per model; a model without a price shows "cost unknown".
