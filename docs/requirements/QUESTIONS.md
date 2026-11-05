# Questions

Open questions for the product owner. Each names the rule and what was searched (brief = docs/agents/work/EXP1-R22C/change.md; answers = ~/exp1/answers.md 1-37; decisions file: none in the profile).

## EXP1-R22C (asked 2026-11-05 by the business analyst)

### Q-001 · CON-014, CON-021 · ANSWERED 2026-11-05 (answers 19, 20; with answer 7) · applied in CON-013, CON-014, CON-015, CON-016, CON-021, CON-024
Do "role runs" (total, failed, repeat rounds) and "active role time" include the ticket's main session(s), or only sub-agent runs?
Searched: brief item 2 ("including its main sessions"), answers 2, 7, 17, 18. Answer 18 speaks of sub-agent spawns; answer 7 says "sum of run durations" without saying which runs.

### Q-002 · CON-022 · ANSWERED 2026-11-05 (answer 24) · applied in CON-022 v2
Which user record ends a wait gap? (a) the next user record of any kind, or (b) only the next record from the person, so that a task notification, hook output or other non-human user record does not end it. For an AskUserQuestion stop, is the answer record (tool_result) the end?
Searched: brief decisions ("next user message") vs brief item 2 ("next human message"); answers 4, 15.

### Q-003 · CON-016 · ANSWERED 2026-11-05 (answer 25) · applied in CON-016 v2
Does a denied spawn (answer 18) count as a run of its role when numbering repeat rounds?
Searched: answers 2, 18.

### Q-004 · CON-026 · ANSWERED 2026-11-05 (answer 26) · applied in CON-026 v2
How is the ratio b/a rounded on the page and in the CLI text (e.g. two decimals)? JSON keeps it raw.
Searched: brief decisions (rounding of tokens, dollars, time only), answers 10, 12.

