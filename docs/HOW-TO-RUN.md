# How to run

Three ways of working. All three need a repo set up by [SETUP-A-PROJECT.md](SETUP-A-PROJECT.md) (a filled `docs/agents/PROJECT.md`)
and the roles installed by `install.sh`. Start every session **from the repo root**: Claude Code finds the roles there and files the log
under that folder. Start the first message with `[<KEY>]`: the console files the session under that ticket.

| Way | Use it when | Roles |
|---|---|---|
| 1. Kit | most tickets: one person, one repo, a light route | the six `kit-*` roles (`install.sh`, the default) |
| 2. The 22 roles | a full test process: Definition of Ready, trains, a release GO | the 22 roles (`install.sh --only 22` or `--only all`) |
| 3. Maker + critic | long batches of similar items, each checked by a second session, through files | any maker role and any critic role |

## 1. Kit: the main session follows the playbook

**Preconditions:** the kit roles linked (`ls ~/.claude/agents/kit-*.md`); the profile filled; `docs/agents/work/` in `.git/info/exclude`.

**First message.** VS Code: open the repo, open the Claude Code panel, start a new session, send:

```
[PROJ-123] Follow <workbench>/kit/PLAYBOOK.md for PROJ-123: <one line of what the ticket asks>. Area: <area>.
```

CLI: run `claude` from the repo root and send the same text.

Not run here as a full route (an interactive session with stops for you); the start of it, with kit-analyst, is the dry run in SETUP-A-PROJECT.md, which was run.

**Route and stops** (`kit/PLAYBOOK.md` is the source):
- S: analyst (delta) · **stop for you** · builder `tests` · builder `code` · reviewer · [security] · verifier.
- M / L: analyst (as-is, only when the area has no map yet) · analyst (delta) · **stop for you** · test designer · builder `code` · reviewer · [security] · verifier.
- Also stops: any `QUESTIONS` or `BLOCKED`, a second failed return round, before any push, a role that asks for another model or a dependency.

**Outputs:** `docs/agents/work/PROJ-123/` (brief, status, one report per role, `run-report.md`; not committed); the rules in `docs/requirements/`; tests and code in the working tree. The main session commits after the verifier's PASS and waits for your "push".

**In the console:** Tickets › `PROJ-123`. Each role run is a row with its tier, tokens, cost and score; the verdict is read from the role's first reply line.

## 2. The 22 roles: the coordinator

**Preconditions:** the 22 roles linked (`ls ~/.claude/agents/coordinator.md`); the profile filled, including People, Branches, Limits and every Optional gate you use (or `none`); your scope: the `tracker` gate's release task, or a list of keys.

**First message.** VS Code: put this in the repo's `.claude/settings.local.json` (check it is ignored: `git check-ignore .claude/settings.local.json`):

```json
{
  "agent": "coordinator",
  "model": "opus"
}
```

The explicit `"model"` keeps the coordinator on its tier even when your user settings say `"model": "sonnet"`. UNVERIFIED: which of the role file's `model:` and the settings' `model` wins when only `agent` is set; setting both to the same tier avoids the question.

Then start a new session and send:

```
[PROJ-123] Run PROJ-123 through the route. Scope: PROJ-123, PROJ-124.
```

CLI, from the repo root:

```bash
claude --agent coordinator
```

and send the same text.

Not run here: the 22-role route is long, interactive and costly; the coordinator's file, its links and its lint were checked, not a run.

**Route and stops** (`roles-22/agents/coordinator.md`, "The route"): scope check · branch (a worktree per ticket) · Definition of Ready (business analyst, system analyst, QA analyst, each checked) · claim (gate) · cases and failing tests first · build · reviewer · feature test (0 open bugs) · verifiers · hand to the train. It stops at every failed gate, at every blocking question, at a role that fails to start (it never substitutes one), before a pipeline push without a free CI slot, and at every shared-environment step until the `approver`'s yes is recorded.

**Outputs:** the requirement map; the change file per ticket (`change_file`); the work folder (reports, checkpoints, triage files); `release_dir` for the GO report, audit and GO verdict; branches and green MRs for you to open and merge.

**In the console:** Tickets › the key shows every role run of the ticket in order, with rounds (a second builder run is "round 2"), first-pass rate and scores. The coordinator itself is the main session (Sessions), not a scored run.

## 3. Two sessions, maker + critic, through files

**When:** a batch of similar items (re-tests, a list of small fixes) where every item needs an independent check, and you want each session short and fresh.

**Preconditions:**
- One branch for the maker (it is the branch you push) and one for the critic, each in its own worktree.
- A committed handoff folder per item, for example `docs/agents/handoff/<ITEM>/` with `brief.md` and `status.yaml` (`state: todo | review | rework | passed`). It travels on the two branches; drop it before the MR if the repo should not carry it.
- Each worktree's `.claude/settings.local.json` names its role. Check it is ignored: `git check-ignore .claude/settings.local.json`; if not, add it to `.git/info/exclude`.

