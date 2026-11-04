# hostile-verifier: judge criteria

Source: `roles-22/agents/hostile-verifier.md` (blob aab5d32). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Edit, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Each bug recorded (steps to reproduce / actual / expected, severity, rule id, case id) | write {suites}, {work}/bugs.md | Does: "Records each bug where the verifier records them"
- A verdict, PASS only on the final head with 0 open bugs | reply \bPASS\b|\bFAIL\b|REJECT | Does: "PASS only on the final head, with 0 open bugs in the ticket's own work."

## Allowed write paths
- {suites}
- {work}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
