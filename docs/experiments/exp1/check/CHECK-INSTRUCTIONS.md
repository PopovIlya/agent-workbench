# EXP1 independent check: instructions for the executing session

You are the executing session `[EXP1-CHECK]`. You compare two finished implementations of one brief. You have seen neither run.
Do not edit either branch except to apply and revert a mutation. No verdict on which process is better: only measured facts.

## Reading rules
- You may read: ~/exp1/brief.md, ~/exp1-private/mutations.md, this file, ~/exp1-private/check/oracle.out, and the code and tests in the two worktrees.
- You may NOT read: anything else in ~/exp1/ or ~/exp1-private/, anything in ~/.claude/projects, and `docs/agents/work/` or `docs/requirements/` in either worktree (the arms' own process files). If you find yourself reading one, stop and say so in the report.
- Never touch the console on port 8790 or the folder ~/.agent-console. Use only the ports and folders written in the steps. Never push. Never commit.
- Work only with the commands given. Keep command output short (`| tail -15`).

## Report contract (strict)
Write ~/exp1/check-report.md. Create it with the title line first, then append ONE block per numbered step, immediately after doing it (do not batch). A block has exactly these fields:

    ### STEP <n>
    Action taken: <the command or action, and what you did>
    Expected: <copy from the step>
    Actual: <what you observed: exit codes, counts, the relevant output lines>
    Status: MATCH | MISMATCH | COULD NOT COMPLETE

- MATCH = the observation equals Expected. MISMATCH = it differs (say how in Actual). COULD NOT COMPLETE = you could not do the action (say why).
- For a "record" step, Expected is "record", and Status is MATCH when you recorded it.
- Do NOT skip a step because it should work or because an earlier step passed. Do the action and write what you saw. Do not guess what would have happened.
- If a step depends on an earlier step that failed or was not completed, write: `Action taken: None. Depends on step <n>`, Status COULD NOT COMPLETE. Do not continue past it silently.
- Do not improvise extra checks, do not reorder, do not merge steps.
- Likely wrong turns: (1) the two worktrees are different folders; every command names its folder, do not `cd` elsewhere. (2) The page may answer HTTP 503 for a few seconds while the throwaway console builds its index: poll up to 60 s before calling it a failure. (3) Do not start anything on port 8790. (4) A page whose `/compare` route does not exist answers 404 or the app shell: record exactly what you got.
- After the last step, write the summary tables described at the end. If you have made more than 450 tool calls, stop, write the summary of what you have, and say you stopped.

## Dataset (made once; the same for both arms)
A neutral synthetic log root with known numbers. Expected values are in ~/exp1-private/check/oracle.out. Tickets: CMPA-1 (main session + 3 sub-agent runs), CMPB-1 (one sub-agent run, no main session), CMPC-1 (not used). Unknown key for the error steps: NOPE-9.
Environment for every console or CLI command of an arm (replace <PORT> and <ARM>):
    AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-<ARM> AGENT_CONSOLE_PORT=<PORT> AGENT_CONSOLE_TZ=UTC


### STEP 1. Make the dataset
Action: Run `python3 ~/exp1-private/check/make_dataset.py` and `ls /tmp/exp1-check-logs/-work-app`.
Expected: prints `written /tmp/exp1-check-logs/-work-app`; the folder lists S-A.jsonl, S-A, S-C.jsonl, S-C

### STEP 2. Read the oracle
Action: Run `cat ~/exp1-private/check/oracle.out`.
Expected: record (you will compare each arm against it)


## PART KIT: worktree <awb-kit> (branch exp1/kit)

### STEP 3. KIT: clean state
Action: Run `git -C <awb-kit> status --porcelain` and `git -C <awb-kit> rev-parse --abbrev-ref HEAD` and `git -C <awb-kit> log --oneline 0891a04..HEAD | wc -l`.
Expected: status output empty; branch exp1/kit; record the number of commits

### STEP 4. KIT: lint
Action: Run `cd <awb-kit> && console/.venv/bin/python -m ruff check . | tail -3`.
Expected: `All checks passed!`

### STEP 5. KIT: console suite
Action: Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -4`.
Expected: record: passed and failed counts (0 failed expected)

### STEP 6. KIT: install tools and kit suite
Action: Run `cd <awb-kit> && console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider 2>&1 | tail -3`.
Expected: 49 passed

### STEP 7. KIT: new tests and test lines
Action: Run `cd <awb-kit> && git diff --numstat 0891a04 HEAD -- console/tests` and `git diff 0891a04 HEAD -- console/tests | grep -c '^+def test_'` and `git diff --stat 0891a04 HEAD | tail -1`.
Expected: record: added lines of test files, number of added test functions, total diff stat

### STEP 8. KIT: start a throwaway console
Action: Run `cd <awb-kit>/console && (env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18801 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console > /tmp/exp1-check-kit.log 2>&1 &)` then poll `curl -s http://127.0.0.1:18801/health` every 2 s up to 60 s.
Expected: health answers `{"ok":true,"app":"agent-console"}`

### STEP 9. KIT: brief 1, CLI text
Action: Run `cd <awb-kit>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18801 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1; echo EXIT=$?` (add `| tail -60` before the echo if long).
Expected: exit code 0; a table with a column for CMPA-1, a column for CMPB-1 and a difference column. Record the full output.

### STEP 10. KIT: brief 1, page
Action: Poll `curl -s -o /tmp/exp1-kit-page.html -w '%{http_code}' 'http://127.0.0.1:18801/compare?a=CMPA-1&b=CMPB-1'` until 200 (up to 60 s), then record `python3 -c "import re,html,sys;print(re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',open('/tmp/exp1-kit-page.html').read()))))" | head -c 3000`.
Expected: HTTP 200; the page text shows both tickets side by side with a difference column

### STEP 11. KIT: brief 2, role runs for CMPA-1
Action: From the CLI output of the CLI step (run it again with `--json` if easier), find the role-run figures of CMPA-1.
Expected: total 3, failed 1, repeat rounds 1

### STEP 12. KIT: brief 2, tokens per model for CMPA-1
Action: Find CMPA-1 tokens split into input, output, cache write and cache read, per model.
Expected: sonnet-5-5: input 3200, output 850, cache read 12000, cache write 2500; opus-5-5: input 3000, output 600, cache read 10000, cache write 1000 (a different grouping of the same numbers is a MISMATCH only if a number is wrong; say which)

### STEP 13. KIT: brief 2, cost for CMPA-1
Action: Find CMPA-1 cost per model and in total.
Expected: sonnet 0.02355, opus 0.031, total 0.05455 USD (the page rounds to cents: $0.05; JSON keeps raw values)

### STEP 14. KIT: brief 2, wall time for CMPA-1
Action: Find CMPA-1 wall time.
Expected: 151 min (9030 s) on the page; raw 9030 s in JSON

### STEP 15. KIT: brief 2, active role time for CMPA-1
Action: Find CMPA-1 active role time.
Expected: 18 min (1080 s: runs of 600, 300 and 180 s added up)

### STEP 16. KIT: brief 2, wait on a person for CMPA-1
Action: Find CMPA-1 wait time (and the part from gaps over 2 hours, if shown).
Expected: 130 min (7800 s = 300 + 7500; the 30 s gap counts as zero). Part over 2 h: 7500 s if shown

### STEP 17. KIT: brief 2, main session share for CMPA-1
Action: Find the main-session cost as a share of sub-agent cost for CMPA-1.
Expected: 0.40 (main 0.0155 / sub-agents 0.03905 = 0.3969), shown as a ratio or a percent near 40%

### STEP 18. KIT: brief 2, CMPB-1 has no main session
Action: Look at the rows of CMPB-1 that cover only the main session (main tokens, main cost, main wait, share).
Expected: each shows `no main session` (or equivalent clear words), not 0. Record what each shows.

### STEP 19. KIT: brief 3, difference column
Action: Look at the difference column for total cost (a = CMPA-1, b = CMPB-1).
Expected: b minus a = about -0.0518 USD (page: -$0.05); b divided by a = about 0.05

### STEP 20. KIT: brief 4, unknown key on the page
Action: Run `curl -s -w ' HTTP=%{http_code}' 'http://127.0.0.1:18801/compare?a=CMPA-1&b=NOPE-9' | head -c 1500`.
Expected: a clear error message that names the unknown key; record the HTTP status (any 4xx is acceptable; 200 with the error text is partly met)

### STEP 21. KIT: brief 4, unknown key in the CLI
Action: Run `cd <awb-kit>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18801 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 NOPE-9; echo EXIT=$?`.
Expected: a clear error and EXIT=2

### STEP 22. KIT: brief 5, JSON parses and keys are sorted
Action: Run `cd <awb-kit>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18801 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1 --json > /tmp/exp1-kit.json; echo EXIT=$?` then `python3 ~/exp1-private/check/chk_json.py /tmp/exp1-kit.json`.
Expected: EXIT=0; `parsed`; `KEYS_SORTED True`

### STEP 23. KIT: brief 5, JSON is stable
Action: Run the same `--json` command twice and compare: `cd <awb-kit>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18801 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1 --json | md5; cd <awb-kit>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18801 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1 --json | md5`.
Expected: the two checksums are equal

### STEP 24. KIT: brief 1, no arguments starts the server
Action: Run `cd <awb-kit>/console && (env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-kit AGENT_CONSOLE_PORT=18901 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console > /tmp/exp1-check-kit-noarg.log 2>&1 &)` with AGENT_CONSOLE_PORT changed to 18901, poll `/health` on that port up to 30 s, then stop that process only (find its pid with `lsof -nP -iTCP:18901 -sTCP:LISTEN -t`).
Expected: health answers on port 18901; the process is then stopped

### STEP 25. KIT: stop the throwaway console
Action: Stop the console started for this part: `kill $(lsof -nP -iTCP:18801 -sTCP:LISTEN -t)`; then `lsof -nP -iTCP:18801 -sTCP:LISTEN | wc -l`.
Expected: 0 listeners left

### STEP 26. KIT: mutation M1
Action: Read row M1 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 27. KIT: mutation M2
Action: Read row M2 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 28. KIT: mutation M3
Action: Read row M3 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 29. KIT: mutation M4
Action: Read row M4 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 30. KIT: mutation M5
Action: Read row M5 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 31. KIT: mutation M6
Action: Read row M6 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 32. KIT: mutation M7
Action: Read row M7 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 33. KIT: mutation M8
Action: Read row M8 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 34. KIT: mutation M9
Action: Read row M9 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 35. KIT: mutation M10
Action: Read row M10 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 36. KIT: mutation M11
Action: Read row M11 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 37. KIT: mutation M12
Action: Read row M12 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 38. KIT: mutation M13
Action: Read row M13 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 39. KIT: mutation M14
Action: Read row M14 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 40. KIT: mutation M15
Action: Read row M15 of ~/exp1-private/mutations.md. In <awb-kit>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-kit>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-kit> checkout -- .` and run `git -C <awb-kit> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)


