# requirements-reviewer: judge criteria

Source: `roles-22/agents/requirements-reviewer.md` (blob da99c3b). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- A review report with the verdict PASS or REJECT | reply \b(PASS|REJECT)\b | Output: "A review report: verdict PASS or REJECT."
- Each finding: rule id · what is wrong · how it should be | reply | Output: "Each finding: rule id · what is wrong · how it should be."
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines."

## Allowed write paths
- none (read-only role)

## Forbidden write paths
- {requirements} | Does not: "Edit a rule, a change file or a ticket."

## Forbidden commands (regex on Bash commands)
- none stated
