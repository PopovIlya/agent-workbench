# Requirements: console

File: `docs/requirements/console.md`. Prefix CON. As-is rules for the agent console, collected for EXP1-KITC (ticket comparison report).

---

### CON-001
- status: observed
- statement: Every run (a main session file or a sub-agent file) gets exactly one ticket key from the first source that yields one, in this order: worklog, spawn description lead, first-prompt lead, change/work file path, git command, worktree directory, worktree branch, log branch, other edited path, key in spawn text, key in first prompt, the spawning run's ticket. No source: the run has no key.
- source: console/agent_console/tickets.py:52-113
- scope: as-is
- tests: none
- notes: 

### CON-002
- status: observed
- statement: A leading `[KEY]` in a spawn description or first prompt is a ticket key whatever its format, if it has a hyphen and fully matches a configured pattern. `[WIP]` and `[TODO]` are never keys.
- source: console/agent_console/tickets.py:69-74; config.py:70-78
- scope: as-is
- tests: none
- notes: 

### CON-003
- status: observed
- statement: All other key sources accept only the plain `ABC-123` form (or only the prefixes in AGENT_CONSOLE_KEY_PREFIXES); tokens such as UTF-8, ISO-8601, SHA-256 are never keys. Prefixes are read once at start.
- source: console/agent_console/tickets.py:34-49
- scope: as-is
- tests: none
- notes: 

### CON-004
- status: observed
- statement: A sub-agent run with no key of its own takes its parent session's key in force when it started, else the parent's overall key.
- source: console/agent_console/store.py:~512-523
- scope: as-is
- tests: none
- notes: 

### CON-005
- status: observed
- statement: The key that counts for a run (`ticket_eff`) is its own key for a sub-agent. A main session takes the key carried by at least 80% of its keyed sub-agent runs; if the children disagree or have no key it keeps its own. One key per session, cost is never split.
- source: console/agent_console/tickets.py:146-167; config.py:145
- scope: as-is
- tests: none
- notes: 

### CON-006
- status: observed
- statement: A ticket's runs are all runs whose effective key equals the key (main sessions and sub-agent runs together). Runs with no key are grouped under `(no ticket)`.
- source: console/agent_console/ctq.py:30,137 (r["key"]=ticket_eff or NOKEY); ctq_pages.py:68-69
- scope: as-is
- tests: none
- notes: 

### CON-007
- status: observed
- statement: The console reads session logs from ~/.claude/projects (AGENT_CONSOLE_LOG_ROOT), builds a local SQLite index (~/.agent-console/index.sqlite) and rescans every 30 s and on page load. A run is one main-session file or one sub-agent file.
- source: console/agent_console/config.py:95; server.py:31,112-119; store.py:24-27
- scope: as-is
- tests: none
- notes: 

### CON-008
- status: observed
- statement: Only runs in a 'project' scope are shown by default (main sessions by first cwd under the tree roots, default the home directory; sub-agents follow their parent session). Scope `all` includes the rest.
- source: console/agent_console/store.py:~555-585; ctq.py:select
- scope: as-is
- tests: none
- notes: 

### CON-009
- status: observed
- statement: Token counts and cost come from one usage row per API message (message id + request id); a message repeated in several files (resumed session, copied transcript) is counted once.
- source: console/agent_console/store.py:383-390
- scope: as-is
- tests: none
- notes: the brief asks for tokens per model; per-message model is stored but not aggregated by model anywhere

### CON-010
- status: observed
- statement: Tokens are stored per message as input, output, cache read, cache write 5 min and cache write 1 h, with the served model id. Per-model totals are not exposed by any existing page; only the sum of cache-write kinds is shown.
- source: console/agent_console/store.py:33-35; ctq.py:119-130
- scope: as-is
- tests: none
- notes: the brief asks for tokens per model; per-message model is stored but not aggregated by model anywhere

