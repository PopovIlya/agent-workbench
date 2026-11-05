PASS

# Security report, EXP1-KITC, round 1

Workbench: <workbench>. Reviewed: working tree against HEAD 0891a04 (server.py, __main__.py, compare.py, test_compare.py).

## Summary
No high or medium findings. Two low notes.

## Checked
- Raw prompt/reply leakage: compare.py reads session files read-only (`_records`) and keeps only booleans, counts and timestamps. `run_failed` and `main_waits` do not return or store text. Output holds only counts, seconds, token numbers, model names and the two user keys. OK.
- Tests prove it: test_compare.py plants SENTINEL-PROMPT, SENTINEL-REPLY, SENTINEL-DENY and SENTINEL-ERROR in prompts, replies, denials and api errors (about lines 39-41, 117, 130, 385-390) and asserts (about line 449) they are absent. A leak into the text, JSON or page would fail them. UNVERIFIED: I did not run the tests or mutate the code.
- Injection: all SQL uses `?` parameters (compare.py `_ticket`). The user keys never reach a path, command or header. File paths come from the index, not from input.
- HTML: keys, model names and error messages go through `html.escape` (`render_html`, `render_error`). The unknown-key 404 reflects the key, but it is escaped and sent as HTMLResponse. OK.
- Endpoint: GET /compare is read-only, writes nothing and adds no new write path. The key length cap of 60 is enforced on the server side. Access control is the same as the rest of the console (local server). UNVERIFIED: how the existing app restricts Host or binding. The diff does not change it.
- JSON uses `allow_nan=False`, so no invalid JSON is produced.

## Findings
1. low, console/agent_console/compare.py `cli_main`: CLI keys have no length or character limit, and `render_text` / the unknown-key message echo them to the terminal. A key with control or escape sequences would be printed raw to the user's own terminal. Impact is self-inflicted only. Fix: strip or repr-escape non-printable characters in echoed keys.
2. low, console/agent_console/server.py `compare_page`: the 404 versus 200 response tells whether a ticket key exists in the index. Not sensitive for a local single-user console. No fix needed. Keep the page behind the same local-only binding as the other routes.
