PASS

# analyst report: EXP1-KITC

Path: `docs/agents/work/EXP1-KITC/analyst-as-is.md`

## Summary
Read the ticket-key, session indexing, usage/pricing, wait/time, flag, server and route code and wrote 24 observed rules to `docs/requirements/console.md`. There is no /compare route, no CLI (python -m agent_console only starts the server) and no per-model aggregation or ticket-level "active time"; the brief's wait definition conflicts with the code. Nine questions are filed for the delta step.

## Mode and area
as-is, console (CON)

## Rules added or changed
| ID | Status | Statement (short) | Source | Scope |
|---|---|---|---|---|
| CON-001..003 | observed | Key sources, order, bracket and plain patterns | tickets.py:34-113 | as-is |
| CON-004 | observed | Sub-run inherits parent's key in force at start | store.py:~512 | as-is |
| CON-005 | observed | Main session takes key of >=80% of its sub-runs | tickets.py:146-167 | as-is |
| CON-006 | observed | Ticket = runs with that effective key; no key -> "(no ticket)" | ctq.py:137 | as-is |
| CON-007, 008 | observed | Log root, index, rescan; project scope | config.py, store.py | as-is |
| CON-009, 010 | observed | One usage row per API message; token kinds stored, no per-model total | store.py:383 | as-is |
| CON-011..013 | observed | Pricing: substring match, tier fallback, over-100K, unpriced = zero + counter, file load | pricing.py, pricing.yaml | as-is |
| CON-014, 015 | observed | cost_main / cost_sub exist; `rounds` = API messages | ctq_pages.py:94 | as-is |
| CON-016, 017 | observed | "returned" flag; reject_count; no "failed" field | flags.py:125-145 | as-is |
| CON-018..021 | observed | calendar/working time, human/ask/parked waits (no 60 s floor, no stop-reason), main-only waits, per-run time | ctq.py, timing.py | as-is |
| CON-022, 023 | observed | JSON endpoints and hash router, no /compare; unknown key gives 200 empty | server.py, ctq_api.py, ctq_pages.py:253 | as-is |
| CON-024 | observed | Server local-only with security headers | server.py:32-110 | as-is |
| CON-025 | observed | `python -m agent_console` has no arguments | __main__.py | as-is |
| CON-026 | observed | JSON holds raw floats; key order not sorted explicitly | ctq_pages.py | as-is |

The map has 26 rules, CON-001..CON-026; the table groups them by range.

## Questions filed
See `docs/requirements/QUESTIONS.md` (9 questions: wait definition, failed run, repeat rounds, active role time, per-model tokens/unpriced, same-ticket two runs, share when sub cost is zero or several mains, unknown-key meaning, scope/period).

## CONFLICT / UNVERIFIED
- CONFLICT: brief (wait = gap after a stop for a person, under 60 s = 0) vs code (every human gap, no stop-reason read, parked over 2 h split out).
- CONFLICT: brief "tokens per model" / "active role time" / "failed" / "repeat rounds" vs code: none of these exist as fields; closest are listed in rules above.
- UNVERIFIED: browser-side rounding/formatting in console/static/*.js (ctq-lib.js) not read; `parser.py` handling of stop_reason was grepped only (no match), not read line by line.
- UNVERIFIED: store.py scope classification line range cited approximately.

## Size
L, for the delta step: new page, API route, CLI with subcommand dispatch (none today), and several undefined measures (wait, failed, active time) that need decisions.
About 8 files touched (server.py, __main__.py, new compare module, static JS, tests, docs) across data read, pricing and time logic.

## Security triggers
as-is: none (no change made). For the later delta, expected: new or changed endpoints (new /compare route and API with user-supplied keys), personal data (none expected; ticket keys only), logging of request data (none expected).
