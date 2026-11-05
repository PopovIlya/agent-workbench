# Design check 1 (test cases), EXP1-R22C — REJECT (written by coordinator from the checker's reply)
Traceability complete: 227 items + CI-022-30 = 228 cases (EP 136, DT 47, BVA 31, ST 11, CL 3); versions current; markers present; oracle arithmetic recomputed and holds.
BLOCKING
1. TC-ST-01..11: keys A, B, W are not keys (DEFAULT_KEY_PATTERN [A-Z][A-Z0-9]+-[A-Z0-9]+). Use real keys (e.g. EXP1-AAA, EXP1-BBB); update header/meta assertions in ST-01..03. Same for EP-026-05, -06, -08 (literal `compare a b`).
2. EP-029-16: fixture contradicts itself (1500/2500 tokens vs input 1_234_000/2_500_000 -> 1234k/2500k). Put 1500/2500 in one row (e.g. main input), make dollars consistent, recompute every string; state how wall time is built (100 s, 400 s from record timestamps).
3. EP-011-17: can pass without proving no-fetch (refresh_claims returns early if time.time()-_last_fetch<600; fetches via Store.repo; non-git tmp never fetches). Fix: monkeypatch scope._last_fetch=0; env.repo a git checkout with an origin; positive control (without NO_FETCH and no CLI, refresh_claims shows a fetch argv in the spy), then CLI asserts none. Drop the redundant "restore" step.
4. Status-only oracles: EP-027-01..04, -12 (add 200 body: th.a/th.b keys, tr[data-row="runs.total"] cells, "no main session" where it applies; CLI stdout header line). EP-033-04, -05 (200: <table class="compare">; 404: <p class="error">Unknown ticket key: <code>ABC-404</code>.</p>).
MINOR
5. EP-032-02: base is 0891a04, not a549ddc+profile; use `git archive 0891a04 console` into its own tmp folder, fixture env, golden dump written once; remove "run the two existing test files" (dup of CI-032-01).
6. EP-032-04: compare with the literal POST set asserted in test_server.py (~line 50).
7. EP-029-18: usage(...) defaults out=20; specify usage(1499, 0); pytest.approx.
8. BVA-001: DROP (no boundary after Q-039; EP-012-01 already covers "old record counts"). qa.md: retire CI-012-03 / merge into EP-012-01 with a Q-039 note.
9. qa.md stale: add CI-022-30; CON-022 v10 -> v11; CI-012-03 retire note; totals.
10. Multi-move cases: TC-ST-07 (4 variants), EP-022-12, EP-022-13, EP-022-21, BVA-006: keep the primary move, split negatives into own cases or tag them clearly.
11. Duplicates: BVA-012 & BVA-030 (ratio(0.125)=="0.13"); EP-026-08 & EP-030-04 (D key-path set); EP-031-04 repeats DT-034-11 & EP-034-12 — merge by citing both item ids.
12. EP-010-01: use th.a / th.b (interface <th scope="col" class="a">), as DT-010-04.
13. EP-022-26: state how fields are removed (del rec["uuid"], del rec["message"]["id"], no rid).
14. DT-014-05: say "a first prompt, description and prompt with no key".
15. DT-011-13: baseline call is a --json call.
16. TC-CL-03: full suites run once by the lead QA at the gate, not by designers.
