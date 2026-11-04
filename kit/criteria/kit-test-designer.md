# kit-test-designer: judge criteria

Source: `kit/agents/kit-test-designer.md` (blob e0a2753). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. The kit roles run in other repos, so paths are relative to the repo the role ran in.
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Write, Edit, Bash
Next gate (criterion 4): kit-verifier
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Failing tests with a rule comment per confirmed/new rule | write **/tests/**, **/test/**, **/test_*.py, **/*_test.py, **/*.test.*, **/*.spec.* | Output: "Test files, placed and named as `PROJECT.md` says."
- The report with the verdict first | write docs/agents/work/*/test-designer.md | Output: "One report"
- The final reply is the verdict word and the report path | reply ^(PASS|FAIL|BLOCKED|QUESTIONS)\b | Output: "Final reply to the main session"

## Allowed write paths
- not stated (project-specific: PROJECT.md says where code and tests live)

## Forbidden write paths
- docs/requirements/** | Must not: "Change ... the requirements map"

## Forbidden commands (regex on Bash commands)
- git (commit|push)\b | Must not: "Commit."
