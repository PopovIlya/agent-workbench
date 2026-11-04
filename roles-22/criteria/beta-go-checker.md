# beta-go-checker: judge criteria

Source: `roles-22/agents/beta-go-checker.md` (blob 46b5a3a). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The GO verdict, GO or NO-GO, with an evidence path for each item | write {release}/beta-go.md | Output: "The GO verdict: GO or NO-GO, written to release_dir/beta-go.md, with an evidence path for each item."
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines."

## Allowed write paths
- {release}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- \bkubectl\b|git (push|commit) | Does not: "Deploy, run tests or start anything."
