# Code review 5 (delta), EXP1-R22C — PASS (BLOCKER 0, HIGH 0, MEDIUM 1, LOW 1) — copied by the coordinator from the reviewer's reply
All review 4 findings closed (B5-D1 recorded as Q-054; mutations a-d and window-end killed; index_mismatch reason; version tags gone). Console 751 passed, tools+kit 49, ruff clean (on a /tmp copy without .git).
1. MEDIUM compare.py:277-278 CON-014 v7 note B5-D1 (Q-054): "result time of the earliest copy that has one" unpinned — `end[r["id"]] = r["end_ts"]` (latest copy wins) survives. Test: one spawn copied into a resumed file, copy 1 result at 40, copy 2 result at 30, an unlinked file of the same session starting at 35 -> pairs (window 10..40), total 1 (latest-wins gives 2).
2. LOW test_compare.py:2191 ("review 4 finding 2"), test_store_and_flags.py:326 ("Review 1 finding 5"): name the rule or Q only.
Outside: exp1/kit and exp1/r22 change the same files; origin/main behind base.
