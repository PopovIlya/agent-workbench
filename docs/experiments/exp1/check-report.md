# EXP1 independent check report

### STEP 1
Action taken: python3 ~/exp1-private/check/make_dataset.py; ls /tmp/exp1-check-logs/-work-app (the first attempt, combined with other commands, was denied by the permission classifier; re-run alone succeeded)
Expected: prints `written /tmp/exp1-check-logs/-work-app`; folder lists S-A.jsonl, S-A, S-C.jsonl, S-C
Actual: printed `written /tmp/exp1-check-logs/-work-app`; listing: S-A, S-A.jsonl, S-C, S-C.jsonl
Status: MATCH

### STEP 2
Action taken: cat ~/exp1-private/check/oracle.out
Expected: record
Actual: recorded. CMPA-1: sonnet [in 3200,out 850,cr 12000,cw 2500] cost 0.02355; opus [3000,600,10000,1000] cost 0.031; total 0.05455, main 0.0155, sub 0.03905, share 0.3969; runs 3 (failed 1, repeat 1); wall 9030 s; active 1080 s; wait 7800 s (7500 over 2h). CMPB-1: 1 reviewer run, sonnet [400,100,1000,300], cost 0.00275, no main session.
Status: MATCH

### STEP 3
Action taken: git status --porcelain; rev-parse --abbrev-ref HEAD; log --oneline 0891a04..HEAD | wc -l (in awb-kit)
Expected: status empty; branch exp1/kit; record commits
Actual: status empty; branch exp1/kit; 3 commits
Status: MATCH

### STEP 4
Action taken: ruff check . | tail -3 in awb-kit
Expected: All checks passed!
Actual: All checks passed!
Status: MATCH

### STEP 5
Action taken: pytest tests -q in awb-kit/console
Expected: record passed/failed (0 failed)
Actual: 554 passed, 1 warning, 0 failed
Status: MATCH

### STEP 6
Action taken: pytest tests kit/tests -q in awb-kit
Expected: 49 passed
Actual: 49 passed
Status: MATCH

### STEP 7
Action taken: git diff --numstat, grep -c '^+def test_', diff --stat (awb-kit)
Expected: record
Actual: console/tests/test_compare.py +1232 -0; added test functions 79; total: 6 files changed, 2146 insertions(+), 4 deletions(-)
Status: MATCH

### STEP 8
Action taken: started throwaway KIT console on 18801 (env as given), polled /health
Expected: {"ok":true,"app":"agent-console"}
Actual: {"ok":true,"app":"agent-console"}
Status: MATCH

