# EXP1-R22C red run, test_compare_cli.py + test_compare_format.py (ae2)
Command: cd console && .venv/bin/python -m pytest tests/test_compare_cli.py tests/test_compare_format.py -q -p no:cacheprovider
Result: 61 collected, 61 failed, 0 passed (41 in test_compare_cli.py, 20 in test_compare_format.py). Ruff on both files: All checks passed.
- ModuleNotFoundError agent_console.compare_cli: 39 tests (36 in the cli file: every in-process CLI test, EP-011-03/04/17/20/22/23, DT-011-05..13, TC-ST-01..03, EP-027-*, DT-027-15, EP-031-04, DT-034-07..10, EP-035-01/02/04; 3 in the format file: EP-029-18, EP-026-06, BVA-013)
- ModuleNotFoundError agent_console.compare_format: 16 tests (BVA-015..030)
- agent_console/compare*.py files missing: 1 (TC-CL-02)
- /compare route missing, page 404 `{"detail":"Not Found"}`: 1 (EP-029-16)
- Subprocess tests (old `__main__` ignores `compare` and starts the console): EP-011-01, EP-011-02 (exit 1, port already in use), EP-027-06 (exit 1, expected 2), EP-011-21 (traceback, expected the exit-1 line): 4
Fixture sanity (scratch, deleted): the NOMAIN / CHILD3 / old-day / no-file-spawn recipes index as the cases assume (CHILD3 main ticket ABC-1, ticket_eff ABC-2); snapshot helpers are stable on a built index.
- EXP1-R22C: run_proc now sets a free AGENT_CONSOLE_PORT, 15 s timeout, kills child on timeout; 4 subprocess tests still red for the same reasons, 8790 never bound.
