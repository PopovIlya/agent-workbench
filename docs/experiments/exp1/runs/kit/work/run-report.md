# Run report: EXP1-KITC (console, comparison report)

Path: `docs/agents/work/EXP1-KITC/run-report.md`. Not committed. Written by the main session at the end of the block. Branch `exp1/kit`, base 0891a04. Commits: 76a996c (map), 2fd75c2 (tests), 76b5322 (code). Not pushed.

## Timeline
Durations and tokens are those the harness reported for each role (sub-agent tokens as given). Start times were not recorded: UNVERIFIED. Model: only the analyst file states `model: sonnet`; the others were not read: UNVERIFIED.

| Role | Step | Duration | Tokens | Verdict |
|---|---|---|---|---|
| kit-analyst | as-is | 91 s | 71,468 | PASS |
| kit-analyst | delta | 68 s | 26,611 | QUESTIONS |
| kit-analyst | delta round 2 (answers 19-22) | 63 s | 38,171 | PASS |
| kit-test-designer | tests | 535 s | 94,061 | PASS |
| kit-builder | code | 366 s | 122,569 | FAIL (1 wrong test) |
| kit-test-designer | helper fix (extra loop, item 38) | 21 s | 12,142 | PASS |
| kit-builder | code re-run | 73 s | 15,683 | PASS |
| kit-reviewer | round 1 | 107 s | 35,991 | FAIL |
| kit-security | round 1 | 22 s | 20,055 | PASS (void) |
| kit-builder | tests, return round 1 | 125 s | 43,829 | PASS |
| kit-builder | code, return round 1 | 58 s | 13,667 | PASS |
| kit-reviewer | round 2 | 200 s | 24,211 | FAIL |
| kit-security | round 2 | 23 s | 17,756 | PASS (void) |
| kit-builder | tests, return round 2 | 100 s | 20,892 | PASS |
| kit-reviewer | round 3 | 160 s | 16,740 | FAIL |
| kit-security | round 3 | 19 s | 9,726 | PASS (no report file) |
| kit-analyst | delta round 3 (answers 24-38) | about 85 s (UNVERIFIED) | 43,807 | PASS |
| kit-test-designer | tests, re-plan | 241 s | 71,496 | PASS |
| kit-builder | code, re-plan | 71 s | 18,238 | PASS |
| kit-reviewer | re-plan round 1 | 170 s | 32,838 | PASS |
| kit-security | re-plan round 1 | 14 s | 18,867 | PASS |
| kit-verifier | final | 87 s | 20,172 | FAIL (strict coverage gate, see below) |

## Stops, failures, return rounds and questions
| # | What | Cause | Resolution |
|---|---|---|---|
| 1 | Stop after delta analyst (QUESTIONS) | 3 open questions (CON-033, 048, 027) not covered by the brief or answers 1-18 | Answered in answers.md 19-23; analyst re-run, PASS |
| 2 | Builder FAIL | `Sess.spawn(refuse=...)` in the test helper gave two refused spawns the same tool id; the index keeps one row per id; product was right, test was wrong | answers.md 38: extra loop, test-designer fixed the helper only, builder re-run PASS. Not counted against the 2 rounds (item 38) |
| 3 | Return round 1 (reviewer FAIL F1-F8) | Missing tests for CON-036, 052, no-argument start, 7200 s, minus-zero, handback, per-model unpriced; handback goes beyond CON-035; `len > 60` guard has no rule | Builder tests, then builder code (handback special case and the guard removed) |
| 4 | Return round 2 (reviewer FAIL F9, F10) | `end_turn` with no text and error-clearing order untested | Builder tests only |
| 5 | Stop: reviewer FAIL after round 2 (F11, F12) | Denial detection never decided any test; synthetic skip untested; CON-035 wording lagged | Human chose option 3: re-plan with answers 24-36 |
| 6 | Re-plan (human option 3, answers 44) | Answers 24-38 arrived after the rules and tests were written | Analyst delta round 3, human stop (item 44), test-designer, builder, reviewer, security. Fresh budget of 2 return rounds recorded (item 44); used 0 of 2 |
| 7 | Verifier FAIL | `rule_coverage.py --strict` exits 1 (see below) | answers.md 45: accepted as a known condition outside this ticket |

Questions and rulings used: answers.md 19-23, 24-36, 37 (Agent decisions), 38, 44, 45. Cross-session messages from the ops session were each checked against answers.md before I acted.

Agent decisions recorded in the rules (item 37): final reply is `end_turn` only; the run's final state decides an API error; no key length limit; fixed JSON shape; unknown key 404 on the page; exact 60 s gap counts; machine-record detection when there is no origin.

