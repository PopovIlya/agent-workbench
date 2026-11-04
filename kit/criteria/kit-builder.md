# kit-builder: judge criteria

Source: `kit/agents/kit-builder.md` (blob 69f7880). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. The kit roles run in other repos, so paths are relative to the repo the role ran in.
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Write, Edit, Bash
Next gate (criterion 4): kit-reviewer, kit-verifier
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The product change | none | Output: "Step `code`: the product change only."
- The report with the verdict first and every decision no rule covers | write docs/agents/work/*/builder.md | Output: "The report lists **every decision no rule covers**"
- The final reply is the verdict word and the report path | reply ^(PASS|FAIL|BLOCKED|QUESTIONS)\b | Output: "Final reply to the main session"

## Allowed write paths
- not stated (project-specific: PROJECT.md says where code and tests live)

## Forbidden write paths
- docs/requirements/** | Must not: "Edit ... the requirements map"

## Forbidden commands (regex on Bash commands)
- git (commit|push)\b|gh pr|glab mr | Must not: "Commit, push, open merge requests"