## PART R22: worktree <awb-r22> (branch exp1/r22)

### STEP 41. R22: clean state
Action: Run `git -C <awb-r22> status --porcelain` and `git -C <awb-r22> rev-parse --abbrev-ref HEAD` and `git -C <awb-r22> log --oneline 0891a04..HEAD | wc -l`.
Expected: status output empty; branch exp1/r22; record the number of commits

### STEP 42. R22: lint
Action: Run `cd <awb-r22> && console/.venv/bin/python -m ruff check . | tail -3`.
Expected: `All checks passed!`

### STEP 43. R22: console suite
Action: Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -4`.
Expected: record: passed and failed counts (0 failed expected)

### STEP 44. R22: install tools and kit suite
Action: Run `cd <awb-r22> && console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider 2>&1 | tail -3`.
Expected: 49 passed

### STEP 45. R22: new tests and test lines
Action: Run `cd <awb-r22> && git diff --numstat 0891a04 HEAD -- console/tests` and `git diff 0891a04 HEAD -- console/tests | grep -c '^+def test_'` and `git diff --stat 0891a04 HEAD | tail -1`.
Expected: record: added lines of test files, number of added test functions, total diff stat

### STEP 46. R22: start a throwaway console
Action: Run `cd <awb-r22>/console && (env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18802 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console > /tmp/exp1-check-r22.log 2>&1 &)` then poll `curl -s http://127.0.0.1:18802/health` every 2 s up to 60 s.
Expected: health answers `{"ok":true,"app":"agent-console"}`

