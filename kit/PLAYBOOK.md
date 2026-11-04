# Playbook for the main session

The main session is the only coordinator. It is not a role and has no LLM role file. It follows this playbook, passes **file paths** (never file contents) to the roles, and reads back only each report's verdict line and summary.

## 0. Before the first spawn
1. The repo has `docs/agents/PROJECT.md`. If not, STOP and ask the human.
1a. Find the workbench: run this line once from the repo root. It prints `WORKBENCH=<path>` (from the profile's optional `workbench_path`, else `$AGENT_WORKBENCH`, which `install.sh` sets), a note if the profile still has the obsolete `kit_path`, or a `BLOCKED:` line: then STOP and show it. `<workbench>` below is that path.

```bash
bash -c 'p=docs/agents/PROJECT.md; [ -f "$p" ] || { echo "BLOCKED: PROJECT.md missing"; exit 1; }; grep -q "^- .kit_path.:" "$p" && echo "kit_path is obsolete, using AGENT_WORKBENCH"; w=$(sed -n "s/^- .workbench_path.: *//p" "$p" | head -n 1); case "$w" in ""|none|"<"*) w="${AGENT_WORKBENCH:-}" ;; esac; w="${w/#\~/$HOME}"; if [ -n "$w" ] && [ -f "$w/kit/PLAYBOOK.md" ]; then echo "WORKBENCH=$w"; else echo "BLOCKED: workbench not found: AGENT_WORKBENCH is not set (run install.sh in the workbench) and PROJECT.md has no workbench_path"; exit 1; fi'
```

2. Create `docs/agents/work/<KEY>/` with `brief.md` (from `<workbench>/templates/work/brief.md`) and `status.md` (from `<workbench>/templates/work/status.md`).
3. `docs/agents/work/` is not committed: add it to `.git/info/exclude` (not `.gitignore`). The map (`docs/requirements/`), tests and code are committed.

## 1. Routes
Sizes come from the analyst: S / M / L.

- **S:** analyst(delta) → **STOP for the human** → builder step `tests` (tests only; the red run is recorded) → builder step `code` (product code only) → reviewer → [security] → verifier.
- **M / L:** analyst(as-is, only if the area has no map yet) → analyst(delta) → **STOP for the human** → test-designer → builder step `code` → reviewer → [security] → verifier.

`[security]` runs only when the delta analyst report lists at least one security trigger for the block being built. The triggers are the list with definitions in `agents/kit-analyst.md`; a trigger needs a one-line reason, and a pure refactor has `none`. The human may skip `[security]` after reading the reasons; the skip and the reason go in `status.md`.

A role that is not needed for the block is skipped, and the skip and its reason go in `status.md`.

## 2. Spawning
- Every Agent spawn `description` starts with `[<KEY>]`, then the role and the step: `[PROJ-123] kit-analyst delta audit-log`, `[PROJ-123] kit-builder 6.3 tests`, `[PROJ-123] kit-builder 6.3 code`, `[PROJ-123] kit-reviewer 6.3 round 2`.
- The spawn prompt gives: the ticket key, the role's mode (if any), the step, `WORKBENCH=<path>`, and the **paths** of the brief, the reports to read, the area map and the rule IDs in scope. Nothing else. No pasted content.
- Never use a general-purpose agent or a fork in place of a role. Never do a role's work in the main session.
- Models are fixed in the role files. A row in the profile's "Model tiers" table (written by the human) is passed as `model:` in the Agent call. Any other change needs the human's confirmation.

## 3. Verdicts and return rounds
Each report starts with a verdict line: `PASS`, `FAIL`, `BLOCKED` or `QUESTIONS`.

A role's final reply to the main session is exactly two lines: the verdict word alone, then the report path. Read the verdict from the reply's first line (the console reads it from there too); the summary and details are in the report file, and the report's own first line carries the same verdict.

- `PASS`: go to the next step.
- Reviewer and security review the same working-tree diff and may run in parallel. A return round starts only after every review role that is due has reported.
- `FAIL` from reviewer or security: send the report path(s) back to the builder, with the step the findings need (`tests` for findings about tests, `code` for findings about product code, both when both apply, tests first). If both failed in the same round, the builder gets both reports in one return, and that counts as **one** round. **At most 2 return rounds** in total (one shared counter for reviewer and security). After the second round ends in another `FAIL`, STOP and report.
- `FAIL` from the test-designer or verifier: STOP and report.
- `QUESTIONS`: STOP, show the questions, wait for the human.
- `BLOCKED`: STOP and report the cause. A role that fails to start is also a STOP.
- Never retry a failed role with a rewritten prompt to get a different verdict.
- **Change requests from the human after a PASS or after the verifier** (for example a review decision): the main session writes the request as `docs/agents/work/<KEY>/change-<id>.md` (what to change, why, which rules), passes its path to the builder with the step it needs, and then re-runs reviewer, [security] and verifier on the new diff. It counts as a return round against the same budget of 2. Spawn descriptions say so: `[<KEY>] kit-builder 6.3 code change-f3`.
- **A PASS is void after any later change to code or tests.** Any change to code or tests after a PASS voids every earlier PASS (mark it `PASS (void)` in `status.md`). After a builder return, re-run both the reviewer and security (if it ran before), whoever failed, on the new diff; the verifier always runs last. In a repeat round, give the reviewer the path of its previous report. A report that is void cannot be used to close the block.

## 4. Human stops
1. After the analyst (map and size reviewed).
2. Before any push. The session never pushes by itself.
3. Whenever a rule's status must change from `observed` to `confirmed`, or to `retired`: only the human changes it.
4. Whenever a role asks to change its model or add a dependency.

## 5. State
After every step, update `status.md`: step, role, verdict, start time, end time, one line of summary. Read each report's verdict line and summary section only; open the rest when a decision needs it.

**Permission check after every step.** Before each spawn, record `git status --porcelain`. After the role returns, compare `git status` / `git diff` with that record against the role's "May change" list in its role file. The builder's list depends on its step: step `tests` may change test files only, step `code` product code only. Any changed file outside that list is a **permission breach**: STOP, and record it (role, file, the role-file line it broke) for the run report. Files under `docs/agents/work/` are excluded from git and are not covered by this check; a role may write only its own report there.

## 6. Closing a block
1. Run `python3 <workbench>/kit/tools/rule_coverage.py <repo> --write-tests --strict --scope <current block>` (the block named in the brief). `--write-tests` fills each rule's `tests:` field in the map from the `# rule: <ID>` markers; nobody edits that field by hand, neither a role nor the main session. A non-zero exit is a STOP. The verifier runs the same command without `--write-tests`.
2. The main session commits (no role commits): the map (with the `tests:` fields just written), then tests and code, as separate small commits in the repo's commit style (`PROJECT.md`). Until then all role output stays in the working tree, and the base commit does not move.
3. Write `docs/agents/work/<KEY>/run-report.md` (not committed), from `<workbench>/templates/work/run-report.md`: timeline (role, step, start, duration, model, tokens, verdict), every stop, return round and question with its cause, permission breaches (any role that edited files or ran commands outside what its role file allows), unclear places in role files or this playbook with `path:line` and a proposed fix as text, and the console's scores and flags for the key.
4. Do not edit the kit during a run. Problems with a role file or this playbook go in the run report as text.
5. STOP and wait for the human's check and "push".

## 7. Markers
`⚠️ Deviation from plan:` for any departure from the plan. `CONFLICT: <A> vs <B>` for contradictions. `UNVERIFIED:` for claims without evidence.

## 8. Known gaps
- **No watchdog for a hung role.** The main session cannot interrupt a running role. The console marks a role silent for 20 minutes as `stalled`; the human watches for it and stops the run.
- Role permissions are enforced by text and by the §5 check after each step, not by the tools (a role with `Write` and `Bash` can technically edit anything).