### STEP 9
Action taken: agent_console compare CMPA-1 CMPB-1 (via /tmp/exp1-cli.sh kit 18801, a wrapper that sets the given env and cd's to awb-kit/console)
Expected: exit 0; table with CMPA-1 column, CMPB-1 column, difference column
Actual: EXIT=0 (my first attempt lost the exit code due to a piped PIPESTATUS; re-run alone gave 0). Output columns: "a: CMPA-1 | b: CMPB-1 | difference (b - a) | ratio (b / a)". Full output (rounded: tokens k, $ cents, minutes):
Role runs 3|1|-2|0.33; Failed 1|0|-1|0.00; Repeat 1|0|-1|0.00; Tokens input 6k|0k|-6k|0.06; output 1k|0k|-1k|0.07; cache write 4k|0k|-3k|0.09; cache read 22k|1k|-21k|0.05; total 33k|2k|-31k|0.05; Cost $0.05|$0.00|-$0.05|0.05; Unpriced 0|0|0|n/a; Wall 151 min|2 min|-149 min|0.01; Active role 18 min|2 min|-16 min|0.11; Main: waiting 130 min|no main session|n/a|n/a; Main: gaps over 2 h 125 min|no main session; Main tokens 14k|no main session; Main cost $0.02|no main session; Main/sub cost 0.40|no main session; per model rows: opus-5-5 input 3k, output 1k, cw 1k, cr 10k, cost $0.03 (b '-'); sonnet-5-5 input 3k|0k, output 1k|0k, cw 3k|0k, cr 12k|1k, cost $0.02|$0.00.
Status: MATCH

### STEP 10
Action taken: curl /compare?a=CMPA-1&b=CMPB-1 until 200, text dump
Expected: HTTP 200; both tickets side by side with a difference column
Actual: HTTP 200 on first poll. Text: "Compare CMPA-1 and CMPB-1 ... a: CMPA-1 b: CMPB-1 difference (b - a) ratio (b / a)" followed by the same rows and values as the CLI table in step 9 (e.g. Cost $0.05 $0.00 -$0.05 0.05; Main session cost / sub-agent cost 0.40 no main session n/a n/a).
Status: MATCH

### STEP 11
Action taken: read role-run figures of CMPA-1 from step 9 table and --json output
Expected: total 3, failed 1, repeat rounds 1
Actual: total 3, failed 1, repeat 1
Status: MATCH

### STEP 12
Action taken: read tokens_by_model of CMPA-1 from --json (raw values)
Expected: sonnet: in 3200, out 850, cr 12000, cw 2500; opus: in 3000, out 600, cr 10000, cw 1000
Actual: claude-sonnet-5-5: input 3200, output 850, cache_read 12000, cache_write 2500; claude-opus-5-5: input 3000, output 600, cache_read 10000, cache_write 1000. All equal. (Page shows rounded k values.)
Status: MATCH

### STEP 13
Action taken: read cost of CMPA-1 from --json and page
Expected: sonnet 0.02355, opus 0.031, total 0.05455
Actual: sonnet 0.02355, opus 0.031, total 0.05455 (page: $0.02, $0.03, $0.05)
Status: MATCH

### STEP 14
Action taken: read wall time of CMPA-1
Expected: 151 min (9030 s)
Actual: page 151 min; JSON wall_s 9030.0
Status: MATCH

### STEP 15
Action taken: read active role time of CMPA-1
Expected: 18 min (1080 s)
Actual: page 18 min; JSON active_role_s 1080.0
Status: MATCH

### STEP 16
Action taken: read wait time of CMPA-1
Expected: 130 min (7800 s); over 2 h 7500 s if shown
Actual: page 130 min, gaps over 2 h 125 min; JSON wait_s 7800.0, wait_over_2h_s 7500.0
Status: MATCH

### STEP 17
Action taken: read main-session share for CMPA-1
Expected: about 0.40 (0.3969)
Actual: page 0.40; JSON main_share_of_sub_cost 0.39692701664532654 (main cost 0.0155, sub-agents 0.03905)
Status: MATCH

### STEP 18
Action taken: looked at main-session-only rows of CMPB-1 (page and CLI and JSON)
Expected: each shows "no main session", not 0
Actual: page/CLI: waiting on a person, gaps over 2 h, main tokens, main cost, main/sub share all show "no main session". JSON: main_session null, main_share_of_sub_cost null.
Status: MATCH

### STEP 19
Action taken: read the difference column for total cost
Expected: b-a about -0.0518; b/a about 0.05
Actual: page "Cost $0.05 $0.00 -$0.05 0.05"; JSON difference.cost_usd -0.0518, ratio.cost_usd 0.05041
Status: MATCH

### STEP 20
Action taken: curl /compare?a=CMPA-1&b=NOPE-9 on 18801
Expected: clear error naming the key; record HTTP status
Actual: body "Ticket comparison / Unknown ticket key: NOPE-9"; HTTP=404
Status: MATCH

### STEP 21
Action taken: compare CMPA-1 NOPE-9 via wrapper (kit)
Expected: clear error and EXIT=2
Actual: "Unknown ticket key: NOPE-9"; EXIT=2
Status: MATCH

### STEP 22
Action taken: compare CMPA-1 CMPB-1 --json > /tmp/exp1-kit.json; chk_json.py
Expected: EXIT=0; parsed; KEYS_SORTED True
Actual: EXIT=0; parsed; KEYS_SORTED True
Status: MATCH

### STEP 23
Action taken: ran --json twice, md5 of each
Expected: equal checksums
Actual: 185467ef5d76193fa461accedc318312 and 185467ef5d76193fa461accedc318312
Status: MATCH

### STEP 24
Action taken: started `python -m agent_console` with no args on port 18901 (via wrapper), polled /health, killed pid 80533 (found by lsof on 18901)
Expected: health answers on 18901; process then stopped
Actual: {"ok":true,"app":"agent-console"}; after kill 0 listeners on 18901
Status: MATCH

### STEP 25
Action taken: killed the listener on 18801; lsof count
Expected: 0 listeners
Actual: 0
Status: MATCH

(Note: KIT mutation runs M1–M15 were executed in three batched tool calls via a helper /tmp/exp1-mut.py that edits, runs pytest -x, reverts with git checkout and prints status; the blocks below were written right after those runs, not one by one.)

### STEP 26
Action taken: KIT M1: compare.py _add_tokens: cache_read added to input, cache_read field reported 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_tokens_are_split_per_model_by_the_messages_own_model); git status --porcelain after revert: empty
Status: MATCH