### Q-005 · CON-010 · ANSWERED 2026-11-05 (answer 27; proposal not taken) · applied in CON-034
What does `/compare` show when a or b is missing? Proposal (as on GitHub's compare page): a form with two key fields, prefilled from the URL, and a swap a/b action; plus a "compare with ..." link from a ticket's page.
Searched: brief item 1, 4; answers 6, 11.

### Q-006 · CON-027 · ANSWERED 2026-11-05 (answer 28) · applied in CON-027 v2
Is the key matched exactly as written, or is `exp1-r22c` the same ticket as `EXP1-R22C`?
Searched: brief item 4, answer 6; observed tickets.py (only directory-name keys are upper-cased).

### Q-007 · CON-017 · ANSWERED 2026-11-05 (answer 29) · applied in CON-017 v2
Under which model do tokens of a message with no model id show (e.g. a row "unknown model")?
Searched: answers 1, 8.

## EXP1-R22C round 2 (asked 2026-11-05 by the business analyst)

### Q-008 · CON-022 · ANSWERED 2026-11-05 (answer 30) · applied in CON-022 v3
Do user records with no `origin` field end a wait gap? A read-only log scan shows typed messages carry origin.kind "human", but these records have no origin: slash commands (`<command-name>...`), "[Request interrupted by user]", local command output (`<local-command-...>`), and plain text in older logs or non-interactive runs. Current rule reading: only origin.kind "human" ends a gap, so none of these do.
Searched: answers 4, 15, 24; brief item 2 ("next human message"); CON-022 history; logs in ~/.claude/projects (field names only).

### Q-009 · CON-014, CON-015 · ANSWERED 2026-11-05 (answer 31) · applied in CON-014 v3, CON-015 v3, CON-016 v3, CON-021 (note)
Is a spawn that failed for a reason other than a denial ("Agent type '<x>' not found", "Cannot create agent worktree ...", no run file) counted like a denied spawn (in the run total and as failed), or not counted?
Searched: answers 18, 22, 25; CON-014, CON-015; observed flags.py spawn_failure; logs in ~/.claude/projects (tool_result texts of Agent/Task calls, patterns only).

### Q-010 · CON-026, CON-029 · ANSWERED 2026-11-05 (answer 32) · applied in CON-026 v3, CON-029 v3
Display details the brief leaves open: (a) ties: is 0.5 rounded up, or half to even (Python round() gives 2 for 2.5, JS Math.round gives 3); (b) negative differences: is -2.5 shown as -3 or -2; (c) "tokens to thousands": shown as "12 K" or "12,000", and how a value under 500 tokens shows ("0 K"); (d) are the difference and ratio computed from raw values and then rounded (current reading) or from the rounded values?
Searched: brief decisions; answers 10, 12, 22, 26; console/static/ctq-lib.js usd()/dur(); console/static/app.js fmtTok().

## EXP1-R22C round 3 (asked 2026-11-05 by the business analyst)

### Q-011 · CON-014, CON-015, CON-016 · ANSWERED 2026-11-05 (answer 33) · applied in CON-014 v4, CON-015 v4, CON-016 v4, CON-021 (note)
A spawn (Agent/Task tool_use) with no tool_result at all and no run file, e.g. the main session ended or was interrupted before the result was written: is it a spawn that failed before it started (counted in the run total, as failed and in the repeat-round order, answer 31), or not counted? Current reading: open; answer 31 names spawns that "failed", which presumes an error result.
Searched: answers 18, 22, 25, 31; CON-014..016 history; Q-009.

### Q-012 · CON-029 · ANSWERED 2026-11-05 (answer 34) · applied in CON-029 v4
A negative difference that rounds to zero (e.g. -400 tokens, -$0.004, -20 s): shown with its sign ("-0k", "-$0.00", "-0 min") or as plain zero ("0k", "$0.00", "0 min")? Answer 32 says a negative difference keeps its sign; it does not say what happens when the size rounds to zero.
Searched: brief decisions; answers 12, 26, 32; Q-010.

## EXP1-R22C round 4 (asked 2026-11-05 by the business analyst)

### Q-013 · CON-014, CON-015, CON-016, CON-021 · ANSWERED 2026-11-05 (answer 35) · applied in CON-014 v5, CON-015 v5, CON-016 v5, CON-021 (note)
A spawn whose tool_result is not an error but for which no run file exists (e.g. the sub-agent file was removed or never written): is it counted (in the run total, as failed with no final reply, in the repeat-round order) or not counted? Current reading: not counted, since CON-014 counts run files plus error-result spawns only; but answer 33 ties counting to "evidence of a run", and a result is such evidence.
Searched: answers 18, 22, 31, 33; CON-014..016, CON-021 history; Q-009, Q-011.

### Q-014 · CON-029 · ANSWERED 2026-11-05 (answer 36) · applied in CON-029 v5
How is a time value in minutes written on the page and in the CLI text: `12 min`, `12m` or a bare `12`? Answer 34 lists `0` next to `0k` and `$0.00`, which may mean a bare number; and do values of an hour or more stay in minutes (e.g. `125 min`)?
Searched: brief decisions; answers 12, 32, 34; CON-029; console/static/ctq-lib.js dur().

## EXP1-R22C round 5 (asked 2026-11-05 by the business analyst)

### Q-015 · CON-029 · Agent decision (answer 37) 2026-11-05 · applied in CON-029 v6
A time value that rounds to zero (e.g. -20 s, or a zero wait time): shown as `0 min` (answer 36: time is written `12 min`) or as a bare `0` (answer 34 lists `0` next to `0k` and `$0.00`)? If the bare `0` in answer 34 means another figure (e.g. a run count), which one?
Searched: answers 32, 34, 36; Q-012, Q-014; CON-029 history.
Agent decision (answer 37): `0 min`. Reason: narrowest reading; answer 36 fixes one written form for time, so the bare `0` in answer 34 is a figure with no unit (e.g. a run count), not time.

## EXP1-R22C round 7 (review 1 findings, 2026-11-05, business analyst)

### Q-016 · CON-022 · Agent decision (answer 37) 2026-11-05 · applied in CON-022 v4, revised in CON-022 v5 · ANSWERED (answer 39) 2026-11-05 · applied in CON-022 v6
Several stops before one typed message (e.g. a stop, a task notification wakes the assistant, it stops again, then the person types): one gap from the earliest stop, one from the latest, or one per stop (overlapping)? A stop with no typed message after it: counted to the session end or not at all?
Searched: brief decisions and item 2; answers 4, 15, 24, 30; CON-022 history.
Agent decision (answer 37): one gap per typed message, from the latest stop before it; no interval counted twice; a stop with no typed message after it adds nothing. Reason: narrowest reading; the brief's gap ends at the next user message, so no message means no gap. The product owner may overturn it (alternative: from the earliest stop).
Revised 2026-11-05 (review 2 finding 1, CON-022 v5): an AskUserQuestion answer also ends a gap (answer 24), so the unit is a gap end = a typed message or an AskUserQuestion answer. Each gap end closes at most one gap, from the latest stop after the previous gap end; earlier stops in the same stretch add nothing; a stop with no gap end after it adds nothing. A rejected permission prompt is not a gap end (answer 24). Reason: narrowest reading consistent with answers 15, 24 and 30.
Answered 2026-11-05 (answer 39, extra loop, review 3): the product owner accepted the reviewer's two fixes as written: the first sentence says "the next gap end"; the list says "tool results other than an AskUserQuestion answer"; a dismissed AskUserQuestion is not an answer, it counts as a rejected prompt, so its gap ends at the next typed message. Applied in CON-022 v6.

### Q-017 · CON-024 · Agent decision (answer 37) 2026-11-05 · applied in CON-024 v2
How is the cost share shown on the page and in the CLI text (number or percent, decimals)? Which label wins when both "no main session" and "no sub-agents" apply?
Searched: brief item 2; answers 5, 16, 17, 26, 32.
Label: already decided (answers 16, 17): "no main session". Agent decision (answer 37): a plain number with 2 decimals, raw in JSON. Reason: narrowest reading; the share is a ratio and answer 26 fixes the ratio form.

### Q-018 · CON-026 · Agent decision (answer 37) 2026-11-05 · applied in CON-026 v4
A model used by one ticket only: is the other side 0 or "no value" (n/a)?
Searched: brief item 3; answers 1, 10, 17, 29.
Agent decision (answer 37): 0 on the other side; the difference shows; the ratio is n/a when a is 0. Reason: narrowest reading; answer 17 shows real values including 0, and "no value" is kept for "no main session" and "no sub-agents".

### Q-019 · CON-029 · Agent decision (answer 37) 2026-11-05 · applied in CON-029 v7
How is a negative dollar difference written, and do dollars use a thousands separator?
Searched: brief decisions; answers 12, 32, 34; CON-029 history.
Agent decision (answer 37): `-$1.23`, no thousands separator (`$1234.56`). Reason: narrowest reading; the same as tokens (`1234k`, answer 32), sign kept in front (answer 32).

## EXP1-R22C DoR part 2 (2026-11-05, system analyst)

### Q-020 · CON-027, CON-034 · Agent decision (answer 37) 2026-11-05 · applied in CON-027 v3, CON-034 v2
Which HTTP status does the page give for an unknown key (CON-027 left it to the system analyst)? Is `a=` (empty value) missing or an unknown key?
Searched: brief item 4; answers 6, 27, 28; CON-027, CON-034 history; server.py (`_ticket_known` answers 404, the validation handler answers 422).
Agent decision (answer 37): 404 with an HTML page naming the key (both keys when both are unknown); an empty value counts as missing (422, CON-034). Reason: narrowest reading; the console's existing ticket endpoints answer an unknown ticket with 404, and an empty key can name no ticket.

### Q-021 · CON-027, CON-013, CON-014 · already decided (answer 6) + Agent decision (answer 37) 2026-11-05 · applied in CON-027 v4, v5 (reworked in return round 1; the v3 reading is withdrawn)
A key found only as the own key of a main session whose effective key (CON-002) is another ticket, or only on a spawn with no run file: known or unknown? Do index rows of runs whose log file is gone count as "in any log"?
Searched: answers 6, 18, 19, 20, 31, 35; CON-002 notes; CON-013, CON-014; CON-015 / CON-022 and Q-022 (log file gone); review 5 (rr5-sa.md).
already decided (answer 6): unknown = no run and no session for the key in any log. So known = any run, main session (own or effective key) or counted spawn (CON-014) carries the key. A key that is only a main session's own key is known; with no data by CON-013 it shows "no main session" and 0 runs (brief item 4). A key only on a counted spawn is known.
Agent decision (answer 37): index rows of runs whose log file is gone count as "in any log", so such a key is known. Reason: narrowest reading; Q-022 keeps those runs' figures in the comparison, so their key has data to show.

### Q-022 · CON-015, CON-022 · Agent decision (answer 37) 2026-11-05 · applied in CON-015 v7, CON-022 v7
A run whose log file is gone (Claude Code deletes old logs; the index keeps their token rows): failed or not? Wait time of such a main session?
Searched: brief item 2; answers 3, 13, 22; CON-015, CON-022 history; store.py (`log_deleted`, RAW_TABLES carried over).
Agent decision (answer 37): the run counts as a run and is not failed; such a main session adds 0 wait time (it is still a main session, not "no main session"). Its tokens, cost, wall time and run time still come from the index. Reason: narrowest reading; a failure and a wait need markers in the log, and none can be read.

## EXP1-R22C DoR part 2, return round 1 (2026-11-05, system analyst)

### Q-023 · CON-034 · Agent decision (answer 37) 2026-11-05 · applied in CON-034 v3 · accepted (answer 40)
Is a value of only spaces (`a=%20%20`, or `"  "` in the CLI) missing or an unknown key?
Searched: answers 27, 28; CON-034 v2 and Q-020; review 5 (non-blocking gap).
Agent decision (answer 37): missing (422 on the page, usage and exit 2 in the CLI). Other values are used as written, not trimmed. Reason: narrowest reading; it can name no ticket, like an empty value, and answer 28 adds no other key handling.

### Q-024 · CON-010, CON-027 · Agent decision (answer 37) 2026-11-05 · applied in CON-010 v2 · accepted (answer 40)
What does the page show while the console builds its first index (an existing key may not be indexed yet; figures are partial)? Does the page start a rescan?
Searched: brief items 1, 4; answers 6, 21, 37; CON-010, CON-027; store.py `ingest` (rebuild every 250 files while `progress["initial"]`), server.py (30 s rescan loop, POST /api/rescan); check 1 item 6 (sa-check1.md).
Agent decision (answer 37): during the first index (index empty when the scan started, or no scan yet on an empty index) the page answers HTTP 503 with one clear message that the index is being built; no figures and no unknown-key error. The page never starts a rescan; it reads the index the console's own rescans keep fresh. Reason: narrowest reading; partial figures or a false "unknown" would be wrong answers, a GET that writes the index would be new behaviour, and the state is short and only after install or an index reset.

### Q-025 · CON-011, CON-012, CON-027 · ANSWERED (answer 40) 2026-11-05 · applied in CON-011 v2, v3 · asked 2026-11-05 for the product_owner (the repo owner)
The CLI `compare` must use all logs (answer 6), so the plan was: open the person's shared index (`~/.agent-console/index.sqlite`) and rescan it before comparing. Observed (store.py:100-105, `ingest`, `rebuild`): (1) when the CLI's shell has another AGENT_CONSOLE_TZ or AGENT_CONSOLE_KEY_PATTERNS than the stored ones, opening the index drops all derived rows and re-reads every log (minutes), and the running console then serves an empty or partial index; (2) every rescan rebuilds the `runs` table with the CLI's own repo root, TREE_ROOTS, WORKTREE_ROOTS and PROJECT_REMOTE, so the running console shows another scope until its next scan (up to 30 s; and its own next start resets again if the stored zone or patterns changed); (3) with AGENT_CONSOLE_CLAIMS_REPO set, the CLI runs a `git fetch`. Each safe fix changes what the CLI does or the size of the work, so the analyst does not decide it.
Searched: brief items 1, 2, 4; answers 6, 9, 12, 13, 37; CON-011, CON-012, CON-027; store.py, config.py, scope.refresh_claims; check 1 item 2 (sa-check1.md).
Options:
- A. Read-only CLI: the CLI only reads the shared index (no rescan, no reset, no fetch). No side effect. Figures are as of the console's last scan (at most 30 s old while it runs); if the console has not indexed a log yet, its key is "unknown". If there is no index, the CLI prints one line and exits 1. Smallest work. Bends answer 6 ("any log") to "any indexed log".
- B. Guarded rescan of the shared index: the CLI rescans as planned, but refuses (one line, exit 1, nothing written) when its zone or key patterns differ from the stored ones, and skips the claims fetch. Remains: (2) above for up to 30 s while the console runs, stated in README. Needs a small store.py option (no reset, no fetch) and its tests; size stays L.
- C. Private index: the CLI builds and keeps its own index in a separate file under AGENT_CONSOLE_HOME (e.g. `compare-index.sqlite`), never the console's. No effect on the console and answer 6 holds; the first CLI run reads every log (minutes; about 670 sub-agent files today), later runs are incremental. Doubles the disk use of the index.
- D. Accept the risk: rescan the shared index as planned; README states (1)-(3) and says to run the CLI from the console's environment.
Recommendation: B (keeps answer 6, no reset, no fetch, small change), with A as the smallest fallback.
In every option the tests use the `env` fixture (tmp AGENT_CONSOLE_HOME, AGENT_CONSOLE_NO_FETCH=1) and never touch ~/.agent-console.
Answer 40: option B, guarded refresh. The CLI refreshes the index but refuses with a clear message (exit code 2, nothing written; not exit 1 as option B proposed) if its time zone, key patterns or console home/checkout differ from the ones the index was built with. It never runs the git fetch. Applied in CON-011 v2. Agent decision (answer 37): an index that does not record these values, or has another schema version, is refused the same way.
Agent decision (answer 37), 2026-11-05, return round 2: the console-home check only catches an index copied or moved from another home; a CLI with another AGENT_CONSOLE_HOME opens that home's own index (none: builds a new one), so another home = another index and the console's index is never touched. Reason: narrowest reading, the index path comes from the home. Applied in CON-011 v3.

## EXP1-R22C DoR part 3, gap hunt (2026-11-05, QA analyst)
All below: small edge cases the brief and answers 1-41 do not cover; reversible before merge; no change of what the feature does, its scope or budget. Searched for each: CON-010..035 (statements, notes, history), Q-001..Q-025, answers 1-41, change.md system analysis, rr7-sa.md.

### Q-026 · CON-011 · Agent decision (answer 37) 2026-11-05 · applied in CON-011 v4
The CLI's console home (the console's own, or another) has no index file yet. Refuse, or build?
Searched: CON-011 v3 (states it only for another home), Q-025, answer 40, change.md "CLI index" (index_mismatch returns [] when no file), rr7-sa.md note 2.
Agent decision (answer 37): build a new index there, compare, exit 0. Reason: narrowest reading; no shared index exists yet, so nothing can differ and nothing shared is written over.

