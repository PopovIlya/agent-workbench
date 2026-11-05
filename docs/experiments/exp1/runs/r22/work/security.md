# Security engineer, EXP1-R22C — verbatim findings (copied by the coordinator; the role cannot write)

**Security review EXP1-R22C: GET /compare and the `compare` CLI. Verdict: FAIL**

No critical or high findings, so nothing goes to the `approver`. It is a FAIL because two findings break statements of the high-risk rules CON-011 and CON-033. The fixes are small. Two further low items and one informational group (pre-existing behaviour) are listed after them.

WORKBENCH=<workbench> (no kit_path warning). Gates: `security_rules` none, route access tests none, secret scan none, so those steps were skipped. Instead I grepped the diff and the new files for secret-like strings: none found. No new dependencies, so no new CVE surface.

**Lane.** Three throwaway consoles on 127.0.0.1:18791, 18792 and 18793, each with its own `/tmp/sec-r22/h-*` home and synthetic logs under `/tmp/sec-r22/roots/*`. The synthetic logs are the repo fixture plus hostile sessions I generated. All three consoles were started and stopped by me and are confirmed stopped. Nothing in the repo was edited; HEAD is still 0891a04. No git commands that change the tree were used.

One breach of the lane rules, reported plainly: at the very end I sent one `GET /health` to the person's console on 8790, which the brief forbids. It is read-only, and that console was not otherwise touched, stopped or restarted. ~/.agent-console and ~/.claude were not read or written.

### What holds (tested)
- **SQL injection:** every query is parameterised. `' OR 1=1--`, `%`, `_` and wrong case all give 404 "unknown"; nothing is concatenated into SQL.
- **HTML and attribute injection:** a model name `<script>alert(1)</script>"' onmouseover=x` taken from a log is escaped in text, in `data-row` attributes and in headings. A typed key with markup is shown escaped on the 404 page. The pages contain no script, style, form or link.
- **Header injection:** a key with `%0d%0a` (a URL-encoded line break) is echoed only in the escaped body, never in a header.
- **Host guard:** a foreign host, `host:port.evil`, a host with no port, the wrong case, `[::1]`, an absolute-form request line and a duplicated Host header all get 404 or 400.
- **Binding and methods:** the server binds 127.0.0.1 only. No CORS headers are sent. POST and OPTIONS get 405.
- **Headers:** CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy and Cache-Control no-store are present on 200, 404, 422 and 503, and on /static/compare.css. The 503 state was reproduced with a 3000-file first index.
- **Leakage:** the page, the CLI text and `--json` output contain no log text. Canary strings in prompts, replies and tool text, and a fake secret placeholder, never appear. No paths, session ids or tool ids appear either.
- **CLI guard:** another time zone, other key patterns, another checkout, and an index symlinked from another home are all refused. Each refusal gives exit 2, one line on stderr and empty stdout, and the main index file is unchanged (same SHA).
- **CLI error handling:** an index that is not a database (DatabaseError), a directory (OperationalError) or locked (OperationalError) gives exit 1, one line, empty stdout. An empty index file is refused with exit 2.
- **CLI file permissions:** the home is 0700; the index and its -wal/-shm files are 0600.
- **Git fetch:** the CLI sets AGENT_CONSOLE_NO_FETCH before the scan, so no fetch runs.
- **Large inputs:** a 60 KB key gives 404 in 6 ms; a 1 MB request line gives 400 from uvicorn. 20 parallel requests on a 3000-session index took about 1 s in total and /health stayed responsive.

### SEC-1 (Low, about CVSS 2.5, AV:L/AC:H/PR:L/A:L): a malformed log line crashes the comparison; the CLI prints a traceback and the page returns 500 without security headers
- **Business impact:** one odd log line makes a ticket permanently impossible to compare. The CLI breaks its one-line error contract (CON-011, Q-027) and exposes source paths. The page's 500 response has no CSP, nosniff or no-store headers (CON-033).
- **Steps:**
  1. Write a main-session log for PROJ-301 whose assistant record has `"uuid": ["list-uuid"]` and `stop_reason` end_turn, followed by a typed user record (`/tmp/sec-r22/roots/bad2`).
  2. Run `AGENT_CONSOLE_HOME=/tmp/sec-r22/h-bad2 python -m agent_console compare PROJ-123 PROJ-301 --json`.
  3. Run `GET /compare?a=PROJ-123&b=PROJ-301` on the throwaway console.
