# Status: EXP1-KITC

Current step: closed, waiting for the human's check and push
Next: STOP, human check and push

| # | Step | Role | Verdict | Start | End | Summary (one line) |
|---|---|---|---|---|---|---|
| 1 | as-is | kit-analyst | PASS | | | 24 observed rules in docs/requirements/console.md; size L; no /compare, no CLI args |
| 2 | delta | kit-analyst | QUESTIONS | | | 26 new rules, 3 open questions; answered by answers.md 19-23 |
| 2b | delta round 2 | kit-analyst | PASS | | | rules updated from answers 19-22; no open questions; size L accepted (answer 23) |
| 3 | tests | kit-test-designer | PASS | | | console/tests/test_compare.py, 47 cases red for the right reason; gaps: CON-052, no-arg start, JSON field names guessed |
| 4 | code | kit-builder | FAIL (extra loop re-run: PASS, 47/47, console 492, install+kit 49, ruff clean; no-arg start checked by a throwaway instance) | | | 46/47 green; test_denied_spawn_counts_in_run_total_and_failed (CON-037) red: test reuses tool_use id tu-SAa2 for two refused spawns; builder judged the test wrong |

## Skipped roles
| Role | Reason |
|---|---|

## Return rounds
Builder ↔ reviewer/security: 2 of 2 used before the re-plan; re-plan budget 0 of 2 (item 44)

## Open items
- Permission check after step 1: only docs/requirements/ changed (within May change).
- Permission check after step 2: no change beyond docs/requirements/ (untracked).
- QUESTIONS: CON-033 (main session as role run?), CON-048 (several main sessions summed?), CON-027 (server-rendered page, same Host/header rules?). Neither brief nor answers.md settles them.
- Permission check after step 3: only console/tests/test_compare.py added.
- Map statuses: no rule set to confirmed (answer 23 says map confirmed; per playbook only the human changes status).
- Security run: triggers listed; answer 23 asks for it.
- Extra loop (answers.md item 38, not a reviewer/security return round, budget stays 0 of 2): test-designer fixes only the refused-spawn tool ids in the Sess.spawn helper; then builder code re-run. ⚠️ Deviation from plan: playbook has no rule for a builder FAIL.
- Builder decisions the rules do not cover (JSON field names, 404 for unknown key, SubagentHandback as final reply): item 37, Agent decision.
- OPEN: answers.md items 24-36 were added after the rules/tests were written (answers 1-23). Not yet applied to rules or tests; reviewer/verifier may find gaps against them. Raised with the human.
- Extra loop step 3b: test-designer PASS, helper only (self.refused counter); test_compare.py 47 passed per its report. Next: builder code re-run (extra loop).
| 5a | review | kit-reviewer | FAIL | | | F1-F8: missing tests CON-036, CON-052, no-arg start, 7200 s boundary, -0 rounding, handback branch, per-model unpriced; handback goes beyond CON-035; len>60 guard has no rule |
| 5b | security | kit-security | PASS (void) | | | no high/medium; 2 low notes |
- Return round 1 of 2 started: builder tests (reviewer-1.md), then builder code. Both reviewer and security re-run after (security PASS is void after any change).
| 6a | tests r1 | kit-builder | PASS | | | 55 tests, 1 red on purpose (handback not a final reply, CON-035); only test_compare.py changed |
- ⚠️ Risk: narrowing CON-035 counts runs that end on a SubagentHandback call as failed on live kit logs (UNVERIFIED). Raised with the human.
| 6b | code r1 | kit-builder | PASS | | | handback special case and len>60 guard removed |
- Earlier PASS of reviewer (FAIL) and security (PASS) are void after the change: PASS (void). Re-running both on the new diff (round 1 of 2).
| 7a | review r2 | kit-reviewer | FAIL | | | F9 (end_turn with no text untested), F10 (later normal reply clears an earlier API error: untested/unspecified) |
| 7b | security r2 | kit-security | PASS (void) | | | no high/medium; unbounded key safe |
- Return round 2 of 2 started: builder tests (F9, F10). A further FAIL = STOP.
| 8a | tests r2 | kit-builder | PASS | | | 5 new cases for F9, F10; 60 pass; N2 and N3 killed; no product code change |
- Tests changed after security r2 PASS: PASS (void). Re-running reviewer and security (after return round 2).
| 9b | security r3 | kit-security | PASS | | | no high/medium; same 2 low notes (CLI echoes keys raw; 404 vs 200 reveals key existence). Report file NOT written: the role said its tool rules forbade writing it; verdict came in the reply only. For the run report. |
| 9a | review r3 | kit-reviewer | FAIL | | | F11: denial detection (compare.py:89, N8) never decides in any test; F12: N10 synthetic-model skip, near-equivalent; CON-035 wording lags tests |
- STOP: second return round ended in another FAIL (playbook 3). Verifier not run. No run-report written.
- ⚠️ Deviation from plan: human chose option 3 (apply answers 24-36). Re-plan: analyst delta (answers 24-38, CON-035 wording, F11/F12 reviewer items) -> STOP for the human -> test changes -> code -> reviewer + security -> verifier. All earlier PASS marked void by the coming changes.
| 10 | delta r3 | kit-analyst | PASS | | | CON-027..052 updated for answers 24-38; new CON-053..055; no questions; 2 CONFLICTs for the human (denial anywhere vs latest event; non-error spawn without run file not read by code) |
- Permission check after step 10: only docs/requirements/ changed.
- Human ruling answers.md item 44: map confirmed (no rule status changed by me), size L, conflict 1 keep wording (denial fails only if no normal final reply follows), conflict 2 non-error spawn without run file counts as a run, not failed. Re-plan has a fresh budget of 2 return rounds (to note in run report). Earlier PASS verdicts are void after the new diff.
| 11 | tests re-plan | kit-test-designer | PASS | | | 54 tests added, 108 pass, 1 red for the right reason (non-error spawn without run file, CON-037/053); mutation check done |
| 12 | code re-plan | kit-builder | PASS | | | non-error spawn without run file now counted |
- All earlier reviewer/security verdicts are PASS (void) / FAIL (void) after the re-plan diff. Re-running both (re-plan round budget 0 of 2).
| 13a | review re-plan | kit-reviewer | PASS | | | reviewer-4.md |
| 13b | security re-plan | kit-security | PASS | | | security-4.md; same 2 low notes |
| 14 | verify | kit-verifier | FAIL | | | ruff clean; console 554; install+kit 49; strict rule coverage exit 1 only from AUDIT-001/002/003/999 fixture IDs in kit/tests (not changed by this ticket); exit 0 without kit/tests |
- STOP (playbook 3: verifier FAIL). Permission check after step 14: clean. Not done: run-report.md, commits.
- Item 45: strict gate exit 1 accepted (kit tool problem). Committed 76a996c map, 2fd75c2 tests, 76b5322 code on exp1/kit. run-report.md written. STOP: waiting for the human's check and push; no push.