### Q-027 · CON-011 · Agent decision (answer 37) 2026-11-05 · applied in CON-011 v4 (note); in the statement since CON-011 v5
What does the CLI do when the index cannot be opened or refreshed (locked, not a database, scan ends in an error)?
Searched: CON-011, CON-027, CON-034 (exit 2 only), answers 9, 27, 40; change.md "CLI errors" (exit 1).
Agent decision (answer 37): one line on stderr naming the error class (no details), nothing on stdout, exit 1. Exit 2 stays for usage, refusal and unknown key. Reason: narrowest reading; a run-time failure is neither a wrong call nor a comparison.

### Q-028 · CON-027 · Agent decision (answer 37) 2026-11-05 · applied in CON-027 v6
Both keys unknown in the CLI ("one line naming the key"); the same unknown key as a and b.
Searched: CON-027 v5, CON-028, answers 11, 28, Q-020, Q-021.
Agent decision (answer 37): the CLI prints one line naming both keys (a, then b), exit 2; the same unknown key twice is named once, on the page and in the CLI. Reason: narrowest reading, keeps "one line" and matches the page.

### Q-029 · CON-034, CON-031 · Agent decision (answer 37) 2026-11-05 · applied in CON-034 v4
A third CLI key; extra or repeated page query parameters.
Searched: CON-031 (no more than two tickets), CON-034 v3, answer 27, Q-020, Q-023.
Agent decision (answer 37): a third CLI key -> usage, exit 2; on the page other parameters are ignored and a repeated `a` or `b` uses the value the framework gives (the last one). Reason: narrowest reading, no new error kinds.