### CON-011
- status: observed
- statement: Cost of a message is its tokens times the price per 1M tokens in pricing.yaml for the model matched by substring (longest key first), else the model's tier default, times the regional multiplier. The over-100K price table applies to a request whose input+cache tokens exceed 100,000 (only haiku-5-5 has one).
- source: console/agent_console/pricing.py:48-80; console/pricing.yaml:11-23
- scope: as-is
- tests: none
- notes: 

### CON-012
- status: observed
- statement: A message whose model matches no key and no tier gets no price: it counts as zero cost and is counted in an `unpriced` total, not reported per ticket. A missing needed price also gives no cost.
- source: console/agent_console/pricing.py:60-78; ctq.py:131-135
- scope: as-is
- tests: none
- notes: 

### CON-013
- status: observed
- statement: pricing.yaml is read from the console folder (or AGENT_CONSOLE_PRICING) when the app starts; a missing or broken file gives an empty table and all costs unknown. Prices are marked as estimates.
- source: console/agent_console/pricing.py:37-46; config.py:133; pricing.yaml:1-10
- scope: as-is
- tests: none
- notes: 

### CON-014
- status: observed
- statement: Ticket cost is the sum of its runs' message costs; the console already reports cost for main sessions and for sub-agent runs separately (`cost_main`, `cost_sub`) and the overview computes the main share of total spend.
- source: console/agent_console/ctq_pages.py:94,133
- scope: as-is
- tests: none
- notes: 

### CON-015
- status: observed
- statement: A run's `rounds` is its number of API messages (model calls), not a repeat or retry count.
- source: console/agent_console/store.py:470; ctq_pages.py:117
- scope: as-is
- tests: none
- notes: 

### CON-016
- status: observed
- statement: A 'return' (repeat round) is a derived flag: a non-gate sub-agent role runs again on the same ticket after a gate role (reviewer, requirements-reviewer, verifier, kit-reviewer, kit-security, kit-verifier) ran in between; the round number counts per role. Main sessions are not considered.
- source: console/agent_console/flags.py:21,125-142
- scope: as-is
- tests: none
- notes: 

### CON-017
- status: observed
- statement: A run counts as rejected (`reject_count`) when its replies start with the word FAIL on the first line (kit roles) or contain REJECT in the first 300 chars (other roles). The flag `reject` is raised only for gate roles. The console has no field named 'failed' for a role run; the scorer also writes a per-run `round` and `delivered` into scores.jsonl.
- source: console/agent_console/store.py:477; flags.py:143-145; parser.py:222; ctq.py:113,119
- scope: as-is
- tests: none
- notes: 

### CON-018
- status: observed
- statement: Wall time of a ticket (`calendar_s`) is from the first run start to the last run end; `working_s` = open time minus waiting, parked and blocked. These are clipped to the selected period (default: the whole index).
- source: console/agent_console/ctq.py:1-12,265; ctq_pages.py:95
- scope: as-is
- tests: none
- notes: 

### CON-019
- status: observed
- statement: A human wait is the idle gap before a user record of origin 'human' (or unmarked), taken for every gap of any length; AskUserQuestion calls are 'ask' waits. A human or ask wait over 2 hours is 'parked' and excluded from waiting. Records of other origin (notifications) are 'notification' waits. No 60-second floor exists and the end-of-turn stop reason of the previous assistant message is not read.
- source: console/agent_console/timing.py:73-94; config.py:143; parser.py (no stop_reason)
- scope: as-is
- tests: none
- notes: CONFLICT: brief (EXP1) wait definition (stop for a person, gaps under 60 s count as zero) vs code (all human gaps, any length, no stop-reason test); see QUESTIONS.md

### CON-020
- status: observed
- statement: Only main sessions contribute waits to a ticket's `waiting_s`; sub-agent user records are tool plumbing and record no gap.
- source: console/agent_console/store.py:311-313; ctq_pages.py:274
- scope: as-is
- tests: none
- notes: 

### CON-021
- status: observed
- statement: Per-role run time is the clipped duration of each run (start to end); a per-run split into model, tool, test, waiting, parked, blocked time is stored. No ticket-level 'active role time' term exists.
- source: console/agent_console/ctq_pages.py:84,269; timing.py:125-176
- scope: as-is
- tests: none
- notes: 

