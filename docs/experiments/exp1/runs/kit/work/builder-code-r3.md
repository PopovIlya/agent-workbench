PASS

# builder report (code): EXP1-KITC, round 3

Changed only `console/agent_console/compare.py`, `_ticket` (about 5 lines). The no-run-file spawn query now selects Agent/Task spawns that have a tool result (`end_ts IS NOT NULL`), not only error ones. It keeps `is_error` per spawn. The role count uses the role of each spawn. The failed count includes only spawns whose result is an error. Rules: CON-037, CON-053 (answers 35, 44).

## Results (observed)
- Console suite: 554 passed (the red test is green).
- Install and kit suite (`tests kit/tests`): 49 passed.
- ruff: all checks passed.

## Agent decision
- "Has a result" is read from `tool_calls.end_ts IS NOT NULL`. I did not check against the log by hand. The tests for "no result at all" and "error result" pass.

## Notes
- The re-plan budget of 2 return rounds (answer 44) is not used here; this is the first code round of the re-plan.
- Tests not touched.
