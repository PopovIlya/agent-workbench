0891a04 (exp1/r22, uncommitted tests) · red run done for test_compare_cli.py + test_compare_format.py · next: reviewer mutation check once product code exists · open bugs: none
- Written: console/tests/test_compare_cli.py (41 tests), console/tests/test_compare_format.py (20 tests). Nothing else touched (no conftest, no product file).
- Red run: 61 collected, 61 failed, 0 passed, 0 errors; ruff: All checks passed.
- Failure reasons: 55 ModuleNotFoundError (compare_cli 39 (36 in the cli file, 3 in the format file), compare_format 16); 1 missing module files (TC-CL-02); 1 missing /compare route (404, EP-029-16); 4 subprocess tests: `__main__` still starts the console (address already in use / exit 1 not 2 / traceback on bad db).
- Not automated here (target is another file or a review check): EP-011-18, EP-011-19 (store_and_flags); page halves of EP-011-01, EP-026-06, EP-027-*, EP-034-*, EP-035-03..06 (test_compare_page.py); TC-CL-02 check 1 (git diff, reviewer); TC-CL-01/03 (checklist).
- Lead QA notes 1-3, 7 do not touch these files (TC-ST-08/-11 are in test_compare.py); notes 4-6 no impact.
- Subprocess tests (EP-011-01, -02, -21, EP-027-06) use env=os.environ.copy(), timeout 90 s; before the product exists the old `__main__` tries to bind the console port and exits at once (port in use).
