# Test design open questions, EXP1-R22C (collected by the coordinator from cases-ep/dt/bva/st-cl.md)
## A. Rule questions -> business analyst (already decided / Agent decision answer 37 / BLOCKING)
A1 (ST-1, rr9 N1) CON-022: two stop records in ONE file sharing message.id+requestId (one API reply) = one gap? Case CI-022-30 expects 300 s (vs 900 s). Put it in the statement.
A2 (ST-2) CON-022: which timestamp starts the gap for a rejected permission prompt? Case CI-022-03 assumes the assistant turn holding the prompt (390 s).
A3 (ST-4) CON-022: which record field shows an end_turn stop? Case assumes message.stop_reason.
A4 (EP-3) CON-022: which log marker shows hook output in a user record (EP-022-13 uses isMeta as stand-in)?
A5 (BVA Q-D, EP-5) CON-017/018/019: is an unpriced model listed in cost_usd.by_model with 0, or left out?
A6 (BVA Q-E) default period edge: already decided by answer 6 (comparison ignores the default period; all logs). Confirm in the rule if not said.
A7 (BVA Q-C) CON-014: key evidence at the same timestamp as the spawn: new key (tickets.latest_before "at or before")? State it.
## B. Interface / test-setup questions -> system analyst (change.md)
B1 (ST-3, DT-5, EP-1, BVA Q-A, formatter names) names and signatures: compare data function (DATA(K)), compare_cli.main(argv) -> int, compare_format function names, page test client, how a test sets progress["initial"]/["scans"].
B2 (DT-1, EP-6, BVA Q-B, EP-2) page markup: row labels, column headings, how diff/ratio share a cell, where the unpriced count sits; exact text of 503/422/404 messages (422 must name the missing parameter).
B3 (DT-2) exact CLI usage text.
B4 (EP-4) CON-011 v5: a file that is not a database raises sqlite3.DatabaseError (change.md says OperationalError); exact exit-1 line.
B5 (DT-3) test-data recipe tying a key to a main session (own vs effective key, CON-002 80 %).
B6 (DT-4) tmp pricing in the env fixture must price the test model (or the test adds it).
B7 (EP-8) conftest.ts() stops at 3599 s: a local at(n) helper for long gaps.
B8 (BVA Q-F) a session with no record timestamps: does the Store drop it? (decides whether BVA-006 is index-level).
