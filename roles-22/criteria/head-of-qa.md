# head-of-qa: judge criteria

Source: `roles-22/agents/head-of-qa.md` (blob 4f9d6f0). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Write
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The GO report, the GO rules one by one, written to the release folder | write {release} | Owns: "The GO report (test completion report)"
- The release test plan at the freeze | write {release} | Owns: "Release test plan at the freeze"

## Allowed write paths
- {release}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
