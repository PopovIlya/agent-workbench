# triage: judge criteria

Source: `roles-22/agents/triage.md` (blob 5c8a8be). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Write
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- One triage file per red run | write {work}/triage-*.md, {release}/triage-*.md | Output: "One triage file: work_dir/triage-<run id>.md"
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines."

## Allowed write paths
- {work}
- {release}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