### CON-022
- status: observed
- statement: The server exposes read-only JSON under /api/ctq/ (meta, filters, overview, tickets, tickets/{key}, roles, roles/{role}, sessions) plus /api/runs/{id}, /api/status, /health; the page is a single hash-routed HTML app at `/` (#/overview, #/tickets, #/ticket/<key>, #/roles, #/role/<r>, #/sessions, #/run/<id>). There is no /compare route and no comparison API.
- source: console/agent_console/server.py:121-203; ctq_api.py:39-75; static/app.js:74-96
- scope: as-is
- tests: none
- notes: 

### CON-023
- status: observed
- statement: An unknown key on /api/ctq/tickets/{key} returns HTTP 200 with `{"empty": true}`; the verdict and defect POST endpoints return 404 for an unknown ticket (checked against runs.ticket_eff or ticket).
- source: console/agent_console/ctq_pages.py:253-256; server.py:186-192
- scope: as-is
- tests: none
- notes: 

### CON-024
- status: observed
- statement: The server binds only 127.0.0.1, rejects other Host headers (404), and sets security headers (CSP default-src 'self', no-store) on every response; static files are served only from console/static.
- source: console/agent_console/server.py:32-38,95-110,198-203,211-212
- scope: as-is
- tests: none
- notes: UNVERIFIED: browser formatting not read

### CON-025
- status: observed
- statement: `python -m agent_console` takes no arguments and no subcommands: it always starts the web server (port 8790). There is no CLI for reports and no exit-code convention.
- source: console/agent_console/__main__.py:1-3; server.py:208-227
- scope: as-is
- tests: none
- notes: 

### CON-026
- status: observed
- statement: Rounding and formatting of durations and money on pages is done in the browser/page helpers; the JSON API returns raw floats (seconds, USD). Python dict keys are not sorted explicitly (FastAPI returns the dict in insertion order).
- source: console/agent_console/ctq_pages.py:94-100 (raw floats); UNVERIFIED: browser formatting in static/ctq-lib.js not read
- scope: as-is
- tests: none
- notes: 

---

### CON-027
- status: new
- statement: Comparison entry points: a server-rendered page at `/compare?a=<KEY>&b=<KEY>`, outside the hash-routed app, under the same local-only Host check and security headers as the existing server (CON-024), and a CLI `python -m agent_console compare <KEY> <KEY> [--json]`. `compare` is a subcommand; with no arguments `python -m agent_console` starts the server as today (verified by a check, not by a test, in the code step). A missing or wrong number of keys is handled by CON-054.
- source: brief 1; answers 9, 21, 27, 38
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-025 (no-argument behaviour kept); CON-022 (adds a route)

---

### CON-028
- status: new
- statement: The comparison compares exactly two keys, a and b, read-only. No charts, no more than two tickets, no editing of data.
- source: brief out of scope
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-029
- status: new
- statement: The same key given twice compares that ticket with itself. Comparing two runs of one ticket is out of scope.
- source: answer 11
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-030
- status: new
- statement: A ticket for the comparison is the set of runs whose effective key equals the key (main sessions and sub-agent runs), by the console's existing key rules.
- source: brief decisions; CON-006
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-031
- status: new
- statement: The comparison always reads all logs, ignoring the default period and scope.
- source: answer 6
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-008, CON-018 (period clip and project scope do not apply to the comparison)

---

### CON-032
- status: new
- statement: A key is unknown when it has no runs and no sessions in any log (a spawn refused before it started that names the key also makes it known, CON-037). An unknown key shows a clear error on the page with HTTP status 404 and gives exit code 2 in the CLI.
- source: brief 4; answer 6; Agent decision (answer 37): 404 for the page, builder-code.md
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-023 (the 200 empty answer of the ticket API stays for that API). Agent decision: the page status 404 is the narrowest reading of 'clear error'

---

### CON-033
- status: new
- statement: Role runs are sub-agent runs only. A main session is not a role run: it is not counted in the role-run total, the failed count or the repeat rounds. It appears only in the main-session rows (wait time, tokens, cost) and in the share row. Per ticket: role-run total, failed count, repeat-round count.
- source: brief 2; answer 19; CON-006
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-034
- status: new
- statement: A repeat round is any run of a role on the same ticket after its first run of that role (run 2, 3, ...). No verdict is needed.
- source: answer 2
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-016 (flag kept as is; the comparison does not use it)

---

### CON-035
- status: new
- statement: A failed run is a sub-agent run that did not complete: it ended in an API error, a permission denial, was denied, or has no final assistant reply. A FAIL, BLOCKED or REJECT verdict is a result, not a failed run. FINAL STATE DECIDES (Agent decision, answer 37): a run is failed when its last event is an API error or a permission denial, i.e. no normal assistant record follows it; a later normal assistant reply clears an earlier API error (and an earlier denial), and an API error after a normal reply makes the run failed. FINAL REPLY (Agent decision): a final reply is the last normal assistant record with `stop_reason` `end_turn` and some non-blank text; a record with end_turn but only blank text or non-text blocks is no final reply. A SubagentHandback call is NOT a final reply (a kit run that ends with a handback and stop_reason `tool_use` is failed, a missing `stop_reason` counts as not end_turn). Assistant records whose model is `<synthetic>` and that are not API errors are skipped: they neither set nor clear the state (F12; equivalent in effect to no record). DENIAL (F11): a denied tool result counts when it is the run's latest event; a run that ends with `end_turn` and a text reply but has a denied tool result after its last normal assistant record is failed; a tool result with `is_error` true that is not a denial (wording not matching) does not fail a run that ends with `end_turn` and a text reply. In the logs: an API error is a record with `isApiErrorMessage` true (an assistant record with model `<synthetic>`, status in `apiErrorStatus`) or a `system` record with subtype `api_error`; a permission denial is a `tool_result` block with `is_error` true whose content starts with `Permission for this ` or `The user doesn't want `, in a user record with a string `toolUseResult`. A run whose log file is gone is not counted as failed. A run still in progress (last record not end_turn) is counted as failed. Only these fields are read; message text is never output.
- source: answers 3, 13, 22, 37, 38; parser.py:104-117,200-209 (api error fields); compare.py:65-91 (run_failed); reviewer-3 F11, F12; builder-tests-r2 Agent decisions
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes since the tests were written: final-state wording, handback is not a final reply, denial wording (F11), synthetic skip (F12). CONFLICT: the code (compare.py:82) clears the flag on every later normal assistant record, so a denial that is followed by a later normal reply, including end_turn, does NOT fail the run; the F11 wording above is therefore 'denial is the latest event'. If the person wants any denial in a run to fail it, the code must change (see report). UNVERIFIED: denial wording other than the two prefixes is missed

---

### CON-036
- status: new
- statement: The comparison may read the raw session logs, read-only, to find failed runs; the definition in the failed-run rule is not narrowed.
- source: answer 13
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: UNVERIFIED: which log fields mark an API error, a permission denial or a missing final reply were not read (parser.error_category exists)

---

### CON-037
- status: new
- statement: A sub-agent spawn that failed before it started (denied, agent type not found, worktree error, and so on: any spawn whose `Agent`/`Task` tool_result has `is_error` true and for which no run file exists) counts in the run total and the failed count of its ticket, and takes a number in the order of runs of its role, so it counts when numbering repeat rounds (it is a run). Its ticket key comes from the tool_use input (description lead or key in the spawn text, by CON-001 order). If no key can be taken from that input, the spawn is not counted for any ticket. A spawn with no tool result and no run file (for example the session ended first) is not counted: no evidence of a run (answer 33; answer 31 applies only to spawns whose log shows an error result). A spawn whose tool result is not an error but which has no run file counts as a run (run total and repeat-round order) and is not failed (answer 35; see CON-053). A spawn that has a run file is not counted twice. Each refused spawn needs its own tool_use id.
- source: answers 18, 22, 25, 31, 33, 35, 38; logs read read-only; compare.py:147-151
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes since the tests were written: answers 25, 31, 33, 35 added. UNVERIFIED: the full set of refusal wordings. The test helper was fixed to give refused spawns unique ids (answer 38).

---

### CON-038
- status: new
- statement: Tokens are split into input, output, cache write and cache read, per model, for each ticket, main session included. The model is each message's own served model id. A message with no model id is counted under the model name `unknown` (answer 29). Cache write is the sum of the 5-minute and 1-hour kinds.
- source: brief 2; answers 1, 29; CON-010
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-010 (adds a per-model total). Changed since the tests were written: unknown model name. An unknown-model message is unpriced (CON-040)

---

### CON-039
- status: new
- statement: Cost is shown per model and in total, from the prices in pricing.yaml as on the base commit, by the existing pricing rules (substring match, tier default, over-100K table, regional multiplier).
- source: brief 2 and decisions; CON-011
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: none; keeps CON-011

---

### CON-040
- status: new
- statement: Unpriced messages still add zero to cost. The comparison shows the number of unpriced messages next to the cost of that ticket.
- source: answer 8
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-012 (the count is now reported per ticket)

---

### CON-041
- status: new
- statement: Wall time is from the first to the last record timestamp across all the ticket's session files, main session and sub-agents together.
- source: answer 14
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-018 (calendar_s not used)

---

### CON-042
- status: new
- statement: Active role time is the sum of the durations of the ticket's runs; parallel runs add up.
- source: answer 7
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-021

---

### CON-043
- status: new
- statement: Wait time is the sum of the gaps between an assistant turn that waits on the person and the next message that ends the gap. Only text the person typed (a real human message, including a slash command) ends a gap; the person's answer to an AskUserQuestion call ends the gap of that call. A rejected permission prompt is a stop and its gap ends at the next typed message. These do not end a gap: tool results, task notifications, hook output, local command output, the `[Request interrupted by user]` marker and other machine-written user records. A user record with `origin.kind` is typed by the person only when the kind is `human`; in older logs without an origin, a user record that is not a tool result (no `toolUseResult`, not `isMeta`) and does not start with a machine-written marker (task-notification, local-command, interrupt marker, system-reminder, hook output, bash output) counts as typed. Gaps under 60 s count as zero (a gap of exactly 60 s counts, Agent decision). Gaps over 2 hours (strictly more than 7200 s) count as waiting; no gap is excluded as parked. Assistant records that are API errors or `<synthetic>` are skipped.
- source: brief decisions; answers 4, 24, 30, 37; compare.py:94-128
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-019 (console rule kept for other pages). Changed since the tests were written: what ends a gap (answers 24, 30), 60 s boundary and the machine-record detection list (Agent decisions)

---

### CON-044
- status: new
- statement: A turn that waits on the person is an assistant record whose `stop_reason` is `end_turn`, or that ends with an AskUserQuestion tool call, or a permission prompt. Seen in the logs: `stop_reason` values `end_turn`, `tool_use`, `stop_sequence`, `refusal` and empty. A permission prompt leaves no record of its own (only the later refusal result or a long tool call); it is therefore not counted as a stop, except where the AskUserQuestion call or end_turn is present. A rejected prompt's gap ends at the next typed message (CON-043).
- source: answers 15, 24, 30; logs read read-only; compare.py:108-128
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: UNVERIFIED: a permission prompt that was approved leaves no trace and is not counted

---

### CON-045
- status: new
- statement: Besides wait time the comparison shows one extra figure: the part of the wait time that came from gaps over 2 hours.
- source: answer 4
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-046
- status: new
- statement: Only the main session's user records give waits; sub-agent runs contribute none.
- source: CON-020 kept; brief 2
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: none

---

### CON-047
- status: new
- statement: The share row is main session cost divided by sub-agent cost. If the sub-agent cost is zero it shows "no sub-agents", not 0 and not infinity.
- source: brief 2; answer 5
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-014 (new derived figure)

---

### CON-048
- status: new
- statement: A ticket with no main session shows "no main session" in the main-session rows (wait time, main tokens, main cost) and in the share row. Ticket totals (role runs, total tokens, wall time and so on) show their real value, including 0. With several main sessions on a ticket, their tokens, cost and waits are summed for the main-session rows and the share.
- source: brief 4; answers 16, 17, 20
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-049
- status: new
- statement: A third column shows the difference (b minus a) and the ratio (b divided by a). If a is 0 or either side has no value the ratio is "n/a"; the difference shows only when both sides have a value, else "n/a".
- source: brief 3; answer 10
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-050
- status: new
- statement: Display rounding, page and CLI text alike; JSON keeps raw values. Tokens are shown in thousands as `12k` (no thousands separator); dollars to cents, always two decimals (`$0.50`); time in whole minutes written `12 min`, an hour or more stays in minutes (`135 min`); counts as whole numbers; the ratio with 2 decimals. A .5 tie rounds away from zero. A negative difference rounds its size the same way and keeps its sign, but a negative difference that rounds to zero is shown as `0k`, `0 min`, `0` or `$0.00`, never as `-0k`. The difference and the ratio are computed from the raw values, then rounded for display. The existing browser helpers differ (usd shows one decimal from $0.995 to $99.5 and whole dollars above; dur shows seconds, hours or days), so the comparison does its own rounding, server-side, and does not reuse them.
- source: brief decisions; answers 12, 22, 26, 32, 34, 36; static/ctq-lib.js:34-48
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: none; ctq-lib.js read. Changed since the tests were written: ratio 2 decimals (26), tie and sign (32), `0k` for -0 (34), `12 min` (36)

---

### CON-051
- status: new
- statement: JSON output (`--json` and the page's data) is stable: keys sorted, fixed field names. Shape (Agent decision, answer 37): `{a, b, difference, ratio}`; each column holds `key`, `role_runs{total, failed, repeat}`, `tokens`, `tokens_by_model`, `cost_usd`, `unpriced_messages`, `wall_s`, `active_role_s`, `main_session` (null when there is none), `sub_agents_cost_usd`, `main_share_of_sub_cost`. Times are raw seconds, an `n/a` value is `null`. `difference` and `ratio` also carry the per-model values; a model missing on one side gives `null`.
- source: brief 5; builder-code.md Agent decision
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: changes: CON-026 (key order was not sorted). Changed since the tests were written: field names fixed here

---

### CON-052
- status: new
- statement: No new dependencies.
- source: brief decisions
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: 

---

### CON-053
- status: new
- statement: Spawns and run numbering: a sub-agent spawn counts as a run when it has a run file, or its tool result is not an error (run total and repeat-round order; not failed when it has no run file). A spawn whose result is an error and has no run file counts as a run and as failed (CON-037). A spawn with neither result nor run file is not counted.
- source: answers 18, 25, 31, 33, 35
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: CONFLICT: code vs rule: compare.py:147-151 counts only spawns with `is_error` 1; a non-error spawn with no run file (answer 35) is not read there. UNVERIFIED whether the index can contain such a spawn; the test step should cover it and the code step may need a change

---

### CON-054
- status: new
- statement: A missing parameter a or b (absent or empty; the code tests `not a`, so a value of only spaces is taken as a key): the page shows one clear error message with HTTP status 422, with no form, no swap action and no "compare with" link. The CLI with a wrong number of keys prints usage and exits 2. There is no length limit on a key (Agent decision, answer 37: the earlier 60-character guard was removed).
- source: answers 27, 37; server.py:198-207; compare.py cli_main
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: Changed since the tests were written: 422 and exit 2 (27), no key length limit

---

### CON-055
- status: new
- statement: Keys follow the console's existing key rules (CON-001 order, CON-006); no extra case folding is added: `abc-1` and `ABC-1` are different keys unless the console rules treat them alike.
- source: answer 28
- scope: EXP1-KITC
- tests: console/tests/test_compare.py
- notes: Changed since the tests were written: new rule

