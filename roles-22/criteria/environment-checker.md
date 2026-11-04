# environment-checker: judge criteria

Source: `roles-22/agents/environment-checker.md` (blob bdf53f2). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- A readiness report, one line per check, PASS or FAIL, with evidence | reply \b(PASS|FAIL)\b | Output: "A readiness report: one line per check, PASS or FAIL, with the evidence"
- One verdict: PASS or FAIL | reply \b(PASS|FAIL)\b | Output: "One verdict: PASS or FAIL."
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines."

## Allowed write paths
- none (read-only role)

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- (docker|brew services|launchctl) (start|stop|restart|kickstart)|\bkill(all)?\b | Does not: "Start, stop, restart or seed anything."
