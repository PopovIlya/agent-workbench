# builder: judge criteria

Source: `roles-22/agents/builder.md` (blob 987cf13). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Edit, Write, Bash
Next gate (criterion 4): reviewer, verifier
Criterion 3 applies (decisions or new tests/cases): yes

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- The code and its unit tests | write {code} | Output: "The code, its unit tests, and the impact-map entry"
- The impact-map entry (gate impact_map) | write {impact_map} | Does: "adds the map entry for any added, moved or deleted code path"
- A state note of at most 20 lines | reply | Output: "A state note of at most 20 lines. First line: head sha · step · next action · open bugs."

## Allowed write paths
- not stated (the ticket's modules: checked by the out_of_scope_edit flag)

## Forbidden write paths
- {cases} | Does not: "Edit the test designer's cases"

## Forbidden commands (regex on Bash commands)
- git push\b.*\b(main|master)\b | Does not: "Push to a protected_branches branch."
