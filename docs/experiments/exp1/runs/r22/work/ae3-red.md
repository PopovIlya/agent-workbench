# EXP1-R22C ae3 red run (page, existing-file regressions)
Command (console/): .venv/bin/python -m pytest tests/test_compare_page.py tests/test_server.py tests/test_static.py tests/test_store_and_flags.py -q -p no:cacheprovider
Result: 50 failed, 39 passed. Ruff on the 4 files: All checks passed.

## Written
- test_compare_page.py, 45 tests: CON-010 (EP-010-01, -06; DT-010-02..05), DT-027-13/14, EP-011-01 (page half), EP-025-03 (page half), EP-027-01..05,07,09..12, EP-031-02/03, EP-033-01,02,04..07,09,10, BVA-031, DT-034-01..05, EP-034-06,12..15, EP-035-03..06.
- test_server.py (+2): EP-032-04 (needs a GET /compare route), EP-033-08 (uvicorn.run spy, host 127.0.0.1).
- test_static.py (+1): compare.css is a static file and obeys the strict rules (EP-033-10 static part).
- test_store_and_flags.py (+4): EP-011-18, EP-011-19, EP-032-03 (meta home/repo_root), EP-032-02 (ticket-column golden; golden file tests/fixtures/golden_ticket_columns.json, 8 rows from fixtures/logs plus 2 synthetic sessions, made with base-commit code).

## Failure reasons (new tests)
- test_compare_page.py (45): 28 body {"detail":"Not Found"} (route absent), 8 content-type json instead of html, 4 status 404 instead of 200, 2 host-guard control request 404, 1 no /compare route, 1 ImportError agent_console.compare (EP-027-09, inside the test: fails, not skips), 1 tuple of 404s.
- test_server.py 1 (no GET /compare route); test_static.py 1 (compare.css missing); test_store_and_flags.py 3 KeyError 'home'.
- No fixture or syntax error. Fixtures checked in a scratch run against the base code (runs/keys as expected).

## Already passing (guards of existing behaviour)
- test_server.py::test_ep_033_08_main_binds_loopback_only
- test_store_and_flags.py::test_ep_032_02_ticket_columns_equal_the_golden_of_the_base_commit
- All 37 pre-existing tests in the 4 touched files pass.

## Not automated by me (owner / reason)
- CLI halves of EP-011-01..04,17,20..23, EP-025-03, EP-027 (06,08 and the CLI parts), EP-031-04, EP-035-01/02/04 (CLI parts), DT-027-15, DT-034-07..10, TC-ST-01..03, TC-CL-02: test_compare_cli.py (other engineer).
- Data/format/state cases (test_compare.py, test_compare_format.py): other engineers.
- TC-CL-01 (pricing.yaml unchanged): checklist by git diff; a pinned hash test would fail every later price update. TC-CL-03: lead QA.
- EP-033-08 existing test (test_main_refuses_non_loopback_bind) is untouched and still passes.
- EP-035-04 page part asserts runs.total == 2 and the absent strings; runs.failed == 2 is left to the JSON/CLI test.
Notes: DIR/th class: the Difference heading is asserted by text only (EP-010-01 shows no class, B2 shows class="d"; the test accepts both). Lead QA notes 1-3,6,7 belong to the other files; note 4 applied (NOMAIN fixture for EP-033-06/07, 034-13/14, 035-05).