### Q-030 · CON-015, CON-022 · Agent decision (answer 37) 2026-11-05 · applied in CON-015 v8, CON-022 v8
A log file the index lists is missing at read time with no gone mark yet (deleted between two scans), or cannot be opened (permissions).
Searched: CON-015 v7, CON-022 v7, Q-022, answer 13, change.md data sources (`files`, `log_deleted`).
Agent decision (answer 37): treated like a gone file: the run is not failed, the main session adds 0 wait; no error. Reason: narrowest reading, the same as Q-022; no marker can be read.

### Q-031 · CON-022 · Agent decision (answer 37) 2026-11-05 · applied in CON-022 v8
A ticket with two main sessions: does a stop at the end of session 1 close at a typed message in session 2?
Searched: CON-022 v7 ("a stop with no gap end after it (e.g. the session ends) adds nothing"), answers 15, 20, 24, 39, Q-016.
Agent decision (answer 37): no; gaps are found per main session and then summed. Reason: narrowest reading of the rule's own example.

### Q-032 · CON-020, CON-021 · Agent decision (answer 37) 2026-11-05 · applied in CON-020 v2, CON-021 v4
A session file with no record timestamp (empty start/end in the index, store.py first_ts/last_ts).
Searched: CON-020, CON-021, answers 7, 14, change.md ("Wall time with no records").
Agent decision (answer 37): it does not move the first or last timestamp and adds 0 active time (still a run); with no timestamp at all, wall time is 0. Reason: narrowest reading; there is no time to run from.

## EXP1-R22C DoR part 3, return round 1 (2026-11-05, business analyst)

### Q-033 · CON-022 · Agent decision (answer 37) 2026-11-05 · applied in CON-022 v9, v10
A resumed session's main file repeats records of an earlier main session of the same ticket. Per-file gaps would count the same wait twice.
Searched: CON-022 v8 ("no interval is counted twice", Q-031), Q-016, Q-031, answers 15, 20, 24, 39; store.py lines 28-29 and 383 (resume repeats earlier turns; usage deduplicated by message id + requestId); rr8-qa.md finding 1. Read-only scan of ~/.claude/projects (2026-11-05): 71 main files, 0 uuids and 0 message id + requestId keys shared between main files; no resumed copy in the local logs, so the surviving field is not confirmed by a sample.
Agent decision (answer 37): gaps are found per main-session file; a gap counts once across the ticket's main sessions, matched by its stop record's uuid, fallback message id + requestId, then the (stop timestamp, gap end timestamp) pair; of matching gaps the earliest gap end counts. Reason: narrowest reading of "no interval is counted twice"; what the figure means does not change.
v10 (same Agent decision, answer 37, 2026-11-05, QA analyst finding: qa.md Testability, rr8-qa.md finding 1): the match is an OR, not a fallback: stop records that share a uuid OR share message id + requestId are the same gap; the timestamp pair only when a stop record has neither. Reason: the same message id + requestId is the same API reply (store.py usage dedupe), so a copy with new uuids must not count twice.

## EXP1-R22C test design (2026-11-05, business analyst; td-questions.md section A)

### Q-034 · CON-022 · Agent decision (answer 37) 2026-11-05 · applied in CON-022 v11 · td A1
Two stop records in ONE main file share message id + requestId (one API reply), each with its own gap: one gap or two?
Searched: CON-022 v10 (match key: shared uuid OR shared message id + requestId; earliest gap end counts), Q-016, Q-031, Q-033, rr9-qa.md N1. Read-only log scan: 13303 replies in 71 main files, 0 with a typed message between two of their records.
Agent decision (answer 37): one gap; the match applies inside one file too; the earliest gap end counts (example: 300 s, not 900 s). Reason: narrowest reading of "no interval is counted twice"; the same reply is one stop.

### Q-035 · CON-022 · already decided (answer 15) 2026-11-05 · applied in CON-022 v11 · td A2
Which timestamp starts the gap of a rejected permission prompt?
Searched: CON-022 v10 (dismissed AskUserQuestion example starts at the 10 s turn), answers 15, 24, 39.
Already decided (answer 15: a stop is the assistant turn that waits on the person): the gap starts at the timestamp of the assistant record holding the tool_use, not at the rejection.

### Q-036 · CON-022 · log finding (answer 22) 2026-11-05 · applied in CON-022 v11 · td A3
Which record field shows an end_turn stop?
Searched: CON-022 v10 log markers, answers 15, 22. Read-only scan of 71 main files: assistant message.stop_reason end_turn 1947, tool_use 44815, stop_sequence 36, null 1.
Finding: an end_turn stop = assistant record with message.stop_reason "end_turn". Other values are not an end_turn stop (answer 15 names end_turn only).

### Q-037 · CON-022 · log finding (answer 22) + Agent decision (answer 37) 2026-11-05 · applied in CON-022 v11 · td A4
Which log marker shows hook output in a user record?
Searched: CON-022 v10 log markers, answers 22, 24, 30. Read-only scan: hook output is an `attachment` record (attachment.type "hook_success", 39) or a `system` record (subtype "stop_hook_summary", 263), never a user record; 100 user records have isMeta true and no origin (system reminders, local-command caveats, other meta text).
Agent decision (answer 37): any user record with isMeta true ends no gap, whatever its origin; hook output never ends a gap. EP-022-13's isMeta record is a valid stand-in. Reason: answer 30 (machine-written records do not end a gap); isMeta is the log's own machine-written mark.

