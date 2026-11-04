# system-analyst: judge criteria

Source: `roles-22/agents/system-analyst.md` (blob 5f682a7). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Write, Bash
Next gate (criterion 4): requirements-reviewer
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The change file, one per ticket | write {change} | Does: "Writes the change file, one per ticket"
- The modules the build will change | contains module | Does: "Lists the modules the build will change."

## Allowed write paths
- {requirements}
- {change}
- {work}
- docs/requirements/**

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
