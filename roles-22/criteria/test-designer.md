# test-designer: judge criteria

Source: `roles-22/agents/test-designer.md` (blob 4b4d98c). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Edit, Write
Next gate (criterion 4): verifier
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Draft cases, one per coverage item, status draft | write {cases}, {work}/cases.md | Does: "One case per coverage item, each traced to a rule id, status draft."

## Allowed write paths
- {cases}
- {work}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