### STEP 47. R22: brief 1, CLI text
Action: Run `cd <awb-r22>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18802 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1; echo EXIT=$?` (add `| tail -60` before the echo if long).
Expected: exit code 0; a table with a column for CMPA-1, a column for CMPB-1 and a difference column. Record the full output.

### STEP 48. R22: brief 1, page
Action: Poll `curl -s -o /tmp/exp1-r22-page.html -w '%{http_code}' 'http://127.0.0.1:18802/compare?a=CMPA-1&b=CMPB-1'` until 200 (up to 60 s), then record `python3 -c "import re,html,sys;print(re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',open('/tmp/exp1-r22-page.html').read()))))" | head -c 3000`.
Expected: HTTP 200; the page text shows both tickets side by side with a difference column

### STEP 49. R22: brief 2, role runs for CMPA-1
Action: From the CLI output of the CLI step (run it again with `--json` if easier), find the role-run figures of CMPA-1.
Expected: total 3, failed 1, repeat rounds 1

### STEP 50. R22: brief 2, tokens per model for CMPA-1
Action: Find CMPA-1 tokens split into input, output, cache write and cache read, per model.
Expected: sonnet-5-5: input 3200, output 850, cache read 12000, cache write 2500; opus-5-5: input 3000, output 600, cache read 10000, cache write 1000 (a different grouping of the same numbers is a MISMATCH only if a number is wrong; say which)

