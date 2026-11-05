#!/usr/bin/env python3
import os
ARMS = [("KIT", "<awb-kit>", "exp1/kit", 18801), ("R22", "<awb-r22>", "exp1/r22", 18802)]
BASE = "0891a04"
out = []
n = [0]
def step(title, action, expected):
    n[0] += 1
    out.append("### STEP %d. %s\nAction: %s\nExpected: %s\n" % (n[0], title, action, expected))
out.append("""# EXP1 independent check: instructions for the executing session

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

""")
step("Make the dataset", "Run `python3 ~/exp1-private/check/make_dataset.py` and `ls /tmp/exp1-check-logs/-work-app`.", "prints `written /tmp/exp1-check-logs/-work-app`; the folder lists S-A.jsonl, S-A, S-C.jsonl, S-C")
step("Read the oracle", "Run `cat ~/exp1-private/check/oracle.out`.", "record (you will compare each arm against it)")
for arm, d, br, port in ARMS:
    A = arm.lower()
    env = "AGENT_CONSOLE_LOG_ROOT=/tmp/exp1-check-logs AGENT_CONSOLE_HOME=/tmp/exp1-check-home-%s AGENT_CONSOLE_PORT=%d AGENT_CONSOLE_TZ=UTC" % (A, port)
    cli = "cd %s/console && env %s .venv/bin/python -m agent_console compare" % (d, env)
    out.append("\n## PART %s: worktree %s (branch %s)\n" % (arm, d, br))
    step("%s: clean state" % arm, "Run `git -C %s status --porcelain` and `git -C %s rev-parse --abbrev-ref HEAD` and `git -C %s log --oneline %s..HEAD | wc -l`." % (d, d, d, BASE), "status output empty; branch %s; record the number of commits" % br)
    step("%s: lint" % arm, "Run `cd %s && console/.venv/bin/python -m ruff check . | tail -3`." % d, "`All checks passed!`")
    step("%s: console suite" % arm, "Run `cd %s/console && .venv/bin/python -m pytest tests -q -p no:cacheprovider 2>&1 | tail -4`." % d, "record: passed and failed counts (0 failed expected)")
    step("%s: install tools and kit suite" % arm, "Run `cd %s && console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider 2>&1 | tail -3`." % d, "49 passed")
    step("%s: new tests and test lines" % arm, "Run `cd %s && git diff --numstat %s HEAD -- console/tests` and `git diff %s HEAD -- console/tests | grep -c '^+def test_'` and `git diff --stat %s HEAD | tail -1`." % (d, BASE, BASE, BASE), "record: added lines of test files, number of added test functions, total diff stat")
    step("%s: start a throwaway console" % arm, "Run `cd %s/console && (env %s .venv/bin/python -m agent_console > /tmp/exp1-check-%s.log 2>&1 &)` then poll `curl -s http://127.0.0.1:%d/health` every 2 s up to 60 s." % (d, env, A, port), "health answers `{\"ok\":true,\"app\":\"agent-console\"}`")
    step("%s: brief 1, CLI text" % arm, "Run `%s CMPA-1 CMPB-1; echo EXIT=$?` (add `| tail -60` before the echo if long)." % cli, "exit code 0; a table with a column for CMPA-1, a column for CMPB-1 and a difference column. Record the full output.")
    step("%s: brief 1, page" % arm, "Poll `curl -s -o /tmp/exp1-%s-page.html -w '%%{http_code}' 'http://127.0.0.1:%d/compare?a=CMPA-1&b=CMPB-1'` until 200 (up to 60 s), then record `python3 -c \"import re,html,sys;print(re.sub(r'\\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',open('/tmp/exp1-%s-page.html').read()))))\" | head -c 3000`." % (A, port, A), "HTTP 200; the page text shows both tickets side by side with a difference column")
    step("%s: brief 2, role runs for CMPA-1" % arm, "From the CLI output of the CLI step (run it again with `--json` if easier), find the role-run figures of CMPA-1.", "total 3, failed 1, repeat rounds 1")
    step("%s: brief 2, tokens per model for CMPA-1" % arm, "Find CMPA-1 tokens split into input, output, cache write and cache read, per model.", "sonnet-5-5: input 3200, output 850, cache read 12000, cache write 2500; opus-5-5: input 3000, output 600, cache read 10000, cache write 1000 (a different grouping of the same numbers is a MISMATCH only if a number is wrong; say which)")
    step("%s: brief 2, cost for CMPA-1" % arm, "Find CMPA-1 cost per model and in total.", "sonnet 0.02355, opus 0.031, total 0.05455 USD (the page rounds to cents: $0.05; JSON keeps raw values)")
    step("%s: brief 2, wall time for CMPA-1" % arm, "Find CMPA-1 wall time.", "151 min (9030 s) on the page; raw 9030 s in JSON")
    step("%s: brief 2, active role time for CMPA-1" % arm, "Find CMPA-1 active role time.", "18 min (1080 s: runs of 600, 300 and 180 s added up)")
    step("%s: brief 2, wait on a person for CMPA-1" % arm, "Find CMPA-1 wait time (and the part from gaps over 2 hours, if shown).", "130 min (7800 s = 300 + 7500; the 30 s gap counts as zero). Part over 2 h: 7500 s if shown")
    step("%s: brief 2, main session share for CMPA-1" % arm, "Find the main-session cost as a share of sub-agent cost for CMPA-1.", "0.40 (main 0.0155 / sub-agents 0.03905 = 0.3969), shown as a ratio or a percent near 40%")
    step("%s: brief 2, CMPB-1 has no main session" % arm, "Look at the rows of CMPB-1 that cover only the main session (main tokens, main cost, main wait, share).", "each shows `no main session` (or equivalent clear words), not 0. Record what each shows.")
    step("%s: brief 3, difference column" % arm, "Look at the difference column for total cost (a = CMPA-1, b = CMPB-1).", "b minus a = about -0.0518 USD (page: -$0.05); b divided by a = about 0.05")
    step("%s: brief 4, unknown key on the page" % arm, "Run `curl -s -w ' HTTP=%%{http_code}' 'http://127.0.0.1:%d/compare?a=CMPA-1&b=NOPE-9' | head -c 1500`." % port, "a clear error message that names the unknown key; record the HTTP status (any 4xx is acceptable; 200 with the error text is partly met)")
    step("%s: brief 4, unknown key in the CLI" % arm, "Run `%s CMPA-1 NOPE-9; echo EXIT=$?`." % cli, "a clear error and EXIT=2")
    step("%s: brief 5, JSON parses and keys are sorted" % arm, "Run `%s CMPA-1 CMPB-1 --json > /tmp/exp1-%s.json; echo EXIT=$?` then `python3 ~/exp1-private/check/chk_json.py /tmp/exp1-%s.json`." % (cli, A, A), "EXIT=0; `parsed`; `KEYS_SORTED True`")
    step("%s: brief 5, JSON is stable" % arm, "Run the same `--json` command twice and compare: `%s CMPA-1 CMPB-1 --json | md5; %s CMPA-1 CMPB-1 --json | md5`." % (cli, cli), "the two checksums are equal")
    step("%s: brief 1, no arguments starts the server" % arm, "Run `cd %s/console && (env %s .venv/bin/python -m agent_console > /tmp/exp1-check-%s-noarg.log 2>&1 &)` with AGENT_CONSOLE_PORT changed to %d, poll `/health` on that port up to 30 s, then stop that process only (find its pid with `lsof -nP -iTCP:%d -sTCP:LISTEN -t`)." % (d, env.replace("PORT=%d" % port, "PORT=%d" % (port + 100)), A, port + 100, port + 100), "health answers on port %d; the process is then stopped" % (port + 100))
    step("%s: stop the throwaway console" % arm, "Stop the console started for this part: `kill $(lsof -nP -iTCP:%d -sTCP:LISTEN -t)`; then `lsof -nP -iTCP:%d -sTCP:LISTEN | wc -l`." % (port, port), "0 listeners left")
    for i in range(1, 16):
        step("%s: mutation M%d" % (arm, i), "Read row M%d of ~/exp1-private/mutations.md. In %s/console/agent_console find the code that does that thing and break it as described (a minimal edit). Run `cd %s/console && .venv/bin/python -m pytest tests -q -x -p no:cacheprovider 2>&1 | tail -4`. Record KILLED (at least one test fails) or SURVIVED (all pass), or NOT APPLICABLE with the reason. Then revert with `git -C %s checkout -- .` and run `git -C %s status --porcelain`." % (i, d, d, d, d), "KILLED, and `git status --porcelain` empty after the revert. (If SURVIVED, Status is MISMATCH. If NOT APPLICABLE, say why and use Status MATCH.)")