### STEP 27
Action taken: KIT M2: compare.py _add_tokens: cache_write reported as 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_tokens_are_split_per_model_by_the_messages_own_model); git status --porcelain after revert: empty
Status: MATCH

### STEP 28
Action taken: KIT M3: compare.py _ticket: main-session tokens and cost subtracted from the totals; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_cost_per_model_and_total_from_pricing_yaml); git status --porcelain after revert: empty
Status: MATCH

### STEP 29
Action taken: KIT M4: compare.py WAIT_MIN_S 60 -> 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_wait_threshold_gaps_under_60_s_are_zero_and_long_gaps_count); git status --porcelain after revert: empty
Status: MATCH

### STEP 30
Action taken: KIT M5: compare.py main_waits: every assistant message starts a wait (condition replaced by True); pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_only_end_turn_and_ask_user_question_are_stops_for_the_person); git status --porcelain after revert: empty
Status: MATCH

### STEP 31
Action taken: KIT M6: compare.py _ticket: by_model key replaced by a single name "all"; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_tokens_are_split_per_model_by_the_messages_own_model); git status --porcelain after revert: empty
Status: MATCH

### STEP 32
Action taken: KIT M7: compare.py _ticket: input and output swapped in the message_cost call; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_cost_per_model_and_total_from_pricing_yaml); git status --porcelain after revert: empty
Status: MATCH

### STEP 33
Action taken: KIT M8: compare.py share = main/(main+sub); pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_share_is_main_cost_over_sub_agent_cost); git status --porcelain after revert: empty
Status: MATCH

### STEP 34
Action taken: KIT M9: compare.py _diff: difference returns b/a; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_difference_and_ratio_b_over_a); git status --porcelain after revert: empty
Status: MATCH

### STEP 35
Action taken: KIT M10: compare.py _diff: ratio computed a/b; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_difference_and_ratio_b_over_a); git status --porcelain after revert: empty
Status: MATCH

### STEP 36
Action taken: KIT M11: compare.py cli_main: returns 0 on UnknownKey; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_cli_unknown_key_exits_2_and_names_it[AAA-1-NOPE-9]); git status --porcelain after revert: empty
Status: MATCH

### STEP 37
Action taken: KIT M12: server.py /compare: unknown key gives 200 with empty message; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_page_unknown_key_is_a_clear_error); git status --porcelain after revert: empty
Status: MATCH

### STEP 38
Action taken: KIT M13: compare.py _figure: no main session returns 0 instead of the words; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ticket_without_main_session_says_so_in_the_main_rows); git status --porcelain after revert: empty
Status: MATCH

### STEP 39
Action taken: KIT M14: compare.py to_json: sort_keys=False; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_json_keys_are_sorted_and_the_output_is_repeatable); git status --porcelain after revert: empty
Status: MATCH

### STEP 40
Action taken: KIT M15: compare.py _ticket: failed run counting replaced by +0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_run_that_did_not_complete_is_failed[api_error_after_a_normal_reply]); git status --porcelain after revert: empty
Status: MATCH

### STEP 41
Action taken: git status --porcelain; rev-parse --abbrev-ref HEAD; log 0891a04..HEAD | wc -l (awb-r22)
Expected: status empty; branch exp1/r22; record commits
Actual: status empty; branch exp1/r22; 1 commit
Status: MATCH

### STEP 42
Action taken: ruff check . | tail -3 in awb-r22
Expected: All checks passed!
Actual: All checks passed!
Status: MATCH

### STEP 43
Action taken: pytest tests -q in awb-r22/console
Expected: record passed/failed
Actual: 798 passed, 1 warning, 0 failed
Status: MATCH

### STEP 44
Action taken: pytest tests kit/tests -q in awb-r22
Expected: 49 passed
Actual: 49 passed
Status: MATCH

### STEP 45
Action taken: git diff --numstat, grep -c '^+def test_', diff --stat (awb-r22)
Expected: record
Actual: added lines per test file: fixtures/golden_ticket_columns.json 50, test_compare.py 2381, test_compare_cli.py 1083, test_compare_format.py 296, test_compare_page.py 935, test_server.py 24, test_static.py 8, test_store_and_flags.py 225 (total 5002 added, 0 removed); added test functions: 317; total: 19 files changed, 6826 insertions(+), 20 deletions(-)
Status: MATCH

### STEP 46
Action taken: started throwaway R22 console on 18802 (via wrapper), polled /health
Expected: {"ok":true,"app":"agent-console"}
Actual: {"ok":true,"app":"agent-console"}
Status: MATCH