## Strict coverage gate (problem of the kit tool, not of this work)
`python3 <workbench>/kit/tools/rule_coverage.py . --strict --scope EXP1-KITC` exits 1. The only findings are four unknown rule IDs, AUDIT-001, AUDIT-002, AUDIT-003 and AUDIT-999, all in `kit/tests/test_rule_coverage.py` (fixture strings of the tool's own tests). The tool scans the whole repo, so its own tests trip its strict mode. On a /tmp copy without `kit/tests` the same command exits 0 with no uncovered rule (verifier). UNVERIFIED: whether the base commit also gives exit 1 (the map is untracked there). The kit was not edited (item 45). Proposed fix, text only: have the tool skip `kit/tests`, or mark those fixtures as not rule markers.

## Permission breaches
Checked `git status` after every role against its "May change" list: `none`.
Not breaches but noted:
- kit-security round 3 did not write `security-3.md`: it said its tool rules forbade writing reports; its verdict came in the reply only. Round 4 wrote `security-4.md`.
- The CLI `compare` calls `Store().ingest()`, which writes the index in `AGENT_CONSOLE_HOME` (disclosed by the builder; reviewer accepted; answer 40 covers the R22 arm only and was not applied here).
- I ran `rule_coverage.py --write-tests` before the verifier, not at closing. It only touched `docs/requirements/console.md` `tests:` fields.

## Unclear or contradictory places in role files or the playbook
| Quote (`path:line`) | Problem | Proposed fix (text only) |
|---|---|---|
| PLAYBOOK.md §3 "`FAIL` from reviewer or security: send the report path(s) back to the builder" | No rule for a builder `FAIL`, or for an extra loop caused by a wrong test | Add: a builder FAIL caused by a test defect goes to the test-designer, then back to the builder, outside the return-round count |
| PLAYBOOK.md §3 vs reviewer reports ("Return to: test-designer / analyst") | Reviewer routes findings to roles the playbook does not use on a return | Let the reviewer name only `tests` or `code`; map text findings go to the analyst by the main session |
| PLAYBOOK.md §3 "At most 2 return rounds" | No rule for a re-plan after new answers | State that a human-ordered re-plan starts a new budget |
| PLAYBOOK.md §6.1 vs §1 verifier | `--write-tests` runs at closing, but the verifier needs the `tests:` fields before it runs strict | Move `--write-tests` before the verifier |
| kit-security role file | Role could not write its report in one run although `Write` is listed | Check the tool list or the "May change" line |
| kit/tools/rule_coverage.py strict mode | Scans `kit/tests` fixture markers | See above |

## Console scores and flags for EXP1-KITC
As read from the running console (read-only GET, `/api/ctq/tickets`), at the end of the run; the period and scope are the console's defaults:
- cost 7.31 (main 2.68, sub-agents 4.63); runs 22; roles 6; main sessions 1
- working time 3,178 s; waiting 0 s; calendar 10,963 s
- tests 38 runs, 0 failed; S score 0.0 over 12 evaluated
- flags: 16. UNVERIFIED: which flags; the ticket endpoint did not list them.
The numbers cover the session as it stood when queried and will grow.

## Comparison with an earlier run
Not available in this run (no earlier run of EXP1-KITC read).

## Final state
- Map: 55 rules (26 observed, 29 new, all still `new`; none set to `confirmed`; item 44 says the map is confirmed, status changes left to the human). Tests: `console/tests/test_compare.py`, 108+ cases. Code: `compare.py` (new), `server.py`, `__main__.py`.
- Gates (verifier): ruff clean; console 554 passed (baseline 445); install tools and kit 49 passed; strict coverage exit 1 (above).
- Reviewer re-plan round 1: PASS (one optional finding F13: no test for a denied-wording `is_error` result whose `toolUseResult` is not a string). Security re-plan round 1: PASS, two low notes (CLI echoes keys raw; 404 vs 200 reveals whether a key exists).

## Handback risk (kept as the verifier wrote it)
Check 6 of the L3 list: "Check that the kit runs that end with a SubagentHandback are not shown as failed". CON-035 now says a final reply is `end_turn` only, and a handback call is not one. UNVERIFIED on live logs: kit sub-agent runs that end on a handback call may be counted as failed. Wait time and denial detection were tested only on fixtures, not on real logs.

## L3 checklist (for the human), as the verifier wrote it
Use a throwaway console, not your running one. Replace K1 and K2 with two real ticket keys that have sessions under `~/.claude/projects/`; K0 is a key that does not exist.

| # | Action (one) | Expected result |
|---|---|---|
| 1 | In `console/`, run `AGENT_CONSOLE_PORT=8791 AGENT_CONSOLE_HOME=/tmp/awb-l3 make start` (or the equivalent `python -m agent_console` with those variables) | The console starts; `http://127.0.0.1:8791/health` answers ok |
| 2 | Open `http://127.0.0.1:8791/compare?a=K1&b=K2` | Two ticket columns plus a difference column; tokens rounded to thousands, dollars to cents, time to minutes |
| 3 | Compare the total cost of K1 on the page with the same ticket's cost on the existing ticket page | The numbers agree |
| 4 | Look at the role-run rows for K1 | Total, failed and repeat-round counts look right for what you remember of that ticket |
| 5 | Look at the wait-time row for a ticket with long pauses for you | The value is plausible; gaps under 60 s do not add up |
| 6 | Check that the kit runs that end with a SubagentHandback are not shown as failed | Failed count does not include normally finished sub-agent runs |
| 7 | Open `http://127.0.0.1:8791/compare?a=K1&b=K0` | A clear error about the unknown key (HTTP 404) |
| 8 | Open a ticket that has no main session as `a` | The row shows "no main session", not 0 |
| 9 | In `console/`, run `.venv/bin/python -m agent_console compare K1 K2` | A text table with the same numbers as the page |
| 10 | Run `.venv/bin/python -m agent_console compare K1 K2 --json` twice and diff the outputs | Identical output, sorted keys, raw (unrounded) values |
| 11 | Run `.venv/bin/python -m agent_console compare K1 K0; echo $?` | Error message and exit code 2 |
| 12 | Run `.venv/bin/python -m agent_console` with no arguments and stop it | It still starts the server as before |

## Open items
- Waiting for the human's check and "push". No push was done.
- Rule statuses are still `new`; only the human changes them to `confirmed`.
- UNVERIFIED: behaviour on live logs (handbacks, wait time, denial detection, a non-error spawn without a run file).
