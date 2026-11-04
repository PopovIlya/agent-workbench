# business-analyst: judge criteria

Source: `roles-22/agents/business-analyst.md` (blob 27dc66e). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Edit, Write, Bash
Next gate (criterion 4): requirements-reviewer
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The rules written into the requirement map (id, rule, version, status, risk class, ticket key, source, date) | write {requirements} | Does: "Writes the rules into the requirement map, in its format"
- A short report in your reply | reply | Always: "the verdict and the evidence paths"

## Allowed write paths
- {requirements}
- {change}
- {work}
- docs/requirements/**

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
