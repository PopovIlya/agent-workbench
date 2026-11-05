0891a04 · test_compare.py written, red run done · next: reviewer mutation check once compare.py exists; builder turns it green · open bugs: none
- File: console/tests/test_compare.py (123 test functions, 145 test items with parametrize). No product file touched, conftest untouched.
- Red run: 145 failed, all ModuleNotFoundError agent_console.compare (fixtures and in-test preconditions pass first). Ruff: All checks passed.
- Imports of agent_console.compare are inside tests (importlib), a missing module fails, never skips.
- Data halves only for cases shared with page/CLI/format files (EP-013-05, 014-06, 025-03, 026-06, 027-xx, 028-01, 030-01/02, 035-02/04, BVA-004/005/007..011/013): page, CLI text, exit lines, formatter strings are left to test_compare_cli.py, test_compare_page.py, test_compare_format.py.
- CLI exit-line halves not run here: python -m agent_console compare still falls through to server.main() on this base, so no subprocess.
- Not automated: BVA-001 (dropped), BVA-012 (merged to format), TC-CL-01..03 (checker / other files), EP-029/033/034/010/011/031/032 (other files).
- Lead QA notes: 1 (uA/uB uuids differ, asserted), 2 (TC-ST-08 and TC-ST-11 second variants own tests), 3 (copies keep sessionId, no S2 token asserts) applied; 4-7 not in this file.
- Log: /tmp/ae1-red.log
