# Answers (given to both arms word for word; first given in the kit arm at 12:55)

Keep the existing behaviour of every observed rule; these apply to the comparison only.

1. CON-013, tokens per model: yes. Aggregate tokens by each message's own model, main session included.
2. CON-014, repeat rounds: a repeat round is any run of the same role on the same ticket after its first run (run 2, 3, ...). No verdict needed.
3. CON-015, failed run: a failed run is a run that did not complete: it ended in an API or permission error, was denied, or has no final assistant reply. A FAIL, BLOCKED or REJECT verdict is a result, not a failed run.
4. CON-018, waiting time: use the brief's rule. Gaps over 2 hours count as waiting. Also show one extra figure: the part of the waiting time that came from gaps over 2 hours. The existing "parked" rule elsewhere stays as it is.
5. CON-021, cost share: main session cost ÷ sub-agent cost, as the brief says. Sub-agent cost zero → "no sub-agents", not 0 and not infinity.
6. CON-022, unknown key: unknown means no runs and no sessions for that key in any log, ignoring the default period and scope. The comparison always uses all logs.
7. CON-020, active role time: the sum of run durations; parallel runs add up.
8. CON-012, unpriced messages: they still add zero to cost, and the comparison shows the number of unpriced messages next to the cost of that ticket.
9. CON-026, CLI: yes. `compare` becomes a subcommand; with no arguments `python -m agent_console` starts the server as today.

# Added at 12:57 in the R22 arm (questions only R22 raised). Give word for word to the kit arm too, at its next stop or when it asks.

10. Ratio and difference: if a is 0 or either side has no value, the ratio shows "n/a". The difference shows only when both sides have a value, otherwise "n/a".
11. Two runs of one ticket: out of scope. The same key twice compares a ticket with itself.
12. Rounding: the CLI text output is rounded like the page; JSON keeps raw values.

# Added at 12:58 in the kit arm (questions only the kit arm raised). Give word for word to the R22 arm too, at its next stop or when it asks.

13. CON-038 (failed runs): yes, the comparison may read the raw session logs, read-only, to find failed runs. Keep the definition in answer 3; do not narrow it.
14. CON-041 (wall time): wall time runs from the first to the last record timestamp across all the ticket's session files, main session and sub-agents together.
15. CON-043 (stop for the person): a stop for the person is an assistant turn that waits on the person: it ends with end_turn, or with an AskUserQuestion call, or with a permission prompt. Count a kind only if the log shows it; if a permission prompt leaves no trace in the log, it is not counted, and the rule says so.
16. CON-046 ("no main session"): "no main session" shows in every row that covers only the main session (wait time, main tokens, main cost) and in the share row.

Decision (kit arm, 12:58): ticket size L accepted.

# Added at 13:03 in the R22 arm (clarification of answer 16). Give word for word to the kit arm too, at its next stop or when it asks.

17. Clarification of answer 16 (rows): "no main session" applies to main-session wait time, main-session tokens, main-session cost and the share row. Ticket totals (role runs, total tokens, wall time and so on) show their real value, including 0.

# Added at 13:26 in the R22 arm. Give word for word to the kit arm too, at its next stop or when it asks.

18. Denied spawn: a sub-agent spawn that was denied before it started (no run file exists) counts in the run total and in the failed count.

# Added at 13:59 by the ops session in the kit arm (run 3). Give word for word to the R22 arm too if it asks.

19. Main session and "role runs": role runs are sub-agent runs only. A main session is not a role run: it is not counted in the role-run total, the failed count or the repeat rounds. It appears only in the main-session rows (wait time, tokens, cost) and in the share row.
20. Several main sessions on one ticket: their tokens, cost and waits are summed for the main-session rows and the share.
21. The /compare page is server-rendered, outside the hash-routed app, under the same local-only Host and header rules as the existing server.
22. Fields in the raw logs: find which log fields mark an API error, a permission denial and a missing final reply from the logs themselves (read-only), and write the finding into the rule. If a denied spawn cannot be tied to a ticket key from the log, it is not counted, and the rule says so. Read the browser rounding code in static/ctq-lib.js and keep the CLI/page rounding the same as the rules say.
23. Process: map reviewed and confirmed, size L accepted, run the security review (the analyst listed triggers). Raw prompts and replies from the logs must never be written to the output, the JSON or the page.