### STEP 47
Action taken: compare CMPA-1 CMPB-1 (r22 wrapper)
Expected: exit 0; table with CMPA-1 column, CMPB-1 column, difference column
Actual: exit 0 (my first attempt lost the code through a pipe; separate run printed 0). Header: "Figure | CMPA-1 | CMPB-1 | Difference b - a (ratio b / a)". Rows (a | b | diff (ratio)): Main sessions 1|0|-1 (0.00); Role runs 3|1|-2 (0.33); Failed 1|0|-1 (0.00); Repeat 1|0|-1 (0.00); Tokens in 6k|0k|-6k (0.06); out 1k|0k|-1k (0.07); cache write 4k|0k|-3k (0.09); cache read 22k|1k|-21k (0.05); opus in 3k|0k, out 1k|0k, cw 1k|0k, cr 10k|0k (ratios 0.00); sonnet in 3k|0k -3k (0.13), out 1k|0k (0.12), cw 3k|0k -2k (0.12), cr 12k|1k -11k (0.08); Main-session tokens in 2k, out 0k, cw 2k, cr 9k | no main session | n/a; Cost $0.05|$0.00|-$0.05 (0.05); Unpriced 0|0|0 (n/a); Cost opus $0.03|$0.00|-$0.03 (0.00); Cost sonnet $0.02|$0.00|-$0.02 (0.12); Main-session cost $0.02|no main session; Wall 151 min|2 min|-149 min (0.01); Active 18 min|2 min|-16 min (0.11); Main wait 130 min|no main session; over 2 h 125 min|no main session; Cost share 0.40|no main session. Note: the absent opus model for CMPB-1 is shown as 0k/$0.00 (not "-"), giving ratio 0.00.
Status: MATCH

### STEP 48
Action taken: curl /compare?a=CMPA-1&b=CMPB-1 until 200, text dump (r22)
Expected: HTTP 200; both tickets side by side with a difference column
Actual: HTTP 200 on first poll. Text: "Ticket comparison  Figure CMPA-1 CMPB-1 Difference b - a (ratio b / a)" followed by the same rows as step 47.
Status: MATCH

### STEP 49
Action taken: read role-run figures of CMPA-1 (table and --json)
Expected: total 3, failed 1, repeat 1
Actual: total 3, failed 1, repeat_rounds 1
Status: MATCH

### STEP 50
Action taken: read tokens by model of CMPA-1 from --json
Expected: sonnet 3200/850/12000/2500 (in/out/cr/cw); opus 3000/600/10000/1000
Actual: sonnet input 3200, output 850, cache_read 12000, cache_write 2500; opus input 3000, output 600, cache_read 10000, cache_write 1000. All equal.
Status: MATCH

### STEP 51
Action taken: read cost of CMPA-1 from --json and page
Expected: sonnet 0.02355, opus 0.031, total 0.05455
Actual: by_model sonnet 0.02355, opus 0.031; total 0.05455 (page $0.02, $0.03, $0.05)
Status: MATCH

### STEP 52
Action taken: read wall time of CMPA-1
Expected: 151 min (9030 s)
Actual: page 151 min; JSON time_s.wall 9030.0
Status: MATCH

### STEP 53
Action taken: read active role time of CMPA-1
Expected: 18 min (1080 s)
Actual: page 18 min; JSON time_s.active_role 1080.0
Status: MATCH

### STEP 54
Action taken: read wait of CMPA-1
Expected: 130 min (7800 s); over 2 h 7500 s if shown
Actual: page 130 min; over 2 h 125 min; JSON wait 7800.0, wait_over_2h 7500.0
Status: MATCH

### STEP 55
Action taken: read main-session share of CMPA-1
Expected: about 0.40 (0.3969)
Actual: page 0.40; JSON cost_share 0.39692701664532654
Status: MATCH

### STEP 56
Action taken: looked at CMPB-1 main-only rows (page, CLI, JSON)
Expected: each shows "no main session", not 0
Actual: Main-session tokens (4 rows), Main-session cost, Main-session wait, wait over 2 h, Cost share: all "no main session". JSON has the string "no main session" for tokens.main, cost_usd.main, time_s.wait, wait_over_2h, cost_share. Only the count row "Main sessions" shows 0 for CMPB-1 (a count of sessions, not a main-only figure).
Status: MATCH

### STEP 57
Action taken: read total cost difference column
Expected: b-a about -0.0518; b/a about 0.05
Actual: page "Cost $0.05 $0.00 -$0.05 (0.05)"; JSON cost_usd.total diff -0.0518, ratio 0.05041
Status: MATCH

