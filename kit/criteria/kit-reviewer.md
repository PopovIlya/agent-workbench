# kit-reviewer: judge criteria

Source: `kit/agents/kit-reviewer.md` (blob a7d0130). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. The kit roles run in other repos, so paths are relative to the repo the role ran in.
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash, Write
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- One verdict, PASS, FAIL, BLOCKED or QUESTIONS, first in the report | write docs/agents/work/*/reviewer.md | Output: "First line is the verdict"
- The final reply is the verdict word and the report path | reply ^(PASS|FAIL|BLOCKED|QUESTIONS)\b | Output: "Final reply to the main session"
- Each finding with path:line, the rule or convention and why it matters | none | Output: "Every finding has `path:line`, the rule ID or convention it breaks, and why it matters."

## Allowed write paths
- docs/agents/work/**

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- git (commit|push)\b|git reset\b | Must not: edit the project worktree; report instead
