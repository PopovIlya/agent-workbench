# test-runner: judge criteria

Source: `roles-22/agents/test-runner.md` (blob 7a95062). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- A report: passed, failed, skipped, the head SHA, the log path | reply (?i)passed|failed | Output: "A report: passed, failed, skipped, the head SHA, the log path."
- The result file next to the suite, written by the runner | none | Output: "The result file next to the suite, written by the runner."

## Allowed write paths
- none (the runner writes the result file)

## Forbidden write paths
- {cases} | Does not: "Edit a case, a test or the suite file."
- **/tests/** | Does not: "Edit a case, a test or the suite file."

## Forbidden commands (regex on Bash commands)
- none stated