# Added at 14:00 by the ops session in the R22 arm (run 3). Give word for word to the kit arm too if it asks.

24. What ends a wait gap: only a message the person typed (a real human message). Task notifications, hook output, tool results and other machine-written user records do not end it. The person's answer to an AskUserQuestion ends the gap. A rejected permission prompt is a stop; its end is the next human message.
25. A denied spawn takes a number in the order of runs of its role, so it counts when numbering repeat rounds (it is a run, answer 18).
26. Ratio rounding: the ratio is shown with 2 decimals on the page and in the CLI text; JSON keeps the raw value.
27. Missing parameter a or b: the page shows one clear error message (HTTP 422) and the CLI prints usage and exits 2. No form, no swap action, no "compare with" link: they are not in the brief.
28. Keys follow the console's existing key rules; no extra case folding is added.
29. A message with no model id is counted under the model name "unknown".

# Added at 14:06 by the ops session in the R22 arm (run 3). The kit arm reads this file too; same rulings for both.

30. Wait gaps and user records without an origin (answer 24 refined): a user record ends a wait gap if it is text the person typed, including a slash command. It does not end a gap if it is a tool result, a task notification, hook output, local command output or the "[Request interrupted by user]" marker. In older logs with no marker, a user record that is not a tool result and not one of those machine-written kinds counts as typed by the person.
31. Spawns that failed before starting: any spawn that failed before it started (denied, agent type not found, worktree error, and so on) counts like a denied spawn under answers 18 and 25: in the run total, the failed count and the repeat-round order.
32. Display rounding: a .5 tie rounds away from zero; a negative difference rounds its size the same way and keeps its sign. Tokens are shown in thousands as `12k` (no thousands separator). The difference and the ratio are computed from the raw values, then rounded for display.

33. A spawn with no tool result and no run file (for example the session ended first) is not counted: there is no evidence of a run. Answer 31 applies only to spawns whose log shows an error result.
34. A negative difference that rounds to zero is shown as `0k` (or `0`, `$0.00`), never as `-0k`.

35. A spawn whose tool result is not an error but which has no run file: it counts as a run (the result is evidence of a run), in the run total and the repeat-round order, and it is not failed.
36. Time on the page and in the CLI text is written `12 min`; an hour or more stays in minutes (`135 min`). Rounded to whole minutes.

37. Standing rule for both arms (from the ops session, at the person's request that the ops session handle questions): for a small edge case that the brief and this file do not cover, pick the narrowest reading of the brief, write it into the rule and QUESTIONS.md (or the kit's equivalent) as "Agent decision", and go on without stopping. Stop and ask only for a question that would change what the feature does, its scope, or the budget.

38. Kit arm, builder FAIL caused by a wrong test (14:18): option 1. Send the test-designer back with the builder's report to fix only the test helper (unique ids for refused spawns); do not change the product; then re-run the builder code step. This extra loop is not a reviewer or security return round and does not use up the 2 rounds; note it in status.md as an extra loop. For the builder's decisions the rules do not cover and for its unverified points, item 37 applies (narrowest reading, "Agent decision"). Verify the no-argument server start with a test or a check and say which in the report.

39. R22 arm, requirements step, return rounds used up (14:22): option B. Accept the reviewer's two fixes for CON-022 as written (first sentence says "the next gap end"; the list says "tool results other than an AskUserQuestion answer"; a dismissed AskUserQuestion is not an answer, it counts as a rejected prompt, so its gap ends at the next typed message). The analyst applies them and a fresh reviewer re-checks. This extra loop does not use up a return round and is logged as an extra loop, like item 38 for the other arm. If the reviewer rejects once more, stop and ask.

40. The compare CLI and the console's shared index (R22 arm, Q-025, 14:38): option B, guarded refresh, as the analyst recommends. The CLI refreshes the index but refuses with a clear message (exit code 2, nothing written) if its time zone, key patterns or console home/checkout differ from the ones the index was built with. It never runs the git fetch. Also accepted as Agent decisions: Q-023 (a value of only spaces counts as missing) and Q-024 (while the console builds its first index, /compare answers HTTP 503 with one message).

41. R22 arm, system analysis, return rounds used up (14:47): allow one more analyst round for the stale version references only (text references, no meaning change), then the second system analyst re-checks. It is an extra loop, not a return round, and is logged as such (like items 38 and 39). If the checker rejects once more, stop and ask.

