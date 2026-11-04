# kit-analyst: judge criteria

Source: `kit/agents/kit-analyst.md` (blob dddb623). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. The kit roles run in other repos, so paths are relative to the repo the role ran in.
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Write, Edit, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The report with the verdict first, one per mode | write docs/agents/work/*/analyst-as-is.md, docs/agents/work/*/analyst-delta.md | Output: "One report per mode, so a later run never overwrites an earlier one"
- The final reply is the verdict word and the report path | reply ^(PASS|FAIL|BLOCKED|QUESTIONS)\b | Output: "Final reply to the main session: exactly two lines"
- The area map in docs/requirements | write docs/requirements/** | Output: "The map file(s) under `docs/requirements/`"

## Allowed write paths
- docs/requirements/**
- docs/agents/work/**

## Forbidden write paths
- **/tests/**, **/test_*.py, **/*.test.*, **/*.spec.* | Must not: "Change code, tests"

## Forbidden commands (regex on Bash commands)
- git (commit|push)\b | Must not: change code (read-only git)
