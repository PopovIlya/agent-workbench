0891a04 + uncommitted change (fingerprint db8b5d99b8c0, diff+untracked excl. docs/agents/work) · re-check 2 done · next: none (PASS) · open bugs: 0

0891a04 + uncommitted change (fingerprint 97cfe643792c, diff+untracked) · re-check done · next: none (PASS) · open bugs: 0

0891a04 + uncommitted change (fingerprint 97a37acdd149) · hostile verify done · next: builder fixes HV-1, HV-2 · open bugs: 2

Verdict: **FAIL** (1 Medium, 1 Low open in the ticket's own work).
Lane: two throwaway consoles (ports 54961, a second on a new home for the first-index case), AGENT_CONSOLE_HOME=/tmp/hv22/home*, LOG_ROOT=/tmp/hv22/logs1 (synthetic, ~1800 files), REPO=/tmp/hv22/repo1. Both consoles stopped by me (pids 34341, 36689). Health checked by GET /health before the attacks. No repo file edited. Evidence: /tmp/hv22 (out_*.html, pa_*.html, f_*.html, g_diff_*, gittrace*.log); harness /tmp/hv22/scripts.
Markers planted in prompts, replies, tool inputs (description, prompt, Bash command), tool results (denial text), api_error message, sub-agent text: MRKPROMPT, MRKREPLY, MRKUSER2, MRKTOOLIN, MRKTOOLINPROMPT, MRKTOOLRES, MRKSUBTEXT, MRKSUBBASH, MRKAPIERR, secretXYZ, `<script>`, `<b>`.
Gates: test_case_files / claims / tracker: not declared in PROJECT.md, skipped.

## Bugs

### HV-1 (Medium, CON-027 / CON-013 / CON-014, case HV-P20) A known key is shown as unknown (404) and with wrong figures while the console ingests
Steps to reproduce:
1. Console on a throwaway home, already indexed (not the first index).
2. Add new logs for a ticket: main session `[EXP1-Y5] ...` with Agent spawns and their sub-agent files (/tmp/hv22/scripts/gen.py logs1 800 Y).
3. POST /api/rescan, and poll `GET /compare?a=EXP1-AAA&b=EXP1-Y5` every 0.25 s (no CLI running).
Actual: `404 200 404 404 200 200 ...`. The 404 pages say "Unknown ticket key: EXP1-Y5" for a key that is in the logs; the 200 in between shows EXP1-Y5 with Main sessions 0, Failed runs 1, Tokens input 0k (settled: 1 main session, 2 failed, 2k). Evidence /tmp/hv22/pa_1..5.html vs pa_60.html.
Cause (observed): `unknown_keys` / `_ticket` mix raw tables that `ingest` commits every 20 files (tool_calls, sub_meta: commit at i=0) with `runs`, which is rebuilt only at the end of the scan. A spawn is "without run file" until its sub_meta row lands, then neither spawn nor run until rebuild. Existing pages read only `runs` and do not show this.
Expected: a key that is in the logs is never reported unknown, and no mixed half-scan figures are shown (e.g. read only consistent data, or answer as for a scan in progress). How to answer during a non-first scan is a product ruling for the product_owner (CON-010 v2 covers only the first index).

### HV-2 (Low, CON-027 "one line" / CON-035 "as text", case HV-C10) A CLI key with a newline or terminal escape is printed raw on stderr
Steps: `python -m agent_console compare $'NOPE\nINJECTED-LINE' EXP1-BBB`; also `$'\e[2J\e[31mFAKE' EXP1-BBB`.
Actual: exit 2, stdout empty, but stderr is two lines (`compare: unknown ticket key: NOPE` / `INJECTED-LINE`); the escape bytes ESC[2J ESC[31m reach the terminal (clears it, colours red). A key can forge a second message line.
Expected: exactly one line naming the key, the key shown as text (control characters escaped, e.g. repr-style), as the page does with markup.

## Attacks: page (/compare)
| Case | Input | Expected (rule) | Actual | Result |
|---|---|---|---|---|
| HV-P01 | Host: evil.com / evil.com:<port> / 127.0.0.1 (no port) / 127.0.0.1:<port>.evil.com | 404 guard JSON (CON-033) | 404 `{"detail":"Not found."}` all four | PASS |
| HV-P02 | Host: localhost:<port> | served | 200 | PASS |
| HV-P03 | a=`<script>alert(1)</script>`, b=`"><img src=x onerror=alert(2)>` | 404 naming both, as text (CON-027, CON-035) | 404, both escaped `&lt;script&gt;`, `&quot;&gt;&lt;img` | PASS |
| HV-P04 | a=U+202E+EXP1-AAA, b=emoji | 404 naming both, text | 404, both shown as text | PASS |
| HV-P05 | a=`EXP1-AAA%00` | not trimmed -> unknown | 404 naming it (NUL byte in body, no markup) | PASS (note: control chars echoed raw in HTML text) |
| HV-P06 | a=`%C2%A0` (NBSP), a=`%09` (tab) | missing -> 422 (CON-034 v4: only spaces) | 422 "Missing parameter: a" | PASS (note: all Unicode whitespace counts as missing, not only spaces) |
| HV-P07 | a=&b= ; no parameters | 422 naming a, b | 422 "Missing parameters: a, b" HTML | PASS |
| HV-P08 | a=EXP1-ZZZ&a=EXP1-AAA&b=... | last value wins (Q-029) | 200 for EXP1-AAA | PASS |
| HV-P09 | extra c=, swap=, a[]= | ignored | 200 | PASS |
| HV-P10 | a=b=EXP1-QQQ (unknown) | named once | "Unknown ticket key: EXP1-QQQ" | PASS |
| HV-P11 | a=exp1-aaa ; a=` EXP1-AAA` | no case folding, no trim -> 404 | 404 | PASS |
| HV-P12 | POST / PUT / DELETE / OPTIONS / HEAD | no other method (GET only) | 415 (guard) / 405 / 405 / 405 / 405, no page | PASS (HEAD 405 = same as /health) |
| HV-P13 | /compare/ ; /%63ompare ; //compare ; /Compare ; /compare;x ; /static/../compare | no other route | 307 to /compare on the allowed host; 200 (decoded); 404 x4 | PASS |
| HV-P14 | a=`x' OR 1=1--`, b=`%` | unknown (bound params) | 404 naming both | PASS |
| HV-P15 | key 1k / 60k chars; 200k; 2M | no crash | 404 / 404 (escaped echo) / 400 from uvicorn / not sendable; server stays healthy | PASS |
| HV-P16 | 500 extra parameters | ignored | 200 | PASS |
| HV-P17 | a=`A%0D%0ASet-Cookie: x=1` | no header injection | 404, no Set-Cookie header | PASS |
| HV-P18 | security headers on 200 / 404 / 422 / 405 | CSP, nosniff, DENY, no-referrer, no-store (CON-033) | all present | PASS |
| HV-P19 | first index on a new home (1800 files) | 503 one message, then 200 (CON-010 v2) | 14 x 503 "building its first index", then 200 | PASS |
| HV-P20 | page polled during a later (non-first) ingest | known key never unknown | false 404 and partial figures | **FAIL (HV-1)** |
| HV-P21 | raw text: grep all page bodies (200, 404, 422, 503, mid-scan) for markers | none (CON-035) | 0 hits | PASS |
| HV-P22 | model name `"><img src=x onerror=alert(9)>MRKMODEL` | shown, escaped in text and attribute | escaped, 0 raw `<img` | PASS |

## Attacks: CLI
Index state compared before/after: sha256 of index.sqlite (and -wal when non-empty), `PRAGMA user_version`, every meta row, runs count (read with `?immutable=1`).
| Case | Input | Expected (CON-011, CON-027, CON-034) | Actual | Result |
|---|---|---|---|---|
| HV-C01 | AGENT_CONSOLE_TZ=UTC / Europe/madrid / Not/AZone | exit 2, one line "another time zone", nothing written | exit 2, exact line, stdout 0 B, index unchanged | PASS |
| HV-C02 | AGENT_CONSOLE_KEY_PATTERNS=X-[0-9]+ | "another key patterns" | as expected, unchanged | PASS |
| HV-C03 | AGENT_CONSOLE_REPO=/tmp/hv22, nonexistent dir | "another checkout" | as expected, unchanged | PASS |
| HV-C04 | REPO with trailing / or /../ (same dir); KEY_PATTERNS of only spaces; home via symlink | same values -> refresh, exit 0 | exit 0 | PASS |
| HV-C05 | tz + key patterns + checkout differ | all named, fixed order | "time zone, key patterns, checkout" | PASS |
| HV-C06 | index copied from home A into home B | "another console home" | as expected, unchanged | PASS |
| HV-C07 | meta repo_root deleted / all meta deleted | "does not record its ..." line | exact lines | PASS |
| HV-C08 | tz differs + repo_root missing | "built with another time zone, checkout" | as expected | PASS |
| HV-C09 | user_version=9 | "another schema version" | as expected, unchanged | PASS |
| HV-C11 | not-a-database file (with a marker) | exit 1, one line naming the class | exit 1 "(DatabaseError)", file unchanged, marker not printed | PASS |
| HV-C12 | another process holds BEGIN EXCLUSIVE | exit 1, class only | exit 1 "(OperationalError)", unchanged | PASS |
| HV-C13 | 0-byte index.sqlite | refusal, nothing written | exit 2 "another schema version, time zone, key patterns, console home, checkout"; still 0 bytes | PASS (note: wording says "built with another" for an empty file; per the rule) |
| HV-C14 | refusal with an unknown key / with one key | refusal first / usage first | as expected | PASS |
| HV-C15 | three keys; `-EXP1`; `--js`; `--json=1` | usage, exit 2 | usage, exit 2, index unchanged | PASS |
| HV-C16 | `-- --json EXP1-BBB` | `--json` taken as a key -> unknown, exit 2 | as expected | PASS |
| HV-C17 | "" ; "   " "  " ; tab | usage, exit 2 | "empty key: KEY_A[, KEY_B]", exit 2, unchanged | PASS |
| HV-C18 | NOPE-1 NOPE-1 ; NOPE-2 NOPE-1 ; exp1-aaa ; ` EXP1-AAA` ; `@/etc/passwd` ; 100k chars ; markup ; RTL/emoji | one line, exit 2, stdout empty | as expected (named once; a first) | PASS |
| HV-C10 | key with newline / ESC sequences | one line, text | two lines / raw escapes | **FAIL (HV-2)** |
| HV-C19 | -h ; --json twice | help exit 0 ; JSON exit 0 | as expected | PASS |
| HV-C20 | no fetch: AGENT_CONSOLE_CLAIMS_REPO=/tmp git repo, NO_FETCH unset, GIT_TRACE | no `git fetch` | 0 fetch lines in 34 trace lines; positive control (scope.refresh_claims directly) traces 1 fetch | PASS |
| HV-C21 | no-argument start | server as today | console started with no argv, /health ok (both consoles) | PASS |
| HV-C22 | raw text: grep text, JSON, stderr of all runs | none | 0 hits | PASS |
| HV-C23 | 3 CLIs (same home as the running console) during a console ingest + page polling | exit 0 or exit 1 one line; console alive | 3 x exit 0, identical 4960 B JSON; console healthy, no scan error | PASS |

## Observations (not bugs)
- O-1: on the first refusal after a write run, the guard's `?mode=ro` open leaves an empty `index.sqlite-wal` (0 B) and `-shm`; index.sqlite bytes, user_version, meta and runs are unchanged. The design names -shm only.
- O-2: page and CLI treat any Unicode whitespace (tab, NBSP) as "only spaces" (missing). Matches the Q-023 reason; the rule text says spaces.
- O-3: page echoes control characters (NUL, U+202E) as raw text inside <code>; no markup possible.


## Re-check (2026-11-05, same verifier, fresh lane)
Verdict: **PASS**. HV-1 and HV-2 fixed; sample of earlier attacks: no regression. Open bugs in the ticket's own work: 0.
Lane: consoles on ports 56160 (home /tmp/hv22r/home) and a second one (home /tmp/hv22r/home2, first index), LOG_ROOT=/tmp/hv22r/logs (synthetic, up to 21007 files), REPO=/tmp/hv22r/repo1. Both stopped by me (pids 52521, 63033); ports free. Health GET ok. No repo file edited. Evidence /tmp/hv22r (p20*, cli2, cli3, dead, both, p19, c); harness /tmp/hv22r/scripts. Touched tests: 358 passed.
Pollers read /compare every ~10 ms (poll2 also reads /api/status state); sequences are code:bodyhash/state x count.

| Case | Input | Expected (rule) | Actual | Result |
|---|---|---|---|---|
| HV-P20 | 800 new EXP1-Y sessions, POST /api/rescan, poll a=EXP1-AAA&b=EXP1-Y5 | pre-scan 404, then only 503 (v3 text) or the settled 200 (CON-010 v3, Q-055) | 404x66 503x60 200x757 503x52 200x307; one 200 body only (Y5: 1 main session, 2 role runs); no 404 after the first 503 | PASS |
| HV-P20b | 4x200 W sessions written while the 30 s loop runs, two pollers (new/new, new/old key) | same | 404 then 503/200 alternating, one 200 body per pair, no 404 after the first 503 | PASS |
| HV-P23 | CLI refresh in another process (5000 new files) while polling | 503 while the CLI scans, server idle | 503/idle x221, then 200; CLI exit 0, same figures | PASS |
| HV-P24 | CLI kill -9 1.5 s into its scan (marker scan:<cli pid> seen) | 503 until the next scan finishes (Q-056) | 503/idle x1316 (~20 s) until the server's loop scan, 503/indexing, then settled 200; marker cleared | PASS |
| HV-P25 | planted meta rows scan:999999 and scan:abc, server idle | 503 until next scan, then cleared | 503/idle x1433, 503/indexing, 200; rows gone | PASS |
| HV-P26 | CLI scan and server rescan at the same time | only 503 then 200; CLI 0 or 1 one line | 503 (idle/indexing/idle) then 200; CLI exit 0, stderr empty | PASS |
| HV-P19 | first index on a new home, 21007 files | 503 v3 text, then 200 | 503 x2610 (one body, v3 text), then 200 identical to the other console's page | PASS |
| HV-C10 | keys with \n, \r, ESC[2J, OSC title, C1 0x9b, DEL, VT/FF, same key twice | one stderr line, control chars as text (CON-027, CON-035) | exactly 1 line each, every C0/C1/DEL shown as \xNN, 0 ESC bytes, stdout 0 B, exit 2 | PASS |
| regress P01/P02/P03/P07/P10/P11/P12/P17/P18/P21 | as before | as before | same results as the first run; 0 marker hits in all new bodies and CLI outputs | PASS |
| regress C01/C02/C03/C05/C06/C11/C15/C16/C17/C18/C20 | as before | as before | same results; refusals unchanged index; no git fetch with a claims repo set | PASS |

Observations (not bugs):
- O-4: every scan, also one with no new file, now gives ~0.5-1.5 s of 503 (each 30 s loop and each POST /api/rescan). This is what CON-010 v3 asks.
- O-5: CLI escape is not reversible: a typed literal `X\x0aY` and a real newline print the same. One line holds, no forgery of a second line.
- O-6: U+2028 and U+202E (not C0/C1) are printed raw by the CLI; one line in byte terms; a terminal may reorder text with U+202E.
- O-7: a marker whose pid is alive but not scanning (e.g. scan:1, pid reuse) keeps 503 until that process ends: the documented residual risk (Q-056).
- Not tested: a server scan that ends in an error (no simple way to make ingest raise); covered by the same marker path as the killed CLI.

## Re-check 2 (2026-11-05, same verifier, fresh lane, final version)
Verdict: **PASS**. Open bugs in the ticket's own work: 0.
Lane: one console on port 49411 (pid 80097, home /tmp/hv22r2/home), LOG_ROOT=/tmp/hv22r2/logs (synthetic, up to ~15.5k files), REPO=/tmp/hv22r2/repo1; CLI homes /tmp/hv22r2/home2..6. GET /health ok before the attacks. Console and the helper `sleep` (pid 84417) stopped by me; port free. No request to 8790. Evidence /tmp/hv22r2 (p20*, p24*, pm1-3*, c/); harness /tmp/hv22r2/scripts (c10.sh, creg.sh).
Sequences are code:bodyhash/state x count (poll every ~10 ms).

| Case | Input | Expected | Actual | Result |
|---|---|---|---|---|
| HV-P20 | 800 new EXP1-Y sessions, scan by the 30 s loop, poll a=EXP1-AAA&b=EXP1-Y5 | pre-scan 404, then only 503 or the settled 200 | 404x1621, 503 idle x5, 503 indexing x51, 200 x342; one 200 body (Y5: 1 main session) | PASS |
| HV-P20b | 600 new EXP1-Z sessions, POST /api/rescan (started:true), poll Y5/Z7 | same | 404x101, 503x58, 200x581, 503x49 (loop scan), 200x61; one 200 body | PASS |
| HV-P24 | CLI compare, 12.5k new files, kill -9 at 1.5 s (marker scan:82369 seen) | 503 until the next scan, marker cleared | rc 137, stdout/stderr 0 B; marker still there 3 s later; 503 idle x1316, 503 indexing x179, settled 200 x281; 0 markers at end | PASS |
| HV-P25b | planted scan:999999 (dead), scan:abc, scan:-5 (unparsable), scan:<live pid> 2 h old | 503 until next scan, then all cleared | 503 idle x1579, indexing x131, 200 x176; all four rows gone, live pid still running | PASS |
| HV-P27 | planted scan:<live pid> with a fresh time | survives a scan (503 holds); cleared once the pid ends | 503 through a full scan (idle/indexing/idle), row kept; after the pid stopped: next scan cleared it, 200 | PASS |
| HV-C10 | unknown keys with \n, ESC[2J ESC[31m, \r, DEL | exactly 1 stderr line, escaped, exit 2, stdout empty | 1 line each, \x0a \x1b \x0d \x7f; 0 control bytes | PASS |
| HV-2b | bad third argument `EVIL\nINJECTED-LINE`, `ESC[2J ESC[31mFAKE`, mixed \n OSC BEL \r 0x9b; `--bad\nINJ`; `--json=ESC[31m\n` | usage + exactly one escaped error line, exit 2 | usage line + 1 error line each, all escaped (0x9b shown as \udc9b), 0 control bytes in stderr, stdout 0 B | PASS |
| C01/C02/C03/C05 | TZ=UTC; KEY_PATTERNS=X-[0-9]+; REPO=/tmp/hv22r2; all three | one refusal line naming them, exit 2, nothing written | exact lines; every file in the home byte-identical, no new file | PASS |
| C06 | index copied to another home (also with a bad third argument) | "another console home" / usage | as expected; home unchanged | PASS |
| NEW-3 | -wal present, -shm absent (WAL holds a changed meta value) | refusal reads the -wal values, no -shm created | refusal reflects the -wal-only value (home), home files byte-identical, no -shm | PASS |
| raw text | grep MRK*/secretXYZ in all bodies and CLI outputs | none | 0 hits | PASS |

Observations (not bugs):
- O-8: a 0x9b byte that is not valid UTF-8 is shown as `\udc9b` (surrogate escape), not `\x9b`; still text, one line.
- O-9: before a scan writes its marker, a not-yet-indexed key gives 404 (the index does not have it yet); this is the pre-scan state, not a half-scan figure.
- Not re-tested here: "absent ids never pair" (covered by the builder's tests, not an attack surface of this run).
- Not my processes, left alone: consoles pid 42470 (port 52209) and 46021 (port 52440), running ~27 h; another session's mutation run under /tmp/cr7-r22c.
