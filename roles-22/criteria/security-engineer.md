# security-engineer: judge criteria

Source: `roles-22/agents/security-engineer.md` (blob c4e3d45). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Findings in the reply: steps to reproduce / actual / expected, severity, route or field, fix recommendation | reply | Rules: "Findings: Steps to reproduce / Actual result / Expected result, severity, route or field, fix recommendation."

## Allowed write paths
- none (findings go in the reply)

## Forbidden write paths
- docs/** | Rules: "Findings go in your reply, not in a file you write yourself."

## Forbidden commands (regex on Bash commands)
- none stated
