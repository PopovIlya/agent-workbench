# deployer: judge criteria

Source: `roles-22/agents/deployer.md` (blob 63e0cea). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- A deploy report: tag deployed, version read back, time | reply (?i)tag|version | Output: "A deploy report: tag deployed, version read back, time."
- The smoke results path and counts | reply (?i)smoke | Output: "The smoke results path and counts."
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines."

## Allowed write paths
- not stated

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- \bkubectl\b | Does not: "Use a cluster or cloud console directly"
- git (push|merge) | Does not: "Merge, push, or change anything in the tracker or the code host."
