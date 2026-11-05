FAIL

# Reviewer report: EXP1-KITC, round 3

Workbench: <workbench>. Diff: tracked changes plus untracked compare.py, test_compare.py. Only test_compare.py changed since round 2 (no product code).

## Re-run by me (throwaway copy /tmp/rv3, no bytecode)
- console suite 505 passed; ruff clean.

## Previous findings
- F9 (N2): closed. Dropping `or not has_text` (compare.py:91) now fails 2 tests.
- F10 (N3): closed in tests. Dropping `bad = False` (compare.py:82) now fails 2 tests.
- CON-035 wording (analyst, F10): the map text (docs/requirements/console.md:299) still does not say that a later normal reply clears an earlier API error and an API error after a normal reply fails the run. Not a code defect; rule text lags the tests (builder decision, answer 37). Map is the analyst's file.

## Mutation check (round 3)
Carried over: N2, N3 (re-run, killed). New, on the unchanged run_failed code, one at a time, each diff line confirmed as executable code:

| # | Mutation | Location | Result |
|---|---|---|---|
| N2 | drop `or not has_text` | compare.py:91 | KILLED (2 tests) |
| N3 | remove `bad = False` | compare.py:82 | KILLED (2 tests) |
| N8 | denial prefix match to `startswith(("zzz",))` | compare.py:89 | SURVIVED |
| N9 | system `api_error` check to `if False` | compare.py:73 | KILLED (1 test) |
| N10 | synthetic-model skip to `if False` | compare.py:80 | SURVIVED (probably near-equivalent: synthetic records also carry isApiErrorMessage, which is handled earlier at :76; no test with a synthetic record lacking that flag) |

## Findings
- F11: N8 survived. CON-035 `compare.py:89`. Every permission-denial fixture (`test_compare.py:411-418, 471, 488`) uses stop `tool_use`, so the run fails through the missing end_turn and the denial detection is never what decides. Add a case where the run ends with `end_turn` and a text reply but contains a denied tool_result (both DENY1 and DENY2 wording), expected failed; and a non-denial `is_error` tool_result with end_turn expected not failed.
- F12 (minor): N10. Either add a test with a `<synthetic>` assistant record without `isApiErrorMessage` followed by nothing (expected: does not clear or set state as the rule intends), or state in the map that it is equivalent. State the intent via the analyst; low priority.

## Return to
- test-designer: F11 (required), F12 (optional).
- analyst: CON-035 wording on final-state rule.

Throwaway copy /tmp/rv3 removed.