### STEP 58
Action taken: curl /compare?a=CMPA-1&b=NOPE-9 on 18802
Expected: clear error naming the key; record HTTP status
Actual: body `<p class="error">Unknown ticket key: <code>NOPE-9</code>.</p>`; HTTP=404
Status: MATCH

### STEP 59
Action taken: compare CMPA-1 NOPE-9 (r22 wrapper)
Expected: clear error and EXIT=2
Actual: "compare: unknown ticket key: NOPE-9"; EXIT=2
Status: MATCH

### STEP 60
Action taken: compare CMPA-1 CMPB-1 --json > /tmp/exp1-r22.json; chk_json.py
Expected: EXIT=0; parsed; KEYS_SORTED True
Actual: EXIT=0; parsed; KEYS_SORTED True
Status: MATCH

### STEP 61
Action taken: ran --json twice, md5 each (r22)
Expected: equal checksums
Actual: 3c49dadcd3dc6f553aaaaa2236c67aa2 and 3c49dadcd3dc6f553aaaaa2236c67aa2
Status: MATCH

### STEP 62
Action taken: started no-arg server on 18902 (r22), polled /health, killed pid 89560
Expected: health answers on 18902; process then stopped
Actual: {"ok":true,"app":"agent-console"}; after kill 0 listeners on 18902
Status: MATCH

### STEP 63
Action taken: killed listener on 18802; lsof count
Expected: 0 listeners
Actual: 0
Status: MATCH

(Note: R22 mutation runs M1–M15 were executed in three batched tool calls via the same helper (edit, pytest -x, git checkout, status); the blocks below were written right after.)

### STEP 64
Action taken: R22 M1: compare.py _ticket: cache_read added to input, cache_read reported 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_017_01_four_token_kinds); git status --porcelain after revert: empty
Status: MATCH

### STEP 65
Action taken: R22 M2: compare.py _ticket: cache_write reported 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_017_01_four_token_kinds); git status --porcelain after revert: empty
Status: MATCH

### STEP 66
Action taken: R22 M3: compare.py _ticket: main-session tokens and cost left out of the total tokens and total cost; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_012_01_old_record_counts); git status --porcelain after revert: empty
Status: MATCH

### STEP 67
Action taken: R22 M4: compare.py MIN_GAP_S 60 -> 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_bva_007_gap_of_59_seconds_counts_zero); git status --porcelain after revert: empty
Status: MATCH

### STEP 68
Action taken: R22 M5: compare.py file_gaps: every assistant message counted as a stop (True); pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_022_11_ordinary_tool_result_ends_no_gap); git status --porcelain after revert: empty
Status: MATCH

### STEP 69
Action taken: R22 M6: compare.py _ticket: by_model keyed by a single name "all"; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_013_01_sub_run_included); git status --porcelain after revert: empty
Status: MATCH

### STEP 70
Action taken: R22 M7: compare.py _ticket: input and output swapped in the message_cost call; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_013_04_two_mains_summed); git status --porcelain after revert: empty
Status: MATCH

### STEP 71
Action taken: R22 M8: compare.py share = main/(main+sub); pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_018_04_main_cost_and_share); git status --porcelain after revert: empty
Status: MATCH

### STEP 72
Action taken: R22 M9: compare.py _leaf: diff returns b/a; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_026_05_union_of_models); git status --porcelain after revert: empty
Status: MATCH

### STEP 73
Action taken: R22 M10: compare.py _leaf: ratio computed a/b; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_026_05_union_of_models); git status --porcelain after revert: empty
Status: MATCH

### STEP 74
Action taken: R22 M11: compare_cli.py: returns 0 on unknown key; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_compare_cli.py::test_ep_027_06_unknown_key_is_one_line_on_stderr_exit_2); git status --porcelain after revert: empty
Status: MATCH

### STEP 75
Action taken: R22 M12: server.py /compare: unknown key gives 200 with empty body; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_compare_page.py::test_dt_010_05_after_one_scan_an_empty_index_is_404_not_503); git status --porcelain after revert: empty
Status: MATCH

### STEP 76
Action taken: R22 M13: compare.py _ticket: no main session gives 0 / empty tokens instead of the words; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_013_03_effective_key_decides); git status --porcelain after revert: empty
Status: MATCH

### STEP 77
Action taken: R22 M14: compare.py to_json: sort_keys=False; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_030_01_json_is_sorted_and_versioned); git status --porcelain after revert: empty
Status: MATCH

