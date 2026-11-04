# automation-engineer: judge criteria

Source: `roles-22/agents/automation-engineer.md` (blob 14050b6). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Edit, Write, Bash
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Automated tests for the draft cases | write {tests} | Does: "Automates each draft case"
- A pre-code run: each new test fails for the right reason | reply (?i)fail | Does: "each must fail for the right reason"
- A short report in your reply | reply | Always: "the verdict and the evidence paths"

## Allowed write paths
- {tests}
- **/tests/**
- **/test/**
- {work}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- none stated
