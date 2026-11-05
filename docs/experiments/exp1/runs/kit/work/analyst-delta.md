PASS

# analyst report: EXP1-KITC (delta, round 3)

Path: `docs/agents/work/EXP1-KITC/analyst-delta.md`

## Summary
Rules CON-027..CON-052 updated for answers 24-38, the builder's Agent decisions and reviewer items F11, F12; new rules CON-053, 054, 055. All status `new`, scope EXP1-KITC. No open question (item 37 decisions are written into the rules and listed in QUESTIONS.md).

## Rules changed since the tests were written (for the test step)
| ID | Change | Source |
|---|---|---|
| CON-027 | Missing or wrong keys refer to CON-054; no-argument start verified by a check, not a test | a27, a38 |
| CON-032 | Unknown key: page HTTP 404 (Agent decision), CLI exit 2; a refused spawn naming the key makes it known | a37 |
| CON-035 | Final state decides (later normal reply clears an earlier API error or denial; API error after a normal reply fails). Final reply = last normal assistant with end_turn and non-blank text; handback is NOT a final reply; missing stop_reason = not end_turn; in-progress run = failed; missing log file = not failed. F12: `<synthetic>` records that are not API errors are skipped (neither set nor clear). F11: see below | a3, a37, F11, F12 |
| CON-037 | Spawns that failed before start (denied, type not found, worktree error): run total, failed, repeat order (a25, a31). No result and no run file: not counted (a33). Non-error result without run file: counts as a run, not failed (a35). Each refused spawn needs its own id (a38) | a25, 31, 33, 35, 38 |
| CON-038 | No model id counts under `unknown` | a29 |
| CON-043 | Gap end: only typed text (incl. slash command) or the AskUserQuestion answer; machine records, tool results, interrupt marker do not; rejected prompt ends at next typed message; no-origin records rule; exactly 60 s counts; over 2 h is strictly > 7200 s | a24, a30, a37 |
| CON-044 | Rejected prompt gap pointer | a24, a30 |
| CON-050 | Ratio 2 decimals; .5 tie away from zero; sign kept; negative rounding to zero shown without minus (`0k`, `0 min`, `$0.00`); `12k`; `12 min`, hours stay in minutes | a26, a32, a34, a36 |
| CON-051 | JSON shape fixed (Agent decision) | a37 |
| CON-053 (new) | Spawn counting summary; non-error spawn without run file | a35 |
| CON-054 (new) | Missing a or b: page 422 one message, no form/swap/link; CLI usage, exit 2; no key length limit | a27, a37 |
| CON-055 (new) | Keys by existing rules, no case folding | a28 |
Unchanged: CON-028..031, 033, 034, 036, 039..042, 045..049, 052.

## Agent decisions recorded as such (answer 37)
Final state decides the run's error state; final reply is end_turn only (handback is not one, CON-035); no key length limit (CON-054); JSON shape (CON-051); unknown key 404 on the page (CON-032); exact 60 s gap counts (CON-043); machine-record detection when no origin (CON-043).

## CONFLICT / UNVERIFIED (for the lead)
- CONFLICT: F11 asks that a denied tool result with end_turn counts as failed. In compare.py:82 every later normal assistant record resets the flag, so a denial followed by the final end_turn reply does not fail the run (this is why mutation N8 survived). The rule is worded as the code reads it: the denial counts when it is the latest event (the F11 test fixture must put the denied result after the last normal assistant record). If the person wants any denial anywhere in the run to fail it, that changes the code and answer 3 "ended in" reading; I did not decide it. Not filed as a question (edge case, item 37); the lead may choose.
- CONFLICT: CON-053/CON-037 vs code: compare.py:147-151 counts only error spawns with no run file; a non-error spawn with no run file (answer 35) is not read. UNVERIFIED whether such a spawn can appear in the index. The test step should add a case; the code step may need a change.
- UNVERIFIED: denial wording beyond the two prefixes; full set of spawn refusal wordings.
- The builder-code.md note about SubagentHandback counting as a final reply is out of date (removed in code round 1); CON-035 follows the code and the lead's instruction.

## Questions filed
None.

## Size
L - 29 new rules, unchanged from before (route, CLI, raw-log readers, per-model aggregation).
About 8 files touched; risk sits in the raw-log reading and the two conflicts above.

## Security triggers
- /compare route and CLI (CON-027, 032, 054): new or changed endpoints - user-supplied keys a and b; 422/404 responses; CLI entry.
- Failed-run, spawn and wait detection (CON-035, 036, 037, 043, 044): personal data and logging of request or response data - raw session content is read; none may be output (answer 23).
- Others: none.