### STEP 78
Action taken: R22 M15: compare.py _ticket: failed runs counted as 0; pytest tests -q -x; git checkout -- .; status --porcelain
Expected: KILLED; status empty after revert
Actual: KILLED (first failing test: test_ep_014_06_spawn_lead_wins_over_text); git status --porcelain after revert: empty
Status: MATCH

### STEP 79
Action taken: rm -rf /tmp/exp1-scratch-kit; cp -R awb-kit /tmp/exp1-scratch-kit; copied the files R22 ADDED under console/tests to the same paths
Expected: scratch copy exists; list of copied files recorded
Actual: scratch exists. Copied: console/tests/fixtures/golden_ticket_columns.json, console/tests/test_compare.py (overwrites KIT's own test_compare.py in the scratch copy, same path), console/tests/test_compare_cli.py, console/tests/test_compare_format.py, console/tests/test_compare_page.py
Status: MATCH

### STEP 80
Action taken: in /tmp/exp1-scratch-kit/console: pytest tests/test_compare.py tests/test_compare_cli.py tests/test_compare_format.py tests/test_compare_page.py -q (the fixture json is data, not a test file)
Expected: record passed, failed, errors
Actual: 10 passed, 325 failed, 0 errors. Per file: test_compare.py 200 failed; test_compare_cli.py 57 failed; test_compare_format.py 21 failed; test_compare_page.py 47 failed, 10 passed.
Status: MATCH

### STEP 81
Action taken: grouped the 325 failures by error message (pytest --tb=line); judged only against brief.md
Expected: record
Actual (groups; counts are from --tb=line message counts, so they do not add exactly to 325):
1. count 174, example test_compare.py (e.g. test_ep_013_01_sub_run_included): AttributeError 'sqlite3.Connection' object has no attribute 'reader'. R22 tests call compare(db_connection, pricing, a, b); KIT's compare() takes (store, pricing, a, b). Class: DESIGN.
2. count 23 (11 + 6 + 6), example test_compare.py: AttributeError module 'agent_console.compare' has no attribute 'ticket' / 'unknown_keys' / 'file_gaps'. Different helper names in KIT. Class: DESIGN.
3. count about 57 in test_compare_cli.py, e.g. ModuleNotFoundError: no module named agent_console.compare_cli (3 shown by name), plus text differences: KIT header is "a: / b: / difference (b - a) / ratio (b / a)" not "Figure ..."; JSON top-level keys {a, b, difference, ratio} not {a, b, diff, version}; error text "Unknown ticket key: X" not "compare: unknown ticket key: X". Exit code 2 is the same. Class: DESIGN (module, output format and field names differ; the brief fixes none of them, only "sorted keys, fixed field names").
4. count 21, test_compare_format.py: module agent_console.compare_format does not exist in KIT. Class: DESIGN.
5. count about 47 in test_compare_page.py, examples test_ep_033_04_the_200_page_has_the_table_and_the_headers, test_dt_034_01_a_missing_names_a_only: page HTML differs (no `<table class="compare">`, stylesheet /static/style.css not compare.css, error markup `<p>Unknown ticket key: NOPE</p>` without `<code>`, missing-parameter wording, no compare_page module, JSON paths like runs.total / tokens.main.input / time_s.wait absent). Class: DESIGN.
6. count about 6, e.g. test_dt_027_13_missing_parameter_wins_over_the_first_index_page, test_ep_033_07_the_503_page_has_the_headers: R22 answers 503 while the index is building and an HTML 500 page for an unexpected error; KIT has neither (a raw exception escapes in test_con_033_unexpected_error_gives_the_html_500_page; CLI prints a traceback on an unreadable database, test_compare_cli:331). The brief does not ask for these. Class: DESIGN (beyond-brief robustness, not a missing brief item).
No group was judged REAL; none ENVIRONMENT. Limit of this reading: because most tests fail on interface mismatch before reaching behaviour, they cannot show whether KIT meets the finer rules they encode.
Status: MATCH

### STEP 82
Action taken: ran `rm -rf /tmp/exp1-scratch-kit` together with the later steps in one command while my shell's working directory was inside the scratch copy. The harness denied the command (safety check: "Dangerous rm operation ... workspace directory"; only a person may approve). I did not retry or work around it.
Expected: scratch removed; worktree status empty
Actual: /tmp/exp1-scratch-kit still exists (not removed). The git status of awb-kit was not read in that denied command.
Status: COULD NOT COMPLETE

### STEP 83
Action taken: cp -R awb-r22 /tmp/exp1-scratch-r22 (the rm -rf of this path was skipped: it did not exist); copied the files KIT ADDED under console/tests
Expected: scratch copy exists; list of copied files recorded
Actual: scratch exists. Copied: console/tests/test_compare.py (the only file KIT added under console/tests; it replaces nothing, R22 has the same path and it was overwritten in the scratch copy only)
Status: MATCH

### STEP 84
Action taken: in /tmp/exp1-scratch-r22/console: pytest tests/test_compare.py -q
Expected: record passed, failed, errors
Actual: 74 passed, 35 failed, 0 errors (109 tests in KIT's file; I counted 79 added test functions, the rest are parametrized cases)
Status: MATCH

### STEP 85
Action taken: grouped the 35 failures by cause (pytest --tb=line, test source read); judged only against brief.md
Expected: record
Actual (the KIT tests look numbers up by words in the JSON key path and read CLI text lines by label, so they tolerate some naming differences but not all):
1. count 13, example test_a_gap_of_59_s_counts_as_zero (also test_machine_records_do_not_end_a_gap[...] x6, test_a_typed_slash_command_ends_a_gap x2, test_a_tool_result_does_not_end_a_gap): the test reads numbers whose key path contains "main" and "wait"; R22 puts them at time_s.wait / time_s.wait_over_2h (no "main" in the path). The wait values themselves match the oracle (step 54). Class: DESIGN (field names).
2. count 6, example test_page_missing_or_empty_key_is_422_with_one_message_and_no_form[params0]: expects exactly one bare `<p>` in the 422 page; R22 uses `<p class="error">`, so the markup count differs. Status 422 matches. Class: DESIGN (page markup).
3. count 3, example test_tokens_are_shown_as_12k_with_ties_away_from_zero_and_the_sign_kept (also test_negative_difference..., test_ratio_tie...): StopIteration looking for a CLI text line that starts with a label such as "Tokens: input"; R22 labels are "Tokens, input". Class: DESIGN (output format).
4. count 3, example test_json_shape_is_fixed: expected top-level keys {a, b, difference, ratio}, R22 has {a, b, diff, version}; test_json_main_session_is_null... KeyError main_session; KeyError tokens_by_model. Class: DESIGN (field names; the brief asks only for fixed names).
5. count 1, test_no_argument_starts_the_server_and_compare_does_not: monkeypatches compare.cli_main, which R22 does not have (its CLI is compare_cli.main). Class: DESIGN (module and function name).
6. count 8, example test_run_that_did_not_complete_is_failed[no_final_reply] (also [handback_call_is_not_a_final_reply], test_denied_spawn_counts_in_run_total_and_failed, test_non_denial_error_result_after_the_last_reply_does_not_fail_an_end_turn_run, test_denial_that_is_not_an_error_result_does_not_fail_the_run, test_synthetic_record_that_is_not_an_api_error_does_not_clear_an_api_error, test_run_with_a_missing_stop_reason_is_failed, test_verdicts_and_ordinary_errors_are_not_failed_runs[ordinary_tool_error]): the failed-run count in R22 differs from what KIT's test expects for these built cases. The brief says only "role runs: total, failed"; it does not say which events make a run failed, so I cannot call this REAL from the brief. Class: DESIGN (different reading of "failed"). Flag for a human: this is the group closest to a behaviour difference; the oracle case (step 49) matches in both arms.
7. count 1, test_a_message_without_a_model_id_is_shown_under_unknown_in_the_page_and_json (and test_unpriced_count_is_also_given_per_model): per-model layout and per-model unpriced count differ; brief asks neither. Class: DESIGN.
No group was judged REAL; none ENVIRONMENT. (The group sizes add to 35 only approximately: groups 6 and 7 overlap with tests I named in two places.)
Status: MATCH

### STEP 86
Action taken: rm -rf /tmp/exp1-scratch-r22 (run with my shell outside the scratch folder); git -C awb-r22 status --porcelain
Expected: scratch removed; worktree status empty
Actual: scratch removed (ls: no such file or directory); awb-r22 status empty (0 lines)
Status: MATCH

## Summary

Notes on the run: the exact commands of steps were run through a small wrapper /tmp/exp1-cli.sh (sets the given env vars and the folder) because zsh does not split a variable holding a command; mutations went through /tmp/exp1-mut.py (exact-string edit, pytest -x, git checkout, status). KIT mutation runs and R22 mutation runs were done in batches, with the blocks written right after each batch. Step 1 was first denied by the permission classifier when combined with other commands; re-run alone it worked. Step 82 could not complete: the first removal of /tmp/exp1-scratch-kit was denied by the harness safety check (my shell was inside that folder) and I did not retry or work around it, so /tmp/exp1-scratch-kit still exists; awb-kit git status was empty when checked afterwards (0 lines). I read only brief.md, mutations.md, the instructions, oracle.out, and code/tests in the two worktrees (the compare modules, server and test files); no process files, no session logs.

### 1. Requirements (brief items 1 to 5)

KIT (awb-kit, branch exp1/kit):
| Item | Result | Evidence |
|---|---|---|
| 1 Page and CLI | met | steps 9, 10, 24 |
| 2 Per-ticket figures (roles, tokens per model, cost, wall, active, wait, share) | met (all equal the oracle) | steps 11 to 17 |
| 3 Difference column (b-a and b/a) | met | step 19 |
| 4 Unknown key (page 404 + message, CLI exit 2); no main session shows words | met | steps 18, 20, 21 |
| 5 Stable JSON | met | steps 22, 23 |

R22 (awb-r22, branch exp1/r22):
| Item | Result | Evidence |
|---|---|---|
| 1 Page and CLI | met | steps 47, 48, 62 |
| 2 Per-ticket figures | met (all equal the oracle) | steps 49 to 55 |
| 3 Difference column | met | step 57 |
| 4 Unknown key; no main session | met | steps 56, 58, 59 |
| 5 Stable JSON | met | steps 60, 61 |

Observed differences that are not oracle mismatches: R22 prints a "Main sessions" count row (0 for CMPB-1, a count, not a main-only figure) and shows 0k/$0.00 for a model absent on one side (KIT shows "-"). KIT's JSON uses null for no main session, R22's JSON uses the string "no main session".

### 2. Mutations (KILLED = at least one own test fails)
| # | KIT | R22 |
|---|---|---|
| M1 | KILLED | KILLED |
| M2 | KILLED | KILLED |
| M3 | KILLED | KILLED |
| M4 | KILLED | KILLED |
| M5 | KILLED | KILLED |
| M6 | KILLED | KILLED |
| M7 | KILLED | KILLED |
| M8 | KILLED | KILLED |
| M9 | KILLED | KILLED |
| M10 | KILLED | KILLED |
| M11 | KILLED | KILLED |
| M12 | KILLED | KILLED |
| M13 | KILLED | KILLED |
| M14 | KILLED | KILLED |
| M15 | KILLED | KILLED |
| Killed / applicable | 15 / 15 | 15 / 15 |

All reverts left git status empty in both worktrees. Caveat: the mutation edits are mine and minimal; with pytest -x only the first failing test is seen.

### 3. Cross tests
| Direction | Passed | Failed | Errors | Failure groups |
|---|---|---|---|---|
| KIT code, R22's new tests (5 files copied incl. 1 fixture; 4 test files run) | 10 | 325 | 0 | DESIGN: helper/function names and signatures (174 + 23); module names compare_cli, compare_format, compare_page absent (about 78); output format, JSON field names and page markup (about 47 + CLI text); beyond-brief robustness (503 building page, HTML 500 page, CLI traceback on an unreadable database, about 6). REAL: 0. ENVIRONMENT: 0 |
| R22 code, KIT's new tests (test_compare.py) | 74 | 35 | 0 | DESIGN: JSON key-path names for wait (13), page markup (6), CLI text labels (3), JSON shape keys (3), function name cli_main (1), per-model layout (1), definition of a failed run (8, flagged for a human). REAL: 0. ENVIRONMENT: 0 |

Limit: most cross failures are interface mismatches, so the tests stop before the behaviour they encode.

### 4. Side by side
| Measure | KIT | R22 |
|---|---|---|
| Lint | passed | passed |
| Console suite | 554 passed, 0 failed | 798 passed, 0 failed |
| Install tools + kit suite | 49 passed | 49 passed |
| Commits over base | 3 | 1 |
| New test functions | 79 | 317 |
| New test lines (added) | 1232 (1 file) | 5002 (7 files incl. 50-line json fixture; test_server, test_static, test_store_and_flags edited) |
| Diff stat | 6 files, 2146 insertions, 4 deletions | 19 files, 6826 insertions, 20 deletions |
| Brief items met of 5 | 5 | 5 |
| Mutations killed | 15 / 15 | 15 / 15 |
| Own tests passing on the other arm's code | KIT's tests on R22 code: 74 of 109 | R22's tests on KIT code: 10 of 335 |

No verdict on which process is better.
