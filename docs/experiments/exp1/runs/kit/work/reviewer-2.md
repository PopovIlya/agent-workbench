FAIL

# Reviewer report: EXP1-KITC, round 2

Workbench: <workbench>. Diff: tracked changes plus untracked compare.py, test_compare.py.

## Re-run by me (throwaway copy /tmp/rv2)
- console suite 500 passed; test_compare.py 55 passed; ruff clean.

## Round 1 findings
- F1 CON-036, F2 CON-052, F3 CON-027: closed (tests added, marked).
- F4/F7: closed. `compare.py:65-91` run_failed no longer special-cases SubagentHandback; red test now green. CONFLICT remains in the map text only if the analyst has not changed it: CON-035 (`docs/requirements/console.md:299`) already says end_turn only, so code and map agree. UNVERIFIED: kit runs that end on a handback call now count as failed in live logs.
- F5 (M2), F6 (M9), F8 (M14): carried-over mutations re-checked by the builder; I did not re-run them in this round beyond the suite. `len(a) > 60` guard removed (`server.py:201`), conforms.
- Conventions: no new dependencies, no scope creep in this delta.

## Mutation check (round 2)
Carried over: M10 (handback name), now moot since the branch is gone. New (changed code, run_failed and server route), applied one at a time, __pycache__ disabled (a stale .pyc gave a false kill on the first try; redone):

| # | Mutation | Location | Result |
|---|---|---|---|
| N1 | `not stop == "end_turn"` to `False` | compare.py:91 | KILLED: test_run_that_did_not_complete_is_failed[no_final_reply] |
| N2 | drop `or not has_text` | compare.py:91 | SURVIVED (CON-035 "a run with no assistant text"; no test of an end_turn run with no text) |
| N3 | `bad = False` to `pass` (an API error followed by a normal reply no longer clears) | compare.py:82 | SURVIVED (no test that a later normal reply clears an earlier error, or the opposite) |
| N4 | `isApiErrorMessage` check to False | compare.py:76 | KILLED: ...[api_error_assistant] |
| N5 | `not a or not b` to `and` | server.py:201 | KILLED: test_page_without_a_or_b_is_one_422_error |
| N6 | unknown key 404 to 200 | server.py:206 | KILLED: test_page_unknown_key_is_a_clear_error |
| N7 | __main__ argv branch | __main__.py:3 | not applied (the line mutator did not match); covered by the CON-027 runpy test by reading only, UNVERIFIED |

## Findings
- F9: N2 survived. CON-035 `compare.py:91`. Add a case: last record end_turn with only empty or non-text blocks must count failed.
- F10: N3 survived. `compare.py:82`. Either the clearing of `bad` by a later reply is a rule (then test it) or it is an unrequested behaviour (then drop it). CON-035 says a run that ended in an API error is failed; it does not say a later reply clears it.

## Return to
- test-designer: F9, F10 (test or ask analyst to state the rule).
- analyst: F10 wording in CON-035.

Throwaway copy /tmp/rv2 and the helper script removed.
