# Code review 8 (delta), EXP1-R22C — PASS (BLOCKER 0, HIGH 0, MEDIUM 0, LOW 1) — copied by the coordinator from the reviewer's reply
Review 7 items 1-4 closed; each mutation re-run by the reviewer and killed. No product file changed since review 7 (last write 18:31). No test line removed from the base. Ruff clean. Touched test files 349 passed on a /tmp copy.
LOW test_compare_cli.py:1034: docstring of test_new_3_refusal_of_a_wal_without_shm_creates_no_file still says "exit 1 or 2"; the test asserts rc == 2 and the exact line.
Known, parked: review 7 items 5, 6 and security NEW-5 (answer 49); NEW-1 (answer 48); INFO-1; raw AGENT_CONSOLE_HOME path in refusal lines; NEW-4.
