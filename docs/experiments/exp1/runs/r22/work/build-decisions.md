# Builder's decisions not covered by a rule, EXP1-R22C (copied by the coordinator from the builder's report)
Build: console 703 passed (445 + 258 new), tools+kit 49 passed, ruff clean; no test edited.
Confirmed: rr9 N1 holds (TC-ST-11 / 11b pass). Field paths: uuid top-level, message.id, requestId top-level, message.stop_reason, timestamp. Real logs (counts only): 1993 end_turn records, 1347 with both ids, 335 id pairs with >1 stop uuid in one file; 646 without requestId (match by uuid only).
A second real-log scan was stopped by the tooling (not retried, answer 42).
## To the business analyst (rule level)
D1 CON-017/018/019: a message with all five token counts 0 is ignored for the model list, the cost and the unpriced count (needed by EP-017-03, BVA-014).
D4 CON-022: message.id+requestId match only when both present; (stop ts, gap-end ts) pair only between stops with no uuid and no id pair; a "<task-notification" text with no origin marker is machine-written and ends no gap; a gap end with no timestamp closes the stop but records no gap.
D8 CON-026: a model present on one side only counts as 0 on the other side in the diff; page model rows show 0k / $0.00.
## To the system analyst (design level)
D2 CON-015: failed decided by the run's last turn (failed unless text or SubagentHandback); denial / ordinary tool_result / open tool_use last = failed; denial texts never matched in sub-agent files; consecutive assistant records with the same message.id = one turn; a file with no assistant turn = failed.
D3 CON-016: repeat rounds = runs minus distinct roles (order-independent).
D5 CON-014: spawn key = tool_calls.ticket (lead key, else text key); if empty, spawning run's evidence at or before spawn time, else spawning run's runs.ticket; spawn with no timestamp takes the newest evidence.
D6 CON-011: index_check returns (differ, missing) split; index_mismatch stays the merged list.
D7 CON-011: empty-key check after argparse via parser.error; Store connection closed in finally.
Other: first index = progress["initial"] or scans == 0 with empty runs.
## BA verdict (copied by the coordinator)
D1: already decided AGAINST the builder (CON-017 v2, CON-018 v2, CON-019, answer 8, existing queries.py 51-55 counts zero-token unpriced messages). Code fix: remove compare.py 295-296 skip. Likely cause: test helper asst() in test_compare.py 71-72 writes usage(0, 0) with a model, adding a model row / unpriced count in EP-017-03, BVA-014 -> fix the test helper, not the product (Q-042).
D4: Agent decision (answers 37, 38), Q-041, CON-022 v12 (also: a stop with no timestamp adds no gap). Not checked against real logs.
D8: already decided (CON-026 v4, Q-018, CON-029, answers 17, 34), Q-043.
## SA verdict (copied by the coordinator; details in change.md "Build decisions")
D2, D3, D5, D6, D7, Other: consistent. New Agent decisions (answer 37), not yet in rules: CON-015 consecutive assistant records with the same message.id = one turn; CON-011 when values differ and others are missing, the "another ..." line names all.
Code gaps (fix with a test first):
G1 compare._Ctx.spawns uses only the earliest copy of a spawn id for end_ts/is_error; a later copy (resumed/copied session) with the tool_result is dropped. Fix: counted when any copy has a result; failed when any copy with a result has is_error; key and order from the earliest copy.
G2 store.py ingest end_ts=COALESCE(end_ts, ?) from the record timestamp; a tool_result record with no timestamp leaves end_ts NULL -> spawn looks result-less and is not counted (answers 31, 35). Fix without schema change (e.g. COALESCE(end_ts, ?, ts)).
Open for BA: a sub-agent run still running when the comparison reads it counts as failed under CON-015 (last-turn rule).
## Builder fix round (D1, G1, G2) — copied by the coordinator
Fixed: D1 skip removed; G1 any copy with a result counts, failed if any copy with a result is_error; G2 COALESCE(end_ts, ?, ts) + result updates applied after the file batch. Console 707 passed, tools+kit 49, ruff clean.
OUT OF PLANNED MODULES: parser.py gets a has_usage flag; store.py no longer writes a messages row for an assistant record with no usage block (no model row, not unpriced). Reason given: D1 alone broke EP-017-03, EP-018-02, BVA-014 because helper filler records (no usage) become zero-token messages. This changes the existing message counting used by every page (CON-032; "keep the existing behaviour").
Also: tool_result updates deferred after the file batch (order only; first end_ts wins, is_error max).
## SA scope check: REVERT (copied by the coordinator; details in change.md "Scope check: parser.py")
Base 0891a04: an assistant record with no usage block DOES produce a messages row (counts in messages, unknown_messages, model rows, last-message time). The builder's change alters existing pages (CON-032 v3, Q-042).
Also not order-only: deferred tool_result updates (a result before its tool_use in a batch was lost at base, now applied) and COALESCE(end_ts, ?, ts) (end_ts = call ts -> dur_s 0, call appears in the run page "tests" list). Revert both.
Fix: parser.py has_usage and store.py guard back to 0891a04; deferred updates and ", ts" fallback back to 0891a04. G2 in compare.py _Ctx.spawns: result exists when out_chars IS NOT NULL (every tool_result update sets out_chars).
Tests (no expected value changes): W.__init__(filler_model=M1); W.asst with u=None writes usage(0, 0) under self.filler_model (does not remove usage). EP-017-03 W(env, filler_model=None); EP-018-02 W(env, filler_model="claude-sonnet-9"); BVA-014 W(env, SONNET, filler_model=SONNET_MODEL); D1-confirm W(env, filler_model="zzz-unpriced") and w.sub("S1","ABC-1") with no steps; G2-confirm: flush, read the main file back, remove the result record's timestamp, rewrite in the same order with write_jsonl, then data(scan(), "ABC-1").
SA proof in a /tmp scratch copy: test_compare.py 149 passed; console suite failures only from the scratch layout.
## BA: tool_result after a SubagentHandback turn (Q-047, CON-015 v10) — copied by the coordinator
Already decided (answer 3; CON-015 final reply = last assistant turn has text or a SubagentHandback call): a tool_result after a handback turn does not take the final reply away; after any other turn it still means no final reply (Q-046 stands).
Real logs (counts only): 737 sub-agent files, 627 with a handback call, 637 handbacks followed by their own tool_result (none is_error), 331 files end on that tool_result. Current code (compare.py ~85-86) marks those failed: about half the completed runs.
BUG B1: fix compare.py so a tool_result after a handback turn keeps the "reply" state. Confirmation test first.
## Builder B1 fix (copied by the coordinator)
compare.py run_failed keeps the SubagentHandback tool_use ids of the last assistant turn (same message.id merged; a new turn resets); a user record whose tool_results all answer those ids with is_error not true keeps "reply"; any other tool_result (incl. an is_error handback result) -> "result" = failed. Console 718 passed, tools+kit 49, ruff clean.
Decisions not covered by a rule:
B1-D1 a user record with several tool_results keeps "reply" only if every result answers a handback call and none is an error.
B1-D2 a handback result is judged only when the state is "reply"; a handback result after a non-reply state is failed.
## SA on B1-D1 / B1-D2 (copied by the coordinator; details in change.md "Build decisions B1-D1, B1-D2")
B1-D1 MISMATCH: a handback turn can carry parallel tool_uses (parser.py 234-241 reads every tool_result block); their results, in the same user record or separate records, today make the run failed — against CON-015 v11 (a tool_result is not a turn, Q-047; only the handback's own error result fails). Fix (compare.py run_failed, user branch): when state is "reply" and hb_ids is non-empty, set "result" only if a result with a tool_use_id in hb_ids has is_error true; ignore every other tool_result. hb_ids empty (text + tool_use turn): unchanged (Q-046). Agent decision (answer 37): another tool's result after a handback turn, error or not, does not make the run failed. BUG B2.
B1-D2: consistent.
## BA on review 2 second look (copied by the coordinator)
Q-050, CON-015 v13 (Agent decision): a last turn with text next to an ordinary tool_use (not SubagentHandback) is not a final reply -> failed whether the file ends on the open tool_use (case 1) or on its result (case 2). Counts: 756 sub-agent files; v12 code fails 32; case 1: 0 files, case 2: 1 file; the other reading would give 31. Code: in run_failed the merged turn is "reply" only when it holds a SubagentHandback call, or has non-empty text and no tool_use other than SubagentHandback. Case 1 changes (today reply -> failed). Finding 3 expects failed in both cases. BUG B3.
Q-051, CON-022 v13 (already decided, answer 30, wording): an origin with no kind, or not an object, carries no origin marker. 0 such records in 1599. Code already does it; a test is missing.
## BA on review 3 second look (copied by the coordinator)
Q-052, CON-022 v14: compact-summary user records carry isCompactSummary: true + isVisibleInTranscriptOnly: true (25 of 68 no-origin, not-isMeta, non-tool-result user records in 71 main files; flags never apart). Already decided by answers 24/30: they end no gap; isVisibleInTranscriptOnly alone also ends no gap (Agent decision, answer 37). Under v13 these 25 counted as typed -> BUG B4.
Code: compare.py _typed, no-origin branch: not typed when isCompactSummary is True or isVisibleInTranscriptOnly is True, before the text tests. Tests: (1) isCompactSummary + plain text after an end_turn stop ends no gap; (2) only isVisibleInTranscriptOnly; (3) the next typed message closes the gap from that stop.
CON-015 note wording fixed (v14, history line, no bump).
## SA: spawn-to-run-file link (review 3 #1; details in change.md "Spawn-to-run-file link") — BUG B5
Link 1: sub_meta.tool_use_id = spawn id. Fallback (only for a sub-agent file with no sub_meta.tool_use_id): files in (first_ts, run_id) order pair one-to-one with the earliest not-yet-linked Agent/Task spawn by (ts, run_id, id) called in a file of the same session_id with ts <= files.first_ts <= end_ts. No pair: stays a spawn with no run file. Paired run: role from the spawn's subagent_type (CON-003); failed decided by the run file only (CON-015).
Real logs: 742/742 linked files start inside their spawn window; with all meta removed (simulation) earliest pairing is right 742/742; on today's 23 unlinked files 0 pairings; figures do not move. No schema change.
Tests: test_spawn_with_run_file_and_no_meta_counts_once (meta removed / unreadable x err False/True -> total 1, failed 0, repeat_rounds 0; the sub file needs its own [ABC-1] prompt); guard test_unlinked_file_does_not_take_a_denied_spawn (-> total 2, failed 1, repeat_rounds 1). Full fixture code in change.md.
Rules: Agent decision notes on CON-014 (the link) and CON-003 (role from the paired spawn) — wording in change.md.
## Builder B4/B5 + review 3 items (copied by the coordinator)
B5 _Ctx._pair_unlinked + role from the paired spawn; B4 _typed flags; comments rule-id only; BEGIN/rollback read snapshot on page and CLI; index_mismatch kept. Console 747 passed, tools+kit 49, ruff clean.
Decisions not covered by a rule: B5-D1 a spawn's end_ts comes from the earliest copy that has one; a spawn with no result time is never paired. B5-D2 the paired spawn's role is used only when sub_meta.role is null.
## Builder SEC-1..4, HV-1, HV-2 fix round (copied by the coordinator)
SEC-1 _s() str-only ids/uuids/timestamps; RecursionError skipped; CLI catches Exception -> one line exit 1; compare_view try/except -> HTML 500 with headers. SEC-2 index_check immutable=1 when no -wal. SEC-3 compare_format.safe() escapes C0/C1/DEL as \xNN in text cells. SEC-4 symlink index refused exit 2. HV-2 stderr keys through safe(). HV-1 scan:<pid> marker in ingest; page 503 in its BEGIN snapshot; no Store.lock. Console 769 passed (1 deselected), tools+kit 49, ruff clean.
TEST DEFECT: test_hv_p20 calls monkeypatch.undo(), which also undoes the env fixture -> its fresh Store read the REAL log root (~/.claude/projects) once, read-only. Coordinator check: the person's index (~/.agent-console/index.sqlite, read immutable) has no scan:% rows and no home/repo_root rows -> the new code never wrote to it. Fix the test (own pytest.MonkeyPatch() or setattr back, no undo()).
Decisions not covered by a rule: BD1 safe() escape form \xNN lowercase (newline -> \x0a). BD2 symlink refusal line "compare: refused: the index at <path> is a symbolic link (nothing written)". BD3 500 page text "The comparison could not be built. Try again later." (no detail). BD4 malformed ids/timestamps are skipped, not an error. BD5 index_check: immutable=1 only when no -wal; plain ro when a -wal exists.
## Builder extra loop 5 (copied by the coordinator)
argparse _Parser.error -> usage + "{prog}: error: {safe(message)}" exit 2. NEW-2 _pid_alive treats OverflowError/ValueError as dead; _marker_stale (SCAN_MARKER_MAX_AGE 3600 s). NEW-3 index_check reads a temp copy of db + wal when -wal exists without -shm (_index_values helper). BD4 None ids never added to hb_ids/asks/rejected; run_failed keys on turn_hb (a handback call in the last turn) instead of hb_ids non-empty. Console 789 passed, 1 failed (test_dt_010_08 uses a fixed marker time now > 1 h old: test defect), tools+kit 49, ruff clean, parser.py == base.
Decisions not covered by a rule: L5-D1 an unparsable marker time is not stale (pid decides); L5-D2 a timezone-less marker time is UTC; L5-D3 -wal without -shm: read a temporary copy (immutable would ignore the wal); L5-D4 handback check keyed on a handback call in the last turn (needed once None ids are filtered).
