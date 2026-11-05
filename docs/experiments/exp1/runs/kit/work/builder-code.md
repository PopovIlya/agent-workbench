PASS

# builder report, step code: EXP1-KITC (re-run after the test-helper fix, extra loop per answers 38)

Path: `docs/agents/work/EXP1-KITC/builder-code.md`

## Summary
All 47 tests in `console/tests/test_compare.py` are green. No product code changed in this run; the earlier FAIL was a test-helper defect, fixed by the test-designer (Round 2 helper fix).

## Changes (product code only; no test edited by me)
- `console/agent_console/compare.py` (new), `console/agent_console/server.py` (GET `/compare`), `console/agent_console/__main__.py` (`compare` subcommand). No new dependencies.

## Results (as observed this run)
- `cd console && .venv/bin/python -m pytest tests/test_compare.py -q -p no:cacheprovider` -> 47 passed.
- `cd console && .venv/bin/python -m pytest tests -q -p no:cacheprovider` -> 492 passed.
- `console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider` (repo root) -> 49 passed.
- `console/.venv/bin/python -m ruff check .` -> All checks passed.

## CON-027 no-argument start: verified by a check (not a test)
Throwaway instance: `AGENT_CONSOLE_PORT=18791 AGENT_CONSOLE_HOME=/tmp/kitc-home python -m agent_console` (no arguments). `GET /` -> 200; `GET /compare?a=X&b=Y` -> 404 (unknown key). Process killed afterwards. The running console and `~/.agent-console` were not touched.

## Agent decision (no rule covers; narrowest reading, answers 37)
- JSON shape: `{a, b, difference, ratio}`; each column has `role_runs{total,failed,repeat}`, `tokens`, `tokens_by_model`, `cost_usd`, `unpriced_messages`, `wall_s`, `active_role_s`, `main_session` (null when none), `sub_agents_cost_usd`, `main_share_of_sub_cost`. Times are raw seconds, "n/a" is `null`.
- Per-model difference and ratio are in the JSON and the page; a model missing on one side gives n/a (shown as `-` in that side's cell).
- Unknown key: known if it has a run by effective key, a run by own key, or a refused spawn naming it. Page status 404; missing/too long (over 60 chars) key 422.
- Wait gap of exactly 60 s counts (under 60 is zero). Over 2 h means strictly more than 7200 s.
- Machine-written user records without `origin.kind` are detected by text prefix (task-notification, local-command, interrupt marker, system-reminder, hook output) and by tool_result / isMeta / toolUseResult.
- A run counts as having a final reply if its last real assistant record has `stop_reason` end_turn OR contains a `SubagentHandback` call (kit roles end that way with stop_reason tool_use; without this every kit run would be failed). Missing `stop_reason` is treated as "not end_turn" (failed).
- An API error or denial earlier in a run, followed by a normal assistant record, does not make the run failed ("ended in").
- Synthetic assistant records that are not API errors are ignored.
- Log file gone: run is not counted as failed, wait is zero.
- Page and CLI text: label columns a / b / difference (b - a) / ratio (b / a); counts shown whole, ratio of the share row shown with 2 decimals; the page links `/static/style.css` (inline style would be blocked by the CSP).
- The CLI runs `Store().ingest()` against the normal state dir (`AGENT_CONSOLE_HOME`), so it writes the index (not the logs).
- Page does not start a rescan; it reads the index as it is.

- Agent decision: the final reply of the builder is via SubagentHandback; a run whose last real assistant record contains a SubagentHandback call counts as having a final reply (already listed above).
- Agent decision: unknown key gives HTTP 404 on the page, exit code 2 in the CLI.
- Agent decision: JSON field names as listed above.

## CONFLICT / UNVERIFIED
- UNVERIFIED: real-log behaviour of `stop_reason` for the last record of a run still in progress (counted as failed) and denial wording beyond the two prefixes. Agent decision: keep the narrowest reading (in-progress = failed; only the two known denial prefixes).
- CON-027 no-argument start: now verified (see above).
- No CONFLICT between rules.
