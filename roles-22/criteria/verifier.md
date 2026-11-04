# verifier: judge criteria

Source: `roles-22/agents/verifier.md` (blob 406fd95). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Write, Bash, Grep, Glob
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- One structured report: per-DoD-line results, overall verdict, git status --porcelain confirmation | reply (?i)verdict | Output: "Overall verdict: did every checkable DoD line reach Verified."
- The git status --porcelain confirmation | reply porcelain | Steps 6: "run git status --porcelain in the worktree and confirm it is clean."

## Allowed write paths
- {suites}
- {work}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