Set up once (VS Code's terminal or Terminal.app):

```bash
cd ~/code/shop
git worktree add -b work/batch1 ../shop-maker main
git worktree add -b work/batch1-critic ../shop-critic work/batch1
mkdir -p ../shop-maker/.claude ../shop-critic/.claude
printf '{\n  "agent": "kit-builder",\n  "model": "sonnet"\n}\n' > ../shop-maker/.claude/settings.local.json
printf '{\n  "agent": "kit-verifier",\n  "model": "sonnet"\n}\n' > ../shop-critic/.claude/settings.local.json
```

Open **two VS Code windows**, one per worktree. Every item starts in **fresh** sessions (a new chat for each maker and each critic run).

**The handoff (tested on throwaway branches).** The maker works on `work/batch1`. The critic works on a **detached HEAD** that sits on the maker's tip, and moves its own branch `work/batch1-critic` only by fast-forward. Nothing is ever merged into the critic's branch.

| Step | Where | Command |
|---|---|---|
| Maker starts **every** item (not only a rework) | maker worktree | `git merge --ff-only work/batch1-critic` (brings the critic's commit for the previous item; "Already up to date" on item one). If it fails: stop, never merge, rebase or force |
| Maker hands over | maker worktree | commits the work, `maker-report.md` and `status.yaml` (`state: review`) on `work/batch1` |
| Critic starts | critic worktree | `git switch --detach work/batch1` (the tree must be clean), then the guard `git merge-base --is-ancestor work/batch1-critic HEAD`. If the guard fails, the maker skipped its `--ff-only` step: stop |
| Critic finishes | critic worktree | `git status --porcelain` must list **only** `<ITEM>/critic-report.md` and `<ITEM>/status.yaml`; anything else (an unrestored mutation) means stop: `git restore <file>`, run the tests again, check again. Then `git add` the two files, `git commit -m "[<ITEM>] critic report"`, then `git merge-base --is-ancestor work/batch1-critic HEAD && git branch -f work/batch1-critic HEAD` |
| Rework round | maker worktree | `git merge --ff-only work/batch1-critic` (brings `critic-report.md` and the new `status.yaml`), then a fresh maker session |
| Push | maker worktree | `git merge --ff-only work/batch1-critic`, then push `work/batch1` |

**First messages.** Maker window, new session:

```
[ITEM-1] Maker. Run git merge --ff-only work/batch1-critic first. Then do docs/agents/handoff/ITEM-1/brief.md, write maker-report.md, set status.yaml to review and commit.
```

Critic window, new session, after the maker has finished:

```
[ITEM-1] Critic. Run git switch --detach work/batch1 and the is-ancestor guard first. Check docs/agents/handoff/ITEM-1/ against its brief, write critic-report.md and status.yaml, and finish with the porcelain check, the commit and the branch move.
```

CLI: `claude` in each worktree folder, the same messages. The `agent` setting picks the role.

The set-up block and every git step of the handoff table were run in the clean-machine check, by hand, for one item and the start of a second round. Not run here: the two first messages with live sessions.

**Outputs:** the item's handoff folder (brief, `maker-report.md`, `critic-report.md`, `status.yaml`) on both branches; the work on `work/batch1`.

**In the console:** each maker and critic session is a main session (Sessions) labelled with its `agent` setting and filed under the item's `[KEY]`; cost and time per item and per side. These sessions are not sub-agent runs, so they carry no score.

## Troubleshooting

**"Agent type not found".** The session started outside the repo, or the role is not installed. Start it from the repo root (VS Code: the window's folder is the repo); check `ls -l ~/.claude/agents/` shows the role linked into the workbench; run `./install.sh --only all` if the 22 roles are missing. A project's own `.claude/agents/<name>.md` wins over the user-level one with the same name.

**"Needs a permission" to read the playbook or a template.** The workbench is outside the repo. `install.sh` adds it to `permissions.additionalDirectories` in `~/.claude/settings.json`; with `--no-hooks` it does not, so add `--add-dir <workbench>` to the `claude` command.

**`BLOCKED: workbench not found`.** The role could not find the workbench: `AGENT_WORKBENCH` is missing from `~/.claude/settings.json` (run `./install.sh`, then start a new session) and the profile has no `workbench_path`. A role without Bash needs `WORKBENCH=<path>` in its spawn prompt; the playbook and the coordinator pass it.

**A missing profile.** A kit role reports `BLOCKED: PROJECT.md missing`; a 22 role stops with "no profile". The file must be exactly `docs/agents/PROJECT.md` in the repo the session runs in (a worktree has its own copy only if it is committed).

**A session filed under the wrong ticket key.** The console takes the first key it finds, strongest source first: a leading `[KEY]` in the first message or the spawn description, a change file or work folder path, a git command, the folder name, the branch. Start every first message and every spawn description with `[KEY]`. If your keys have their own prefixes, set `AGENT_CONSOLE_KEY_PREFIXES` (INSTALL.md, the console service). A main session takes the key carried by 80 % of its sub-agent runs.

**"Too little evidence" scores.** A score needs data the logs can show: the role's output files written in the run, a verdict from the next gate, earlier runs of the same role for the budget check. Fewer than five scored runs is "too few to judge". Outputs behind an undeclared gate (for example `test_case_files`) are not checkable in that project and are left out, so a run can be scored on fewer checks. Runs whose folder was deleted are scored against `AGENT_CONSOLE_DEFAULT_PROJECT` when it is set, else without project checks.
