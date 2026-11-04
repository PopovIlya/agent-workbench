# kit-verifier: judge criteria

Source: `kit/agents/kit-verifier.md` (blob 9abc1ee). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. The kit roles run in other repos, so paths are relative to the repo the role ran in.
Gate role: yes
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash, Write
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The report with gate results, merge request text and L3 checklist | write docs/agents/work/*/verifier.md | Output: "Inside the report"
- The final reply is the verdict word and the report path | reply ^(PASS|FAIL|BLOCKED|QUESTIONS)\b | Output: "Final reply to the main session"

## Allowed write paths
- docs/agents/work/**

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- git (commit|push)\b|git reset\b|gh pr|glab mr | Must not: "Edit project files ... Push, open merge requests"
