FAIL

# verifier report: EXP1-KITC

## Summary
All gates were run again from scratch. Lint, both test suites and the code are green and better than baseline. The strict rule-coverage gate exits 1: it reports 4 unknown rule IDs (AUDIT-001/002/003/999), all in `kit/tests/test_rule_coverage.py` (fixture strings of the tool's own tests, not changed by this ticket). In a throwaway copy without `kit/tests` the strict gate exits 0. The verdict is FAIL only because the gate as specified is not green. The human decides whether this is acceptable (see Open items).

## Gate results
| Gate | Exact command | Result | Baseline | Same or worse? |
|---|---|---|---|---|
| Lint | `console/.venv/bin/python -m ruff check .` (repo root) | All checks passed | clean | same |
| Console tests | `.venv/bin/python -m pytest tests -q -p no:cacheprovider` (in `console/`) | 554 passed, 1 warning (Starlette deprecation about httpx in the TestClient, from the library) | 445 passed | better (+109 tests, no failure or skip) |
| Install tools and kit tests | `console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider` (root) | 49 passed | 49 passed | same |
| Rule coverage strict | `python3 <workbench>/kit/tools/rule_coverage.py . --strict --scope EXP1-KITC` | exit 1. Rules: 55 (console: observed=26, new=29). "Tests pointing to UNKNOWN rule IDs": AUDIT-001, AUDIT-002, AUDIT-003, AUDIT-999, all in `kit/tests/test_rule_coverage.py` | none recorded | UNVERIFIED whether the base also gives exit 1 (the map is untracked, so no base run was possible); `kit/tests` is unchanged by this diff |
| Rule coverage strict, copy without `kit/tests` | same command on a /tmp copy with `kit/tests` removed (copy deleted afterwards) | exit 0, no unknown IDs, no uncovered rule listed | | diagnostic only |

Working tree: `git status` shows only `console/agent_console/__main__.py`, `server.py` modified; `compare.py`, `test_compare.py`, `docs/requirements/` untracked. HEAD is 0891a04. Nothing committed or pushed.

## Merge request text
### What changed
Adds a ticket comparison report to the console. A page `GET /compare?a=<KEY>&b=<KEY>` and a CLI `python -m agent_console compare <KEY> <KEY> [--json]` (new `console/agent_console/compare.py`; small edits in `__main__.py` and `server.py`). For each ticket, including its main sessions, it shows role runs (total, failed, repeat rounds), tokens per model (input, output, cache write, cache read), cost per model and in total from `pricing.yaml`, wall time, active role time, wait time on a person, and the main session cost as a share of the sub-agents' cost, plus a difference column (b minus a, b divided by a). Unknown key: error on the page, exit code 2 in the CLI. No main session shows "no main session". JSON has sorted keys and raw values; the page rounds. No new dependencies.

### Rules covered
Map `docs/requirements/console.md` (area console, scope EXP1-KITC): 55 rules, 26 observed and 29 new. The strict gate lists no uncovered in-scope rule. The new rules include CON-027 to CON-055 touched by this ticket (see the map for the exact list).

### Tested
- ruff: clean.
- console suite: 554 passed (baseline 445); `console/tests/test_compare.py` holds the new cases.
- install tools and kit: 49 passed (baseline 49).
- Reviewer (reviewer-4.md): PASS. Security (security-4.md): PASS, no high or medium findings, 2 low notes (CLI echoes keys raw; 404 vs 200 reveals whether a key exists).
- Not tested here: the live console and real `~/.claude/projects` logs (see L3).

### Open items
- Strict rule-coverage exit 1 caused by the AUDIT-* fixture IDs in `kit/tests` (see below).
- Human rulings (answers.md item 44): denial fails a run only if no normal final reply follows; a non-error spawn without a run file counts as a run, not failed.
- Wait time and denial detection were only tested on fixtures, not on real logs.

## L2 checks (scratch services, run by the verifier)
| # | Check | Commands | Result |
|---|---|---|---|
| 1 | none: PROJECT.md has no scratch service recipe | | not applicable |

Cleanup: removed /tmp/vcopy and the temporary output file; no service started.

## L3 checklist (for the human)
Use a throwaway console, not your running one. Replace K1 and K2 with two real ticket keys that have sessions under `~/.claude/projects/`; K0 is a key that does not exist.
| # | Action (one) | Expected result |
|---|---|---|
| 1 | In `console/`, run `AGENT_CONSOLE_PORT=8791 AGENT_CONSOLE_HOME=/tmp/awb-l3 make start` (or the equivalent `python -m agent_console` with those variables) | The console starts; `http://127.0.0.1:8791/health` answers ok |
| 2 | Open `http://127.0.0.1:8791/compare?a=K1&b=K2` | Two ticket columns plus a difference column; tokens rounded to thousands, dollars to cents, time to minutes |
| 3 | Compare the total cost of K1 on the page with the same ticket's cost on the existing ticket page | The numbers agree |
| 4 | Look at the role-run rows for K1 | Total, failed and repeat-round counts look right for what you remember of that ticket |
| 5 | Look at the wait-time row for a ticket with long pauses for you | The value is plausible; gaps under 60 s do not add up |
| 6 | Check that the kit runs that end with a SubagentHandback are not shown as failed | Failed count does not include normally finished sub-agent runs |
| 7 | Open `http://127.0.0.1:8791/compare?a=K1&b=K0` | A clear error about the unknown key (HTTP 404) |
| 8 | Open a ticket that has no main session as `a` | The row shows "no main session", not 0 |
| 9 | In `console/`, run `.venv/bin/python -m agent_console compare K1 K2` | A text table with the same numbers as the page |
| 10 | Run `.venv/bin/python -m agent_console compare K1 K2 --json` twice and diff the outputs | Identical output, sorted keys, raw (unrounded) values |
| 11 | Run `.venv/bin/python -m agent_console compare K1 K0; echo $?` | Error message and exit code 2 |
| 12 | Run `.venv/bin/python -m agent_console` with no arguments and stop it | It still starts the server as before |
| 13 | Decide on the strict rule-coverage result (4 unknown AUDIT-* IDs from `kit/tests`) | Accept as a fixture artefact, or ask for a scope or marker change |
| 14 | Stop the throwaway console and remove `/tmp/awb-l3` | Port 8791 is free |

## Open items (UNVERIFIED / CONFLICT from all reports)
- GATE: `rule_coverage --strict` exits 1 because of AUDIT-001/002/003/999 in `kit/tests/test_rule_coverage.py`. Not caused by this diff as far as observed; UNVERIFIED whether the base behaves the same.
- UNVERIFIED (security-4): whether the tests with planted SENTINEL strings fail on a leak.
- UNVERIFIED (security-4): the bind and host restrictions, unchanged by this diff.
- UNVERIFIED (test-designer-r3): denial wordings beyond the two known prefixes.
- CONFLICT (test-designer-r3, analyst, resolved by the human in item 44): any denial vs a denial after the last normal reply. The code follows the human's ruling; one test pins it (`test_normal_reply_after_a_denial_clears_it`).
- Security run 3 wrote no report file (verdict in the reply only); noted in status.md. security-4.md exists.
- status.md: answers.md items 24-36 were applied in the re-plan; no rule status changed by agents (map status is the human's).
- Two low security notes (CLI echoes keys raw; 404 vs 200 reveals key existence).
