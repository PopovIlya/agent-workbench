# coordinator: judge criteria

Source: `roles-22/agents/coordinator.md` (blob d75f2d7). Written from that file's own text; nothing here is invented. If the role file changes, `agent-score` warns that this list may be stale. Paths in `{...}` are filled from the scored project's `docs/agents/PROJECT.md` (agent_scoring/project.py).
Gate role: no
Tools (copied, for people; the score script reads the live role file): Read, Grep, Glob, Bash, Skill, Agent(business-analyst), Agent(system-analyst), Agent(qa-analyst), Agent(requirements-reviewer), Agent(test-designer), Agent(automation-engineer), Agent(builder), Agent(reviewer), Agent(test-runner), Agent(environment-checker), Agent(verifier), Agent(hostile-verifier), Agent(security-engineer), Agent(lead-qa), Agent(test-manager), Agent(head-of-qa), Agent(independent-auditor), Agent(deployer), Agent(acceptance-tester), Agent(beta-go-checker), Agent(triage)
Next gate (criterion 4): none
Note: Runs as the main session (`claude --agent coordinator`), not as a sub-agent, so the score script does not see it as a task today.
Criterion 3 applies (decisions or new tests/cases): no

## Outputs
<!-- what | check | where the role file says it. check = `write <globs>` (a Write/Edit/shell write to a matching path, not empty) · `reply [regex]` (the final reply, matching) · `contains <text>` (written text contains it) · `none` (cannot be checked from the logs) -->
- A claim for each ticket's modules before the build (gate claims) | none | Does: "claims each ticket's modules before the build"
- A checkpoint note for each step | none | Does: "Record it in the step's checkpoint note"
- A short report in your reply | reply | Always: "the verdict and the evidence paths"

## Allowed write paths
- not stated

## Forbidden write paths
- none stated

## Forbidden commands (regex on Bash commands)
- git push\b.*\b(main|master)\b | Does not: "Push to a protected_branches branch."