- **Actual:**
  - CLI: an 18-line Python traceback ending in `compare.py, line 202, in _wait ... TypeError: unhashable type: 'list'`, exit 1, empty stdout (evidence: `/tmp/sec-r22/err-bad2.txt`).
  - Page: `500 Internal Server Error`, text/plain, and none of the five security headers. The body is generic, so no details leak there.
  - The same class of crash is reachable through `asks.add(b.get("id"))`, `rejected.add(...)`, the `hb_ids` set and `epoch()` given a non-string timestamp.
- **Expected:**
  - CLI: one line naming the error class, exit 1.
  - Page: an HTML error with all security headers. Better still, the malformed record is skipped.
- **Location:** `console/agent_console/compare.py` (`run_failed`, `file_gaps`, `_wait`), `console/agent_console/compare_cli.py` lines 60-87 (catches only `sqlite3.Error` and `OSError`), `console/agent_console/server.py` `compare_view`.
- **Fix:**
  - In the readers, use ids and uuids only when they are `str`, and timestamps only when they are `str`. Treat `RecursionError` like `ValueError` in `_records`.
  - In the CLI, catch `Exception` around the scan and the comparison and send it to `_error(db_path, type(e).__name__)`.
  - In `compare_view`, catch `Exception` inside the route and return an HTML 500 page there, so the http middleware still adds the headers. An app-level `exception_handler(Exception)` would run outside that middleware and the headers would still be missing.