### Q-038 · CON-018, CON-019 · Agent decision (answer 37) 2026-11-05 · applied in CON-018 v2 · td A5
Is an unpriced model listed in cost_usd.by_model with 0, or left out?
Searched: CON-017 v2, CON-018 v1, CON-019 v1, CON-026 v4 (absent = 0 in the difference), answer 8, change.md JSON shape.
Agent decision (answer 37): listed with 0; per-model cost has the same models as per-model tokens. Reason: narrowest reading of answer 8 (an unpriced message adds zero to cost).

### Q-039 · CON-012 · already decided (answer 6) 2026-11-05 · note in CON-012 (no version bump) · td A6
Default period edge for the comparison.
Searched: CON-012 v1 ("ignores the console's default period"), answer 6.
Already decided (answer 6): no period edge exists; the comparison reads no clock or period, a record of any age counts. Already in the statement; note added, meaning unchanged.

### Q-040 · CON-014 · already decided (keep the existing behaviour) 2026-11-05 · applied in CON-014 v7 · td A7
Key evidence at the same timestamp as the spawn: old key or new key?
Searched: CON-014 v6 ("key in force at the spawn call time"), CON-001, answers header, store.py:480-489, tickets.py:100-106 (latest_before: "at or before"; same timestamp -> smaller key).
Already decided (answers header: keep the existing behaviour): the newest evidence at or before the spawn timestamp, so same-instant evidence gives the new key; two keys with the same timestamp give the smaller key.

## EXP1-R22C build decisions (2026-11-05, business analyst; build-decisions.md "To the business analyst")

### Q-041 · CON-022 · Agent decision (answers 37, 38) 2026-11-05 · applied in CON-022 v12 · build D4
Edge cases of the same-gap match and of gap ends the rule did not name.
Searched: CON-022 v11 (match key, log markers, Q-033, Q-034, Q-037), answers 15, 30, 37, 38; compare.py file_gaps and _wait.
Agent decision (answer 37): message id + requestId is a key only when both are present; the (stop ts, gap end ts) pair matches only stops that both lack a uuid and an id pair; a user record with no origin whose text starts with "<task-notification" ends no gap; a gap end or a stop with no timestamp closes the stop and adds no gap. Reason: narrowest reading; answer 30 (task notifications never end a gap); no timestamp, no length. Not confirmed by a log sample.

