PASS

# Builder report, step tests, return round 2: EXP1-KITC

Only `console/tests/test_compare.py` changed (5 new parametrized cases, all `# rule: CON-035` via the existing tests). No product code touched.

## F9 (N2)
Added to FAILING: `end_turn_with_only_blank_text`, `end_turn_with_only_non_text_blocks` (thinking + tool_use, stop end_turn). Basis: answer 3 "no final assistant reply".

## F10 (N3)
Added: FAILING `api_error_after_a_normal_reply`; NOT_FAILING `normal_reply_after_an_api_error` and `normal_reply_after_a_system_api_error`.

## Results (observed; PYTHONDONTWRITEBYTECODE=1, no cache)
- Against current product code: test_compare.py 60 passed (none red); console suite 505 passed; ruff clean.
- N2 (drop `or not has_text`, compare.py:91): 2 failed, the two F9 cases. KILLED.
- N3 (`bad = False` -> `pass`, compare.py:82): 2 failed, the two `normal_reply_after_*` cases. KILLED.
- compare.py restored from a copy; shasum identical before and after (RESTORED).

## Agent decisions (answer 37)
- "Ended in an API error" (answer 3): the run's final state decides. A later normal reply clears an earlier API error (assistant-flag or system api_error); an API error after a normal reply makes the run failed. Tests are written for both orders. CON-035 wording should state this (analyst).
- An end_turn record with only blank text or non-text blocks is no final reply, so the run is failed.