### STEP 51. R22: brief 2, cost for CMPA-1
Action: Find CMPA-1 cost per model and in total.
Expected: sonnet 0.02355, opus 0.031, total 0.05455 USD (the page rounds to cents: $0.05; JSON keeps raw values)

### STEP 52. R22: brief 2, wall time for CMPA-1
Action: Find CMPA-1 wall time.
Expected: 151 min (9030 s) on the page; raw 9030 s in JSON

### STEP 53. R22: brief 2, active role time for CMPA-1
Action: Find CMPA-1 active role time.
Expected: 18 min (1080 s: runs of 600, 300 and 180 s added up)

### STEP 54. R22: brief 2, wait on a person for CMPA-1
Action: Find CMPA-1 wait time (and the part from gaps over 2 hours, if shown).
Expected: 130 min (7800 s = 300 + 7500; the 30 s gap counts as zero). Part over 2 h: 7500 s if shown

### STEP 55. R22: brief 2, main session share for CMPA-1
Action: Find the main-session cost as a share of sub-agent cost for CMPA-1.
Expected: 0.40 (main 0.0155 / sub-agents 0.03905 = 0.3969), shown as a ratio or a percent near 40%

### STEP 56. R22: brief 2, CMPB-1 has no main session
Action: Look at the rows of CMPB-1 that cover only the main session (main tokens, main cost, main wait, share).
Expected: each shows `no main session` (or equivalent clear words), not 0. Record what each shows.

### STEP 57. R22: brief 3, difference column
Action: Look at the difference column for total cost (a = CMPA-1, b = CMPB-1).
Expected: b minus a = about -0.0518 USD (page: -$0.05); b divided by a = about 0.05

### STEP 58. R22: brief 4, unknown key on the page
Action: Run `curl -s -w ' HTTP=%{http_code}' 'http://127.0.0.1:18802/compare?a=CMPA-1&b=NOPE-9' | head -c 1500`.
Expected: a clear error message that names the unknown key; record the HTTP status (any 4xx is acceptable; 200 with the error text is partly met)

### STEP 59. R22: brief 4, unknown key in the CLI
Action: Run `cd <awb-r22>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18802 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 NOPE-9; echo EXIT=$?`.
Expected: a clear error and EXIT=2

### STEP 60. R22: brief 5, JSON parses and keys are sorted
Action: Run `cd <awb-r22>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18802 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1 --json > /tmp/exp1-r22.json; echo EXIT=$?` then `python3 ~/exp1-private/check/chk_json.py /tmp/exp1-r22.json`.
Expected: EXIT=0; `parsed`; `KEYS_SORTED True`

### STEP 61. R22: brief 5, JSON is stable
Action: Run the same `--json` command twice and compare: `cd <awb-r22>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18802 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1 --json | md5; cd <awb-r22>/console && env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18802 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console compare CMPA-1 CMPB-1 --json | md5`.
Expected: the two checksums are equal

### STEP 62. R22: brief 1, no arguments starts the server
Action: Run `cd <awb-r22>/console && (env AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-r22 AGENT_CONSOLE_PORT=18902 AGENT_CONSOLE_TZ=UTC .venv/bin/python -m agent_console > /tmp/exp1-check-r22-noarg.log 2>&1 &)` with AGENT_CONSOLE_PORT changed to 18902, poll `/health` on that port up to 30 s, then stop that process only (find its pid with `lsof -nP -iTCP:18902 -sTCP:LISTEN -t`).
Expected: health answers on port 18902; the process is then stopped

### STEP 63. R22: stop the throwaway console
Action: Stop the console started for this part: `kill $(lsof -nP -iTCP:18802 -sTCP:LISTEN -t)`; then `lsof -nP -iTCP:18802 -sTCP:LISTEN | wc -l`.
Expected: 0 listeners left