### Q-042 · CON-017, CON-018, CON-019 · already decided (rules and answer 8) 2026-11-05 · no rule change · build D1
Is a message with all five token counts 0 left out of the model list, the cost and the unpriced count?
Searched: CON-017 v2 ("each message counts under its own model"), CON-018 v2 ("lists every model that has a message of the ticket"; an unpriced model's messages count in the unpriced number), CON-019 v1, answer 8, answers header ("keep the existing behaviour"), Q-038; queries.py aggregate (existing console counts every unpriced message, zero tokens included, as "unknown"); pricing.py message_cost (no model key -> None, whatever the tokens).
Already decided, against D1: a zero-token message counts under its model (a row of zeros), and a zero-token message whose model has no price counts in the unpriced number. The builder's reading (D1) lowers the answer-8 count and drops model rows against CON-018 v2; it is not taken. A zero-token message of a priced model is priced at 0 and is not unpriced (same as today).

### Q-043 · CON-026 · already decided (CON-026 v4, Q-018; answers 17, 34) 2026-11-05 · no rule change · build D8
A model on one side only, in the difference and on the page.
Searched: CON-026 v4, Q-018, CON-029, answers 17, 32, 34.
Already decided: the missing side counts as 0 (a real value); the page shows it as `0k` / `$0.00` (CON-029 format).

### Q-044 · CON-015 · Agent decision (answer 37) 2026-11-05 · applied in CON-015 v9 · build D2 (SA verdict)
What is "the run's last assistant turn" when one API reply is written as several records?
Searched: CON-015 v8 (final reply = last assistant turn has text or a SubagentHandback call), answers 3, 37; change.md "Build decisions" D2.
Agent decision (answer 37): consecutive assistant records with the same message.id are one turn. Reason: narrowest reading; Claude Code writes one reply as one record per content block, so a reply whose text comes before its last tool block would otherwise count as failed.

### Q-045 · CON-011 · Agent decision (answer 37), wording only 2026-11-05 · applied in CON-011 v6 · build D6 (SA verdict)
Which stderr line when some values differ and others are missing?
Searched: CON-011 v5 (one line naming what differs or is missing), answers 37, 40; change.md "Build decisions" D6.
Agent decision (answer 37): the "built with another ..." line, naming all of them (e.g. an empty index file: schema version 0 and four missing values). Reason: narrowest reading; refusal, exit 2 and nothing written stay the same, and the line still names everything that differs or is missing.

### Q-046 · CON-015 · already decided (answer 3) 2026-11-05 · note in CON-015 v9, no change of meaning · SA verdict open point
Does a sub-agent run that is still running when the comparison reads it count as failed?
Searched: CON-015 v8 ("no final reply = ... the file ends on another tool_use or a tool_result"), answer 3 ("a run that did not complete ... has no final assistant reply"), answers 13, 37; QUESTIONS.md and console.md for "running", "in progress" (no hit).
Already decided: yes, it counts as failed. A running run has not completed and its file has no final assistant reply at read time, which answer 3 names. The log has no "still running" marker, so such a run cannot be told from one that stopped at the same point; leaving it out would add a new state and change what the comparison shows, which nobody has asked for. If the product owner later wants running runs shown apart, that is a new question.

### Q-047 · CON-015 · already decided (answer 3; CON-015 definition of final reply) 2026-11-05 · applied in CON-015 v10 · code review 1 "Second look"
Is a sub-agent run failed when its last assistant turn holds a SubagentHandback call but a tool_result record follows it?
Searched: CON-015 v9 ("final reply = the run's last assistant turn has text or a SubagentHandback call"; "no final reply = neither, e.g. the file ends on another tool_use or a tool_result"), answers 3, 13, 37; Q-044, Q-046; review1.md "Second look"; console/agent_console/compare.py lines 85-86.
Already decided: not failed. Answer 3 makes a run failed when it "has no final assistant reply"; CON-015 defines the final reply by the last assistant turn, and a SubagentHandback call is one. The tool_result after it is the handback's own result, not a turn. The "e.g." only illustrates "neither" and cannot override the definition. Q-046 (still running) is unchanged: there the last turn holds no handback. Wording made unambiguous in CON-015 v10.
Read-only count (answer 22, counts only): 737 sub-agent files, 627 with a handback call, 637 handback calls followed by their own tool_result (0 errors), 331 files end on that tool_result. Read the other way, about half of the completed runs would count as failed.
Code: compare.py must change. A tool_result after a turn holding a SubagentHandback call must keep the run's state at "final reply" (today line 85-86 sets it to "result", so failed). A tool_result after any other turn stays as it is (Q-046).

### Q-048 · CON-015 · already decided (answer 3) for a denial; Agent decision (answer 37) for other errors 2026-11-05 · applied in CON-015 v11 · requirements review 12 (rr12-con015.md)
Is a sub-agent run failed when the SubagentHandback call's own tool_result has is_error true (a denial or another error)?
Searched: CON-015 v10 (Q-047 clause; permission-denial marker "no final reply follows it"), answers 3, 37; Q-044, Q-046, Q-047; docs/agents/work/EXP1-R22C/rr12-con015.md. No log scan (count known: 0 of 637 handback results had is_error).
Decision: failed. A denial is already decided by answer 3 ("ended in an API or permission error ... was denied"); for any other error, Agent decision (answer 37): failed too. Reason: an error result means the report was not handed back, so the run did not complete (answer 3); narrowest reading, one rule for every handback error. The Q-047 clause ("does not take the final reply away") covers only a non-error tool_result. No figure in the local logs moves (0 such results).
Code: in compare.py, a tool_result with is_error true after a turn holding a SubagentHandback call sets the run to failed; a non-error one keeps "final reply" (Q-047).

### Q-049 · CON-015 · Agent decision (answer 37) 2026-11-05 · applied in CON-015 v12 · build decisions B1-D1, B1-D2 (SA verdict)
Is a sub-agent run failed when its last assistant turn holds a SubagentHandback call next to other tool_uses, and those other tools' results follow?
Searched: CON-015 v11 (Q-047 and Q-048 clauses; denial marker "no final reply follows it"), answers 3, 37, 38; Q-044, Q-046, Q-047, Q-048; build-decisions.md "Builder B1 fix" and "SA on B1-D1 / B1-D2"; change.md "Build decisions B1-D1, B1-D2". No log scan.
Agent decision (answer 37): not failed. The other tools' results, in the same user record or separate records, error or not (a denial included), do not make the run failed; only the handback's own result with is_error true does (Q-048). A last turn with no handback call is unchanged (Q-046). B1-D2 is consistent, no decision needed.
Reason: a tool_result is not a turn (Q-047); the final reply is decided by the last assistant turn, which holds the handback; narrowest reading, v11 names only the handback's own result. Not a change of what the feature does: v11 already says the handback's own result decides; this closes the parallel-call case it did not name.
Code: BUG B2 (SA verdict). compare.py run_failed: when state is "reply" and the turn's handback ids are not empty, set "result" only for a result whose tool_use_id is a handback id and has is_error true; ignore other tool_results. No handback id: unchanged.

### Q-050 · CON-015 · Agent decision (answer 37) 2026-11-05 · applied in CON-015 v13 · code review 2 "Second look"
Is a last assistant turn with text next to an ordinary tool_use (not SubagentHandback) a final reply: (1) the file ends on the open tool_use; (2) its tool_result follows and the file ends?
Searched: CON-015 v12 (definition of final reply; "no final reply" example; Q-044, Q-046, Q-047, Q-049 notes), answers 3, 13, 22, 37, 38, 42; QUESTIONS.md Q-044, Q-046, Q-047; review2.md "Second look"; compare.py run_failed (v12 code: case 1 not failed, case 2 failed).
Agent decision (answer 37): not a final reply in both cases, so the run is failed. Reason: narrowest reading of answer 3 ("did not complete ... no final assistant reply"): a turn that calls a tool waits for its result, so its text is not the final reply; answer 13 (do not narrow) and Q-046 (a file ending on an open tool_use or a tool_result is failed) keep such a run failed. Q-047 unchanged (a tool_result is not a turn; the turn decides). Q-044 unchanged (one turn per message.id). Q-049 unchanged (a turn with a SubagentHandback call is a final reply, whatever sits next to it).
Count (answer 22, read-only, 2026-11-05, counts only): 756 sub-agent files, 32 failed by the v12 code; case 1: 0 files; case 2: 1 file. This reading: 32 failed; the other reading: 31. Not blocking: the figure moves by 1 run.
Code: compare.py run_failed must judge the merged turn as "reply" only when it holds a SubagentHandback call, or has non-empty text and no tool_use other than SubagentHandback. Case 1 changes (today "reply", must be failed); case 2 stays failed. Handback rules (Q-047, Q-048, Q-049) unchanged.
Wording (requirements review 14, rr14-con015.md, 2026-11-05, already decided by Q-049): CON-015 v14 limits this ruling to a last turn with no SubagentHandback call: "a last turn with no SubagentHandback call that has text next to another tool_use is not a final reply, whether the file ends on that open tool_use or on its tool_result"; the final-reply definition says the same. Meaning unchanged.

### Q-051 · CON-022 · already decided (answer 30) 2026-11-05 · applied in CON-022 v13, wording only · code review 2 "Second look"
A user record whose origin is an object with no kind (or is not an object): origin marker or not?
Searched: CON-022 v12 (log markers: "a user record with no origin"), answers 22, 30, 37; Q-037, Q-041; compare.py _typed.
Already decided (answer 30, "in older logs with no marker"): no kind is no marker, so the no-origin test applies (not isMeta, not a tool result, not local command output, the interrupt marker or a task notification = typed). The v12 code (_typed) already does this.
Count (answer 22, read-only, 2026-11-05, 71 main files, counts only): 1599 user records with an origin field (human 852, peer 504, task-notification 243); 0 with no kind or a non-object origin. No figure moves.
Code: no change. A test for the case is still missing (review2.md: "no rule, no test").

### Q-052 · CON-022 · already decided (answers 24, 30) + Agent decision (answer 37) 2026-11-05 · applied in CON-022 v14 · code review 3 "Second look"
A user record with no origin marker and no isMeta that Claude Code wrote itself, e.g. the compact summary after a context compaction: does it end a wait gap?
Searched: CON-022 v13 (log markers, Q-037, Q-041, Q-051), answers 22, 24, 30, 37, 42; QUESTIONS.md Q-037, Q-041, Q-051; review3.md "Second look".
Already decided (answers 24, 30: "other machine-written user records do not end it"): a compact summary ends no gap. Marker: isCompactSummary true. Agent decision (answer 37): a user record with isVisibleInTranscriptOnly true ends no gap even without isCompactSummary. Reason: narrowest reading, the log marks it as shown in the transcript only, not sent by the person; the two flags always come together locally.
Count (answer 22, read-only, 2026-11-05, 71 main files, field names and counts only): 68 user records with no origin marker, not isMeta, not a tool result: 25 with isCompactSummary true and isVisibleInTranscriptOnly true (always both); slash commands 16, local command output 16, plain text 11. Under v13 the 25 counted as typed. Not blocking: it is what answers 24 and 30 already say; it does not change what the feature does.
Code: compare.py _typed, in the no-origin branch, must return "not typed" when the record has isCompactSummary true or isVisibleInTranscriptOnly true (check `is True`), before the text tests. The origin.kind "human" branch is unchanged. Test: a no-origin, not-isMeta user record with isCompactSummary true and plain text after an end_turn stop ends no gap; the same with isVisibleInTranscriptOnly true only; the next typed message closes the gap from that stop.

### Q-053 · CON-014, CON-003 · Agent decision (answer 37) 2026-11-05 · applied as notes on CON-014 v7 and CON-003 v1, no version change · code review 3 finding 1
A sub-agent file whose meta is missing, unreadable or has no toolUseId: is its spawn a "spawn with no run file" (CON-014), and which role does the run take (CON-003)?
Searched: CON-014 v7 (statement, notes, history), CON-003 v1, CON-015, CON-016; answers 18, 22, 25, 31, 33, 35, 37, 42; QUESTIONS.md "EXP1-R22C build decisions"; change.md "Spawn-to-run-file link"; build-decisions.md last section.
Agent decision (answer 37): the spawn has a run file. Link: (1) meta toolUseId = spawn id; (2) only for a file with no meta toolUseId: files in (first record time, run id) order pair one-to-one with the earliest not-yet-linked Agent/Task spawn of the same session whose window holds the file's first record (spawn call <= first record <= result); (3) no pair: spawn with no run file. A paired run is failed only by its run file (CON-015); its role is the spawn's subagent_type when the meta has none (CON-003). Reason: narrowest reading of CON-014 (it counts a spawn with no run file only; the meta is not the only evidence of the file). Not chosen: the parent's toolUseResult.agentId (needs a parser and schema change, out of scope, and misses error results).
Count (answer 22, read-only, counts only): 765 sub-agent files, 742 with toolUseId, 23 without; 742 of 742 start inside their spawn window; simulation with every meta removed: 742 of 742 right (latest-spawn pairing: 157 wrong); today's 23 files: 0 pairings; 12 spawns with no file stay counted. Not blocking: no figure moves today; the feature does what CON-014 already says.
Code: compare.py _Ctx.spawns (fallback pairing once per _Ctx, fb_role) and _ticket roles; no schema change. Tests: test_spawn_with_run_file_and_no_meta_counts_once, test_unlinked_file_does_not_take_a_denied_spawn (change.md).

### Q-054 · CON-014 · Agent decision B5-D1 (answer 37) 2026-11-05 · applied as a note on CON-014 v7, no version change · code review 4 finding 1 (extra loop, answer 46)
A spawn whose records are copied (a resumed file repeats them): which call time and which result time make the fallback window of CON-014?
Searched: CON-014 v7 (statement, notes, history), Q-053; answers 31, 33, 35, 37, 46; review4.md finding 1; compare.py:276-278, :290.
Agent decision (answer 37, builder decision B5-D1): the fallback window uses the call time of the earliest copy of the spawn and the result time of the earliest copy that has one; a spawn with no result time is never paired. Reason: the earliest copy that has a result is the same call; a spawn with no result is not counted by CON-014 anyway (answers 31, 33, 35).
Not blocking: it does not change what the feature does; no figure moves (0 pairings today, Q-053). Code: no change.

### Q-055 · CON-010, CON-027 · already decided (answer 47) + Agent decision (answer 37, wording only) 2026-11-05 · applied in CON-010 v3, note on CON-027 v6 · hostile verify HV-1
How does /compare answer while the console re-scans (not the first index)? HV-1: a known key got 404 and mixed half-scan figures during a later rescan.
Searched: CON-010 v2, CON-027 v6, CON-034 v4, CON-011 (notes, history); Q-024; answers 37, 40, 47; hostile.md HV-1; change.md B2 error texts.
already decided (answer 47, option A): during any scan the page answers HTTP 503 with one message; never a mix of old and new tables, never a false "unknown key"; the CLI waits for its own scan as before.
Agent decision (answer 37, wording only): one text for every scan, the first index included: "The console is updating its index. Reload this page later." The first-index text "The console is building its first index. Reload this page later." is dropped. Reason: answer 47 asks for "the same one message" and quotes this text; two texts would not be one message.
Not blocking: order 422 -> 503 -> 404 -> 200 unchanged (CON-034, CON-010, CON-027). Change.md B2 503 row and the 503 tests follow the new text; a later-scan 503 test is added (HV-P20). Open for the system analyst: how the page detects a scan in progress, also a CLI refresh in another process.

### Q-056 · CON-010, CON-011 · Agent decision (answer 37) 2026-11-05 · applied as a note on CON-010 v3, no version change · change.md "Scan in progress"
How does /compare answer after a scan that ended in an error, or after a CLI killed mid-scan?
Searched: CON-010 v3 (statement, notes, history), CON-011, CON-027; Q-024, Q-055; answers 37, 40, 47; change.md "Scan in progress"; server.py loop (INGEST_EVERY_S = 30).
Agent decision (answer 37): such a scan counts as not finished; the index holds mixed rows, so the page answers 503 until the next successful scan of any process finishes. Markers of dead processes are cleared at the end of that next scan. The CLI does not check other processes' markers; it compares right after its own scan (CON-011). Reason: narrowest reading of CON-010 v3 "never mixed figures".
Not blocking: it does not change what the feature does. CON-010 v3 already answers 503 while the index is not settled; the console scans every 30 s, so the 503 after an aborted scan lasts about one loop while the console runs; without the console running the page is not served. A scan that keeps failing keeps 503, which is the rule's safe side (mixed data). Residual: a reused pid of a dead CLI keeps 503 until that process ends (rare, safe side).

### Q-057 · CON-011, CON-014, CON-015, CON-022, CON-027, CON-033, CON-035 · Agent decisions BD1-BD5 (answer 37) 2026-11-05 · applied in CON-011 v7, CON-033 v2, CON-035 v2; notes on CON-014 v7, CON-015 v14, CON-022 v14, CON-027 v6 · builder decisions, security fix round (SEC-1..SEC-4, HV-2)
Which forms did the builder pick for the security and hostile fixes where no rule covered them?
Searched: CON-011 v6, CON-014 v7, CON-015 v14, CON-022 v14, CON-027 v6, CON-033 v1, CON-035 v1 (statements, notes, history), Q-027, Q-045, Q-055; answers 23, 37, 38, 40, 47; security.md SEC-1..SEC-4, INFO-1; hostile.md HV-2; build-decisions.md last section; compare_cli.py, compare_format.safe, compare_page.error_page, store.index_check (read for the exact texts).
- BD1 (CON-035 v2, CON-027 note): control characters in CLI text and stderr are shown as `\xNN`, lowercase hex, for C0 (tab and newline included, newline = `\x0a`), DEL and C1. Agent decision: narrowest reading of "shown as text" (CON-035) and "one line" (CON-027); no information lost. Page and JSON unchanged.
- BD2 (CON-011 v7): symlink refusal line "compare: refused: the index at <path> is a symbolic link (nothing written)", exit 2, nothing created. Agent decision: the same form as the other refusals; any symlink is refused.
- BD3 (CON-033 v2): 500 page text "The comparison could not be built. Try again later.", no detail, HTML, the same security headers. Agent decision: the same one-message form as the 503/404 pages; no detail keeps log text off the page (CON-035, answer 23).
- BD4 (notes on CON-015, CON-022, CON-014): a non-string id, uuid, tool_use id or timestamp is read as absent; a too deeply nested line is skipped like an invalid line; not an error. Agent decision: the rules already read an absent field this way (CON-022 no-timestamp edge case). Spawns come from the index, so CON-014 counts do not move; the ingest's own abort on such lines is pre-existing (INFO-1, backlog).
- BD5 (CON-011 v7): the index check opens immutable only when no -wal exists, plain read-only when one exists. Agent decision: "nothing written" = no new file and no index data changed; an immutable read beside a -wal would ignore the newest rows. Residual: with a -wal present SQLite may touch the existing -shm file (no index data).
Not blocking: none changes what the feature does, its scope or the budget; each fixes a crash, a leak or a text form inside rules that already exist (exit 1 one line, exit 2 refusal with nothing written, page headers, text not markup).
Open for test design: CON-033 v2 has no test that forces the 500 branch (test_sec_1_page_* accepts any status); add one that checks 500, the BD3 text, HTML and the five headers.

### Q-058 · CON-010, CON-011 · already decided (answer 48) + Agent decisions (answers 37, 38) 2026-11-05 · notes on CON-010 v3 and CON-011 v7, no version change · security re-check NEW-1..NEW-3, code review 6 finding 4 (extra loop, answer 48)
How are the security re-check findings NEW-1, NEW-2 and NEW-3 handled?
Searched: CON-010 v3, CON-011 v7 (statements, notes, history); Q-055, Q-056, Q-057 (BD5); answers 37, 38, 40, 47, 48; security.md re-check section (NEW-1..NEW-4, INFO-1); test_compare_page.py (test names).
- NEW-1, already decided (answer 48): known limit, outside this ticket. The existing ingest stops on one malformed log line (INFO-1, pre-existing), so its scan marker stays and /compare stays at 503 until the line is removed. parser.py and the store's ingest are not changed; backlog. Recorded in the CON-010 v3 notes and history.
- NEW-2, Agent decision (answers 37, 38): a scan marker whose pid cannot be parsed, or whose pid is alive but whose start time is older than 1 hour, counts as dead and is cleared at the end of the next successful scan. Reason: narrowest reading of Q-056 "markers of dead processes are cleared"; a reused pid otherwise kept 503 for good. CON-010 notes.
- NEW-3, Agent decision (answers 37, 38): a refusal creates no file even when a -wal exists without a -shm; the check refuses or reads without creating -shm. Reason: narrowest reading of "nothing written" (answer 40, SEC-2). CON-011 notes.
- Code review 6 finding 4: the CON-010 v3 tests field now lists test_hv_p20_a_later_scan_answers_only_503_or_the_settled_200 and test_dt_010_06..09 (exact names).
Not blocking: none changes what the feature does, its scope or the budget (answer 48 sets this loop). Open for test design: NEW-2 and NEW-3 tests are added by the automation engineer in this loop (answer 48); list them in the tests fields of CON-010 and CON-011 once they exist.

### Q-059 · CON-010, CON-011, CON-015 · already decided (Q-058, CON-015 statement) + Agent decisions (answers 37, 38) 2026-11-05 · notes on CON-010 v3, CON-011 v7, CON-015 v14, no version change; tests fields of CON-010, CON-011, CON-015, CON-022, CON-027, CON-035 · builder decisions, extra loop 5 (L5-D1..L5-D4)
How are the builder's decisions L5-D1..L5-D4 from extra loop 5 handled?
Searched: CON-010 v3, CON-011 v7, CON-015 v14 (statements, notes, history); Q-048, Q-049, Q-056, Q-057 (BD4, BD5), Q-058 (NEW-2, NEW-3); answers 37, 38, 40, 48; build-decisions.md "Builder extra loop 5"; `# rule:` markers in console/tests/.
- L5-D1, Agent decision (answers 37, 38): a scan marker whose start time cannot be read is not stale by age; the pid decides (Q-058). Reason: narrowest reading of Q-058, which counts a live marker as dead only when its time is shown to be older than 1 hour. The console always writes a readable UTC time. CON-010 notes.
- L5-D2, Agent decision (answers 37, 38): a marker time with no time zone is UTC. Reason: the console writes the marker time in UTC. CON-010 notes.
- L5-D3, already decided (Q-058 NEW-3: the form is the builder's choice, the outcome is no new file) + Agent decision for the copy: with a -wal and no -shm, the check reads a copy in a system temporary directory, deleted when the check ends; no -shm beside the index, newest rows seen. "Creates no file" = no file left behind. Residual: a CLI killed during the check may leave its temporary directory in the system temp folder, never in the console home. CON-011 notes.
- L5-D4, already decided (CON-015 statement, "a turn that holds a SubagentHandback call"; Q-048, Q-049; Q-057 BD4): the handback-error check keys on a handback call in the last turn, not on a non-empty list of handback ids; needed once non-string ids are read as absent. CON-015 notes.
- Tests fields: NEW-2 (CON-010), NEW-3, BD4 and symlink-to-valid-index (CON-011), BD4 run_failed (CON-015), BD4 file_gaps, CLI and page (CON-022), argparse and exact HV-2 escapes (CON-027, CON-035), exact SEC-3 and safe() escapes (CON-035).
Not blocking: none changes what the feature does, its scope or the budget; each fixes an edge inside a rule that already exists (Q-056, Q-058, CON-015 v14).
Open for the builder (not a rule question): test_dt_010_08 uses a fixed marker time now older than 1 hour, so it fails against the NEW-2 age bound (test defect, build-decisions.md loop 5); the CON-010 v3 rule is unchanged.
