head 0891a04 (no commit) · red run done, ruff clean · next: product code by builder; re-run the 4 touched files · open bugs: none
Files: console/tests/test_compare_page.py (new, 45 tests); appended: tests/test_server.py (2), test_static.py (1), test_store_and_flags.py (4); new data file tests/fixtures/golden_ticket_columns.json (golden made from `git archive 0891a04` code, script in /tmp/ae3/gen2.py).
Red run: 50 new tests fail, all for a missing route/module/file/meta row; 39 pass = 37 old + 2 new guards (EP-033-08, EP-032-02).
Not automated here: see ae3-red.md.