### STEP 64. R22: mutation M1
Action: Read row M1 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 65. R22: mutation M2
Action: Read row M2 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 66. R22: mutation M3
Action: Read row M3 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 67. R22: mutation M4
Action: Read row M4 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 68. R22: mutation M5
Action: Read row M5 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 69. R22: mutation M6
Action: Read row M6 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 70. R22: mutation M7
Action: Read row M7 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 71. R22: mutation M8
Action: Read row M8 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 72. R22: mutation M9
Action: Read row M9 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 73. R22: mutation M10
Action: Read row M10 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 74. R22: mutation M11
Action: Read row M11 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 75. R22: mutation M12
Action: Read row M12 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 76. R22: mutation M13
Action: Read row M13 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 77. R22: mutation M14
Action: Read row M14 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)

### STEP 78. R22: mutation M15
Action: Read row M15 of ~/exp1-private/mutations.md. In <awb-r22>/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd <awb-r22>/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C <awb-r22> checkout -- .` and run `git -C <awb-r22> status --porcelain`.
Expected: KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)


## PART CROSS: each arm's new tests on the other arm's code

### STEP 79. KIT code, R22 tests: make a scratch copy
Action: Run `rm -rf /tmp/exp1-scratch-kit && cp -R <awb-kit> /tmp/exp1-scratch-kit` and then copy the files that R22 ADDED under console/tests: `cd <awb-r22> && git diff --name-only --diff-filter=A 0891a04 HEAD -- console/tests` lists them; copy each to the same path under /tmp/exp1-scratch-kit.
Expected: scratch copy exists; the list of copied files is recorded

### STEP 80. KIT code, R22 tests: run them
Action: Run `cd /tmp/exp1-scratch-kit/console && .venv/bin/python -m pytest <the copied test files> -q -p no:cacheprovider 2>&1 | tail -25`.
Expected: record: passed, failed and errors

### STEP 81. KIT code, R22 tests: classify failures
Action: For the failing tests (group them by cause; at most 10 groups), write for each group: a count, one example test name, the cause, and the class: REAL (the code lacks a behaviour the brief asks for), DESIGN (a different name, module, signature or output format), or ENVIRONMENT. Judge only from the brief.
Expected: record

### STEP 82. KIT code, R22 tests: clean up
Action: Run `rm -rf /tmp/exp1-scratch-kit` and `git -C <awb-kit> status --porcelain`.
Expected: scratch removed; worktree status empty

### STEP 83. R22 code, KIT tests: make a scratch copy
Action: Run `rm -rf /tmp/exp1-scratch-r22 && cp -R <awb-r22> /tmp/exp1-scratch-r22` and then copy the files that KIT ADDED under console/tests: `cd <awb-kit> && git diff --name-only --diff-filter=A 0891a04 HEAD -- console/tests` lists them; copy each to the same path under /tmp/exp1-scratch-r22.
Expected: scratch copy exists; the list of copied files is recorded

### STEP 84. R22 code, KIT tests: run them
Action: Run `cd /tmp/exp1-scratch-r22/console && .venv/bin/python -m pytest <the copied test files> -q -p no:cacheprovider 2>&1 | tail -25`.
Expected: record: passed, failed and errors

### STEP 85. R22 code, KIT tests: classify failures
Action: For the failing tests (group them by cause; at most 10 groups), write for each group: a count, one example test name, the cause, and the class: REAL (the code lacks a behaviour the brief asks for), DESIGN (a different name, module, signature or output format), or ENVIRONMENT. Judge only from the brief.
Expected: record

### STEP 86. R22 code, KIT tests: clean up
Action: Run `rm -rf /tmp/exp1-scratch-r22` and `git -C <awb-r22> status --porcelain`.
Expected: scratch removed; worktree status empty


## After the last step: summary tables (append to the report)
1. One table per part (KIT, R22): requirement results for brief items 1 to 5 (met / partly met / not met, with the step numbers as evidence).
2. Mutations: a table of M1..M15 for each arm: KILLED / SURVIVED / NOT APPLICABLE; the count killed out of the applicable ones.
3. Cross tests: for each direction, passed / failed, and the failure groups with their class.
4. Final side by side table: suite pass/fail and counts, new tests, test lines, items met of 5, mutations killed, own tests passing on the other arm's code.
No verdict on which process is better.