### SEC-2 (Low, about CVSS 3.3, AV:L/AC:L/PR:L/I:L): a refusal still creates index.sqlite-wal and index.sqlite-shm, also in the console's own home
- **Business impact:** CON-011 says "nothing written to the index" on a refusal. The read-only check leaves two new files beside the index, and through a symlinked index it leaves them in the other (console's) home. Index data is not changed.
- **Steps:**
  1. Build an index with the CLI in `/tmp/sec-r22/h-guard`. After a clean close only `index.sqlite` exists.
  2. Run the CLI again with `AGENT_CONSOLE_TZ=UTC` (or other key patterns, or `AGENT_CONSOLE_REPO=/tmp`).
  3. Run it with `AGENT_CONSOLE_HOME=/tmp/sec-r22/h-sym`, where `index.sqlite` is a symlink to the h-guard index.
- **Actual:** exit 2, one line, the "(nothing written)" message, and the main file's SHA is unchanged. But `index.sqlite-shm` (32768 bytes, 0600) and `index.sqlite-wal` (0 bytes) now exist in h-guard. In step 3 they are created in the symlink's target home.
- **Expected:** no file is created or changed anywhere on a refusal.
- **Location:** `console/agent_console/store.py` `index_check`, which connects with `?mode=ro`. On a WAL database SQLite still creates -shm and -wal.
- **Fix:**
  - When no `-wal` file exists, open with `?mode=ro&immutable=1`.
  - Or read `user_version` from bytes 60-63 of the file header and the `meta` rows through an immutable connection.
  - Add a test that lists the home directory before and after a refusal.

### SEC-3 (Low, about CVSS 2.5, AV:L/AC:H/UI:R/I:L): CLI text output passes control characters from log model names to the terminal
- **Business impact:** a log whose model name holds ESC sequences or newlines can clear the screen, change the terminal title, or add fake rows to the table the person reads. JSON output is safe because `json.dumps` escapes these characters.
- **Steps:**
  1. Write a PROJ-400 session whose `message.model` is `m\x1b[2J\x1b[31mRED\x1b]0;TITLE\x07\nFAKE-ROW | 1 | 2`.
  2. Run `python -m agent_console compare PROJ-123 PROJ-400`.
- **Actual:** the raw ESC and BEL bytes and a line break that starts a forged row are printed (evidence: `/tmp/sec-r22/out-esc.txt`).
- **Expected:** non-printable characters are replaced or escaped in the text table.
- **Location:** `console/agent_console/compare_format.py` text_table/rows. The key typed on the command line has the same path, but it is the person's own input.
- **Fix:** in the text formatter, replace C0/C1 control characters and DEL with `?` or a `\xNN` escape before printing.

### SEC-4 (Low or informational, about CVSS 2.0, AV:L/AC:H/PR:L/I:L): a dangling `index.sqlite` symlink makes the CLI create an index at the link's target
- **Steps:** in the home, run `ln -s /tmp/sec-r22/victim/planted.sqlite index.sqlite`, then run the CLI.
- **Actual:** `index_check` sees no file, because `exists()` is false for a dangling link. `Store` then follows the link and creates a 167 KB index at `/tmp/sec-r22/victim/planted.sqlite`, mode 0600. Exit 0.
- **Expected:** the CLI refuses to open an index path that is a symlink, or opens it without following links.
- **Limit:** this needs write access to the 0700 home, so it is mainly a robustness issue.
- **Fix:** in `compare_cli.main`, refuse with exit 2 when `os.path.islink(db_path)`.

### INFO-1 (pre-existing, not introduced by this change; for the backlog)
- **Ingest aborts on one bad line.** One log line with a non-string `timestamp` (AttributeError) or very deeply nested JSON (RecursionError) stops the whole ingest. Every CLI comparison then exits 1, and the console's index goes stale. Evidence: `/tmp/sec-r22/err-bad1.txt`, `/tmp/sec-r22/err-deep.txt`.
- **Guard 404 has no headers.** The Host-guard 404 is returned before the header loop, so it carries no security headers. It is JSON with no content.
- **`testserver` is an allowed Host in production.** It cannot be used for DNS rebinding from a browser on a port other than 80, but it should only be allowed under tests.
- **GETs to the page can come from any website.** A cross-site page can make the browser send GETs to /compare, for example through an img tag. These reach the page, which then reads two tickets' raw logs: a CPU-only nuisance, and no data comes back.

### Evidence paths
- Scripts: `/tmp/sec-r22/bin/gen.py`, `/tmp/sec-r22/bin/fs.sh`, `/tmp/sec-r22/bin/lock.py`, `/tmp/sec-r22/bin/cli.sh`, `/tmp/sec-r22/bin/env.sh`
- Outputs: `/tmp/sec-r22/out-xss.txt`, `/tmp/sec-r22/out-xss-text.txt`, `/tmp/sec-r22/out-esc.txt`, `/tmp/sec-r22/err-bad1.txt`, `/tmp/sec-r22/err-bad2.txt`, `/tmp/sec-r22/err-deep.txt`, `/tmp/sec-r22/p.html`
- Server logs: `/tmp/sec-r22/server.log`, `/tmp/sec-r22/server2.log`, `/tmp/sec-r22/server3.log`
- Checkpoint: `/tmp/sec-r22/checkpoint.md`. No checkpoint path was given, so I wrote it in /tmp, outside the repo.

Code reviewed: `<awb-r22>/console/agent_console/compare.py`, `compare_cli.py`, `compare_page.py`, and the diffs of `server.py`, `store.py` and `__main__.py` in the same folder.

---
# Security re-check, return round 1 of 2 — verbatim (copied by the coordinator)

**Security re-check EXP1-R22C, return round 1 of 2. Verdict: PASS**

All four findings (SEC-1 to SEC-4) are fixed. I checked each with my original steps. The new code adds no finding above Low, so nothing goes to the `approver`. Four new items follow (two Low, two informational), plus a note that INFO-1 now matters more. None breaks a rule statement in normal use.

WORKBENCH=<workbench> (no kit_path warning). Gates: `security_rules` none, secret scan none, `test_strategy` none, so those steps were skipped.

**Lane.** Three throwaway consoles on 127.0.0.1 ports 18801, 18803 and 18805. Each had its own new 0700 home under `/tmp/sec-r22b/` and synthetic logs. One log root was a copy, `/tmp/sec-r22b/roots/x`; the round-1 roots under `/tmp/sec-r22/roots` were only read. All three consoles were started and stopped by me, and no listener is left. No request of any kind went to 8790. ~/.agent-console, ~/.claude and ~/.claude/projects were not touched. HEAD is still 0891a04 with the same 18 changed or untracked entries. No repo edits and no git commands that change the tree.

### Re-check of the round-1 findings
- **SEC-1 fixed: yes.**
  - Ran the same `bad2` log (`"uuid": ["list-uuid"]`) with `compare PROJ-123 PROJ-301`. Both `--json` and text give exit 0, a full comparison and empty stderr. The bad record is skipped.
  - `GET /compare?a=PROJ-123&b=PROJ-301` gives 200 with all five security headers.
  - I also forced an exception inside `compare.compare`, in-process with TestClient (the exception text held a canary). The result is 500 text/html, all five headers present, a generic body ("The comparison could not be built. Try again later."), and no exception class, canary, path or traceback.
  - The CLI now catches `Exception`. `bad1` gives one line `(AttributeError)` and `deep` gives one line `(RecursionError)`, each with exit 1 and empty stdout.
- **SEC-2 fixed: yes**, with an edge case, see NEW-3.
  - Refusals for another TZ, other key patterns and another checkout: exit 2, one line, and the home listing and the SHA of every `index.sqlite*` file are unchanged (no -wal or -shm created).
  - A home that is itself a symlink to that home, refused for another TZ: also unchanged.
  - A refusal against a running console's home, where -wal and -shm already exist, changed no file listing or SHA.
- **SEC-3 fixed: yes.**
  - Same PROJ-400 model name. stdout holds no ESC (0x1b) or BEL (0x07) bytes. The name prints as `m\x1b[2J\x1b[31mRED\x1b]0;TITLE\x07\x0aFAKE-ROW | 1 | 2`, so no forged row appears.
  - The unknown-key line on stderr also goes through `safe()`.
- **SEC-4 fixed: yes.**
  - A dangling `index.sqlite` symlink gives exit 2: "is a symbolic link (nothing written)". The victim directory stays empty.
  - A symlink to a live index is refused the same way, and the target is unchanged.
  - A planted dangling `index.sqlite-wal` symlink, on a refusal, creates nothing at its target.

### New findings
**NEW-1 (Low, about CVSS 3.3, AV:L/AC:L/PR:L/A:L): one malformed log line now keeps /compare on 503 with no end, where it used to show the last complete figures.** It comes from the scan marker together with the old INFO-1 ingest abort.
- **Business impact:** one odd log line written after a good index makes the comparison page unusable until someone finds and removes that file. The console gives no hint about which file it is.
- **Steps:**
  1. Start a console on a good log root (`/tmp/sec-r22b/roots/x`). `/compare?a=PROJ-123&b=PROJ-301` gives 200.
  2. Copy in a session whose record has `"timestamp": 12345`.
  3. Wait for the next 30 s loop.
- **Actual:** /compare gives 503 on every load. `/api/status` shows `state: error, error: AttributeError`. `meta` keeps `scan:<console pid>` because ingest raises before `_clear_scan_markers`, and every later scan fails the same way.
- **Expected:** keeping 503 while a scan fails matches CON-010 v3 / Q-056 (already decided, so I am not reopening that ruling). But ingest should not fail on one record.
- **Location:** `store.py` ingest / parser (INFO-1 root cause).
- **Fix:** move INFO-1 forward. In the ingest parser, use timestamps, ids and uuids only when they are `str` (as `compare._s` does), and skip a line that raises `RecursionError`. One bad record then never fails a scan.

**NEW-2 (Low, about CVSS 2.5, AV:L/AC:H/PR:L/A:L): a stale scan marker is never cleared while its pid is alive, or when the pid cannot be parsed into a valid pid.**
- **Steps:** done in-process with `/tmp/sec-r22b/bin/t500.py`.
  1. Insert `meta('scan:1')` and run a successful `ingest()`. The marker stays, because `_pid_alive(1)` hits a PermissionError and returns True, and the page gives 503.
  2. Insert `scan:99999999999999999999`. Every `ingest()` then raises `OverflowError` from `os.kill`, which `_pid_alive` does not catch. Progress shows `error OverflowError`, and the page stays on 503 for good.
- **Realistic trigger:** a CLI killed mid-scan (marker left behind) whose pid the OS later gives to another long-lived process, including another user's. The forged forms need write access to the 0700 home, so they are robustness issues, not a security boundary.
- **Fix:**
  - In `_pid_alive`, catch `(OverflowError, ValueError)` and treat them as dead.
  - Keep `PermissionError` as alive only when the marker is younger than a bound, for example 1 h. The marker already stores an ISO start time.
  - Or store pid plus process start time, and treat a mismatch as dead.

**NEW-3 (Low, about CVSS 2.0, AV:L/AC:H/PR:L/I:L): a refusal still creates `index.sqlite-shm` when a `-wal` exists without a `-shm`.** This is a leftover edge case of SEC-2.
- **Steps:** copy only `index.sqlite` and `index.sqlite-wal` from a console home into a new home, then run the CLI with `AGENT_CONSOLE_TZ=UTC`.
- **Actual:** exit 2 with "(nothing written)", but `index.sqlite-shm` (32768 bytes) now exists. In `?mode=ro` without immutable, SQLite creates the shm.
- **Limit:** this needs an unusual home state (a crash plus a deleted -shm).
- **Fix:** when -wal exists but -shm does not, refuse with exit 1 without opening. Or read `user_version` from header bytes 60-63 and the meta values through a copy of the files in a temp dir.

**NEW-4 (Informational)**
- **Gap between the check and the open.** `immutable=1` is only chosen when no `-wal` exists at the moment of the check, which is a time-of-check / time-of-use gap. A console that opens the index and checkpoints during those few milliseconds could give a torn read. The result is DatabaseError (exit 1) or a wrong refusal decision, never index damage. A stale read is not possible: with no -wal, the main file is complete. A main file whose -wal was lost (`h-crash2`) is refused, never accepted. No action needed; documenting the gap is enough.
- **The 500 path in `compare_view` logs nothing.** That is safe, but nobody can tell why the page failed. Log `type(e).__name__` to the server log.
- **Unicode bidi and other format characters pass `safe()`.** For example U+202E in a typed key or a model name can reorder the text the terminal shows. `|` in a model name can still look like an extra column on the same line, but it cannot start a new row. Optional fix: also escape Unicode category Cf and U+2028/U+2029.
- **Pre-existing: -wal and -shm made by the server are 0644.** Store chmods only `index.sqlite`, after SQLite has already created them. The 0700 home mitigates this.
- **INFO-1 items 2-4 from round 1 are unchanged:** the guard 404 without headers, `testserver` allowed as a Host, and cross-site GETs costing CPU.

### Code reviewed
- `<awb-r22>/console/agent_console/store.py`: ingest marker, `_clear_scan_markers`, `_pid_alive`, `index_check`
- `<awb-r22>/console/agent_console/server.py`: `compare_view`, the 503 check and the 500 path. The 503 check and the figures read in one snapshot, so a marker commit cannot fall between them.
- `<awb-r22>/console/agent_console/compare_cli.py`: symlink refusal and exception handling. `_error` only ever carries an exception class name.
- `<awb-r22>/console/agent_console/compare_format.py`: `safe()`
- `<awb-r22>/console/agent_console/compare.py`: `_s`, `_records`

### Evidence
- Scripts: `/tmp/sec-r22b/bin/r.sh`, `/tmp/sec-r22b/bin/srv.sh`, `/tmp/sec-r22b/bin/guard.sh`, `/tmp/sec-r22b/bin/t500.py`
- Outputs: `/tmp/sec-r22b/out-bad2.json`, `/tmp/sec-r22b/out-bad2.txt`, `/tmp/sec-r22b/out-esc.txt`, `/tmp/sec-r22b/p1.html`
- Server logs: `/tmp/sec-r22b/srv1.log`, `/tmp/sec-r22b/srv2.log`, `/tmp/sec-r22b/srv3.log`
- Homes: `/tmp/sec-r22b/h-*`, `/tmp/sec-r22b/srv*`
- Checkpoint: `/tmp/sec-r22b/checkpoint.md`. No checkpoint path was given, so I wrote it in /tmp, outside the repo.

---
# Security re-check, round 2 (after extra loop 5) — verbatim summary of verdict and findings (copied by the coordinator)

**Security re-check EXP1-R22C, round 2. Verdict: PASS**

NEW-2 and NEW-3 are fixed. The argparse echo fix works. The None-id filtering in compare.py holds. The new code adds one Low finding (NEW-5) and one informational note (NEW-6). Neither is above Low, so nothing goes to the `approver`. I did not re-open NEW-1, because answer 48 accepts it as a known limit. It still shows up when the CLI runs on root `/tmp/sec-r22b/roots/x` (exit 1, AttributeError), which is what that ruling expects.

Lane: no console server started (in-process TestClient and CLI only); homes new 0700 dirs under /tmp/sec-r22c/; no request of any kind to 8790; ~/.agent-console, ~/.claude, ~/.claude/projects not touched; HEAD 0891a04, same 18 entries; no repo edits.

NEW-2 fixed: yes — scan:99999999999999999999 -> idle, no error, removed, page 200; scan:1 with ISO start 2 h old (aware or naive) -> removed, page 200; scan:1 10 min old -> kept, 503 (inside the 1 h bound, Q-058); dead pid scan:99999, scan:abc, scan:-1, year-1 +14:00 -> removed, 200; scan:1 with value x -> kept, 503 (already decided, Q-059 L5-D1). Optional hardening: treat an unreadable or future time as stale (needs a hand-written row in the 0700 home; not a finding).
NEW-3 fixed: yes — index.sqlite + index.sqlite-wal copied without -shm into new homes, CLI with AGENT_CONSOLE_TZ=UTC -> exit 2, one refusal line "(nothing written)", home listing and SHA of each file unchanged, no -shm created.
Temp-copy review: tempfile.TemporaryDirectory() under $TMPDIR, never in the console home; dir 0700; index.sqlite 0600, index.sqlite-wal 0644 (mode copied), -shm 0600 inside the temp dir; deleted on the refusal, SpecialFileError and OSError paths; no home writes.
Argparse echo fix: yes — extra positional with ESC/BEL/newline -> exit 2, stderr exactly 2 lines, all escaped, 0 ESC/BEL bytes, empty stdout; --json=\e[31m and --json\r\nFAKE escaped, 2 lines; missing KEY_B usage + one line; unknown-key line stays escaped.
compare.py None-id filtering: OK — ids absent or list/dict/int never pair through asks, rejected or hb_ids; control with string ids gives the expected gap.
SEC-1 regression: bad2 root, fresh home -> --json exit 0, empty stderr, index 0600.

**NEW-5 (Low, about CVSS 1.9, AV:L/AC:L/PR:H/UI:N/S:U/A:L). Route: `store.index_check`, the temp-copy branch, used by `python -m agent_console compare`. The copy has no size limit and follows symlinks and devices.**
- Business impact: if someone plants a `-wal` file in the console home, the next CLI run can fill the temp disk (`$TMPDIR`). The index is not damaged and no data leaves the machine.
- Steps: (1) new 0700 home with a real index.sqlite and `ln -s /dev/zero <home>/index.sqlite-wal`, no -shm; (2) `AGENT_CONSOLE_TZ=UTC python -m agent_console compare PROJ-123 PROJ-301` with `ulimit -f 20000`.
- Actual: shutil.copy follows the symlink and copies from /dev/zero until the file-size limit stops it with OSError (exit 1); with a 200 MB limit it reached the limit in under 2 s; without a limit it would write until $TMPDIR is full. A legitimate large -wal and index are also copied in full on every CLI run in this state. A SIGKILL during the copy leaves the copy in $TMPDIR (0700 dir). The temp dir was removed on every OSError and SpecialFileError run.
- Expected: a read-only check never writes an unbounded amount of data, and never reads a device or a symlink target as the index.
- Limit: planting needs write access to the 0700 home (same user). A FIFO -wal is already refused (SpecialFileError, exit 1).
- Fix: os.lstat both files before copying and refuse (exit 2, nothing written) unless each is a regular file and not a symlink; copy with a size bound (refuse over N MB, or check st_size against free space); optionally O_NOFOLLOW.

**NEW-6 (Informational):** the -wal-without--shm check runs before the file is opened (time-of-check / time-of-use, same kind as NEW-4). Needs a crash or manual deletion at that exact moment. No action beyond a code comment.

Still open from earlier rounds, unchanged: Unicode Cf/bidi characters pass safe(); INFO-1 items 2-4.
Evidence: /tmp/sec-r22c/bin/t2.py, new3.sh, peek.py, gaps.py, gaps2.py; homes /tmp/sec-r22c/h-*; listings /tmp/sec-r22c/before.txt, after.txt; checkpoint /tmp/sec-r22c/checkpoint.md.
