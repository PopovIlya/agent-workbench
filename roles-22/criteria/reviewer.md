# reviewer: judge criteria

Source: `roles-22/agents/reviewer.md` (blob fc8721f). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- One verdict, PASS or REJECT | reply \b(PASS|REJECT)\b | Main goal / Does: "One verdict: PASS or REJECT."
- Each finding with severity, file:line, rule and the fix as it should be | reply | Rules for every finding: "SEVERITY · file:line (at the head SHA) · rule id or convention § · what is wrong · how it should be"

## Allowed write paths
- none (read-only role)

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- git (commit|push|merge|checkout|switch|reset) | Does not: "fix, edit, commit, push, merge"; Steps: "Never check out, never write in the repo."
