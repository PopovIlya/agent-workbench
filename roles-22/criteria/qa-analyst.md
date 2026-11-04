# qa-analyst: judge criteria

Source: `roles-22/agents/qa-analyst.md` (blob 35e189f). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Edit, Write
Next gate (criterion 4): requirements-reviewer
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Test conditions and coverage items | none | Does: "writes the test conditions and coverage items"
- Risk class on each rule in the requirement map | write {requirements} | Does: "The risk class is a field of the rule in the requirement map"
- Ticket size in the change file's header line | write {change} | Does: "the ticket size goes in the change file's header line"
- A short report in your reply | reply | Always: "the verdict and the evidence paths"

## Allowed write paths
- {requirements}
- {change}
- {work}
- docs/requirements/**

## Forbidden write paths
- {cases} | Does not: "Write cases (the test designers do) or code."

## Forbidden commands (regex on Bash commands)
- none stated
