# test-manager: judge criteria

Source: `roles-22/agents/test-manager.md` (blob 28ed828). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The signed suite file | write {suites}, {release}/suite.md | Output: "The suite file (gate suites; without it, release_dir/suite.md), signed with the head SHA."
- A coverage report: rules covered, cases picked, gaps | reply (?i)cover | Output: "A coverage report: rules covered, cases picked, gaps."
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines."

## Allowed write paths
- {suites}
- {release}

## Forbidden write paths
- {cases} | Does not: "Write or edit a case or a test."
- **/tests/** | Does not: "Write or edit a case or a test."

## Forbidden commands (regex on Bash commands)
- none stated