42. R22 arm, a refused log scan (14:22): the refusal stands. Do not retry that scan and do not look for another way around it. The Q-037 decision stays as the reviewer judged it. Further read-only scans of the log files are allowed only as answer 22 says (field names and short patterns, no log content) and only if the tool allows them; if one is refused, note it and go on without it. Re-point the cases at the new rule versions as the notes say.

43. R22 arm, test design, return rounds used up (14:45): allow one extra test-design round for the four cost cases (EP-018-01, -02, -04 and EP-019-01) only, then the lead QA re-checks. It is an extra loop, not a return round, and is logged as such (like items 38, 39 and 41). If the lead QA rejects once more, stop and ask.

44. Kit arm, human stop after the delta analyst round 3 (15:47): map confirmed, size L, security trigger stays. Go on with the test step, the code step, reviewer and security on the new diff, then the verifier. Conflict 1 (denial wording): keep the current wording, a permission denial fails the run only if no normal final reply follows it (the same reading the R22 arm's rules use for answer 3); the F11 fixture puts the denied result after the last normal reply. Conflict 2 (answer 35): a spawn with a non-error result and no run file counts as a run and is not failed; the test step adds a case for it and the code step changes the code if needed. The re-plan gets a fresh budget of 2 return rounds; record that in the run report.

45. Kit arm, verifier FAIL on the strict coverage gate (16:58): option 1. Accept the exit 1 as a known condition outside this ticket (the four AUDIT-* fixture strings in kit/tests/test_rule_coverage.py); record it in the run report as a problem of the kit tool, not of this work; do not edit the kit. Then commit the map, the tests and the code on this branch (exp1/kit) only, in the repo's commit style, write the run report, and stop. No push. Keep the L3 checklist and the handback risk in the report as the verifier wrote them.

46. R22 arm, code review return rounds used up (17:40): option A. One extra loop, logged as an extra loop and not a return round: the business analyst records B5-D1; an automation engineer adds the four tests and fixes the docstrings, each test proven against its mutation; the builder gives index_mismatch its reason; a fresh delta review runs. If that review rejects again, stop and ask. Branch merge notes in your report are noted; nothing is merged or pushed in this experiment.

47. R22 arm, HV-1 (the /compare page while the console re-scans, 17:59): option A. During any scan the page answers HTTP 503 with the same one message as for the first index ("The console is updating its index. Reload this page later."), never a mix of old and new tables and never a false "unknown key". The CLI waits for its own scan as before. Write it into the rules as an Agent decision with tests.

48. R22 arm, code review 6 rejected, no return rounds left (18:22): option A. One extra loop, in scope only, logged as an extra loop and not a return round: an automation engineer adds review 6's tests and the NEW-2 and NEW-3 tests; the builder fixes the argument-parser echo, NEW-2 and NEW-3; a delta review and a security re-check run. NEW-1 (the old ingest stops on one malformed log line, so /compare stays at 503) is accepted as a known limit outside this ticket, recorded in the report and the backlog; do not change parser.py or the store's ingest (existing behaviour of every page stays as it is). If anything rejects again, stop and ask.

49. R22 arm, code review 7 rejected (18:46): option B. One more extra loop, tests only: an automation engineer adds and fixes the tests for review 7's items 1 to 4, each proven against its mutation; a delta review runs. Items 5 and 6 and security NEW-5 (a symlinked -wal) are accepted as known low limits, recorded in the report and the backlog; do not change product code. If the delta review rejects again, stop and ask. Do not touch the consoles on ports 52209 and 52440.

50. R22 arm, environment checker returned "placeholder" with no verdict (18:58): option A. Run the environment checker once more with the same brief (no rewritten prompt). If it passes, continue with the test runner, then the verifier, then the lead QA's hand-off line. If it gives no verdict again, stop and ask. Record in the report that the first run gave no verdict.

51. R22 arm, environment checker returned "placeholder" twice (19:00): option A. Skip a new environment check and rely on the first full one (PASS at about 17:46; nothing in the lane changed since, and the 798-test run on the final version works). Go on with the test runner on the seven ticket test files, then the verifier last, then the lead QA's hand-off line. Do not reword the checker's brief. Record both empty runs, and that the hand-off rests on the earlier PASS, in the report.
