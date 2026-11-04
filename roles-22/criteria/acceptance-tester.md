# acceptance-tester: judge criteria

Source: `roles-22/agents/acceptance-tester.md` (blob 1c8f16d). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash, Write
Next gate (criterion 4): none
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- Per-role result report: pass, fail, not verified, with the reason | reply (?i)pass|fail|not verified | Does: "Reports per role: pass, fail, not verified, with the reason."
- Results with record ids | write {release}/acceptance.md | Does: "Writes results only, with record ids"
- A short report in your reply | reply | Always: "the verdict and the evidence paths"

## Allowed write paths
- {release}
- {work}

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- \b(migrate|reseed|re-seed|seed_)\w* | Does not: "Run data scripts, re-seeds or migrations"