# cross tests
out.append("\n## PART CROSS: each arm's new tests on the other arm's code\n")
for arm, d, br, port in ARMS:
    o = [x for x in ARMS if x[0] != arm][0]
    A = arm.lower(); OA = o[0].lower()
    step("%s code, %s tests: make a scratch copy" % (arm, o[0]), "Run `rm -rf /tmp/exp1-scratch-%s && cp -R %s /tmp/exp1-scratch-%s` and then copy the files that %s ADDED under console/tests: `cd %s && git diff --name-only --diff-filter=A %s HEAD -- console/tests` lists them; copy each to the same path under /tmp/exp1-scratch-%s." % (A, d, A, o[0], o[1], BASE, A), "scratch copy exists; the list of copied files is recorded")
    step("%s code, %s tests: run them" % (arm, o[0]), "Run `cd /tmp/exp1-scratch-%s/console && .venv/bin/python -m pytest <the copied test files> -q -p no:cacheprovider 2>&1 | tail -25`." % A, "record: passed, failed and errors")
    step("%s code, %s tests: classify failures" % (arm, o[0]), "For the failing tests (group them by cause; at most 10 groups), write for each group: a count, one example test name, the cause, and the class: REAL (the code lacks a behaviour the brief asks for), DESIGN (a different name, module, signature or output format), or ENVIRONMENT. Judge only from the brief.", "record")
    step("%s code, %s tests: clean up" % (arm, o[0]), "Run `rm -rf /tmp/exp1-scratch-%s` and `git -C %s status --porcelain`." % (A, d), "scratch removed; worktree status empty")
out.append("""
## After the last step: summary tables (append to the report)
1. One table per part (KIT, R22): requirement results for brief items 1 to 5 (met / partly met / not met, with the step numbers as evidence).
2. Mutations: a table of M1..M15 for each arm: KILLED / SURVIVED / NOT APPLICABLE; the count killed out of the applicable ones.
3. Cross tests: for each direction, passed / failed, and the failure groups with their class.
4. Final side by side table: suite pass/fail and counts, new tests, test lines, items met of 5, mutations killed, own tests passing on the other arm's code.
No verdict on which process is better.
""")
open(os.path.expanduser("~/exp1-private/check/CHECK-INSTRUCTIONS.md"), "w").write("\n".join(out))
print("steps:", n[0])
