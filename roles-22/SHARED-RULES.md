# Shared rules for the 22 roles

Every role reads this once at start: `<workbench>/roles-22/SHARED-RULES.md`. `<workbench>` is the path the resolver line in each role file prints: the profile's optional `workbench_path`, else `$AGENT_WORKBENCH` (set by `install.sh` in the user settings of Claude Code).
Roles run with `omitClaudeMd: true`, so the project's own CLAUDE.md is not loaded; these rules are the safety floor that still applies.
Project facts (paths, ports, commands, people) are never here: they are in the profile.

## Environment check at the start of a session
Before a role runs anything against the app, it confirms the local lane is alive with a real request (an HTTP GET to the profile's health
URLs, not only a port check: a suspended process can hold a port and never answer). It reports the state in one line. If something is
down, it says so and stops; it never works around a dead dependency.

## Process safety: never stop what you did not start
- A process you started yourself for your task (a throwaway server on a scratch port): stop it when you are done.
- Any other process, even one that looks dead or idle: report it (pid, port, state, how long) and wait for the person. Never kill it.
- After one unintended disconnect, stop and report. No second corrective action on your own.

## Destructive commands: the person's yes for each run
The profile's `destructive_commands` (and any command that drops, wipes, truncates or restores data) runs only after the person's explicit
yes for that run. A yes for an earlier run does not carry over. Report what the command is about to do, then wait.

## Dependencies: official packages only
A new dependency comes from the official registry (PyPI, npm) or the organisation's own index, under its real name, and only after the
person agrees. Never a name you assume exists.

## Secrets
Never copy a value from `.env`, a secret store, a keychain or a process environment into a file, a comment, a commit message or a report.
Refer to a secret by its name only, even as evidence, even when it is a local placeholder. A secret scanner will flag a quoted value in
an already-pushed commit, and that needs a history rewrite to clear.

## Pushing
- Agents commit and push only to their own ticket branch and their release branch. Never to a `protected_branches` branch.
- Every push to an MR branch may start a pipeline. Commit freely; push in batches. If the profile names a `skip_marker`, an intermediate
  push carries it; the last push before merge never does.
- With the `ci_limit` gate declared, a pipeline push waits for SLOT FREE. Without it, ask the person whether the previous pipeline has
  finished and wait for the answer.
- The `merger` (a person) opens and merges MRs. Agents never open, edit or merge one.

## A role that fails to start
Model access, agent type not found, a tool denial, an API error: stop that step and report the error word for word. Never do the role's
work yourself; never substitute a general-purpose agent, a fork, another role or another model. A model switch needs a person's yes
(see `<workbench>/docs/INSTALL.md`, Models).
