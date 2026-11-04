# independent-auditor: judge criteria

Source: `roles-22/agents/independent-auditor.md` (blob 5e53b88). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- A verdict: each GO rule met / not met, with the evidence path | reply (?i)\bnot met\b|\bmet\b | Does: "Verdict: each GO rule met / not met, with the evidence path."

## Allowed write paths
- none (read-only role)

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
