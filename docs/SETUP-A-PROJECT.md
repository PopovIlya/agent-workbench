# Make a repo ready

Every role reads one file first: `docs/agents/PROJECT.md` in the repo it runs in. This page fills it for an example repo, `shop`
(a small Python web app), field by field. Paths below assume the workbench is at `~/code/agent-workbench` and the repo at `~/code/shop`.

## 1. Copy the profile

VS Code: open the repo (File › Open Folder), then a terminal (Terminal › New Terminal). CLI: Terminal.app.

```bash
cd ~/code/shop
mkdir -p docs/agents docs/requirements
cp ~/code/agent-workbench/templates/PROJECT.md docs/agents/PROJECT.md
cp ~/code/agent-workbench/templates/requirements-area.md docs/requirements/cart.md
```

## 2. Fill it in, field by field

Open `docs/agents/PROJECT.md`. Replace every `<...>` with a fact, or with `none`. Keep the `` `key` `` names as they are: the roles and the console read them by name.

The profile does not say where the workbench is. Every role finds it from `AGENT_WORKBENCH`, which `install.sh` sets in `~/.claude/settings.json`. Only if one repo must use another workbench checkout, add this line to its profile (an override):

```
- `workbench_path`: ~/code/other-agent-workbench
```

A profile from before this change may still have a `` - `kit_path`: `` line. The roles ignore it and write one line in their report, `kit_path is obsolete, using AGENT_WORKBENCH`; you can delete the line when the repo allows it.

| Section | Field | Example for `shop` | Why it matters |
|---|---|---|---|
| Repo | Trunk branch | `main` | the reviewer diffs against it; the console reads it |
| Repo | Layout / Packages | `app/` (code), `tests/` (pytest) | the builder and reviewer know where things live |
| Repo | Commit style | `PROJ-12 Add the empty-cart state` | the main session commits in it |
| Repo | `protected_branches` | `main` | no agent pushes there |
| Repo | `mr_target` | `main` | the default MR target |
| Repo | `release_branch` | `none` | the coordinator's trains (22 roles) |
| Repo | `merger` | `the repo owner` | agents never merge |
| People | `product_owner` | `the repo owner` | who rules on product questions |
| People | `approver` | `the repo owner` | whose yes a deploy or a shared-environment step needs |
| People | `questions` | `docs/requirements/QUESTIONS.md` | where a blocking question goes |
| Documents | `test_strategy`, `dev_strategy`, `decisions`, `conventions`, `security_rules` | `none` (fill in when you have them) | a declared strategy is binding over the role files |
| Requirements map | `requirements` | `docs/requirements/*.md` | the rules; one file per area, `### ID` blocks |
| Requirements map | `rule_marker` | a `# rule: CART-001` comment above each test | `rule_coverage.py` and the reviewer read it |
| Work folder | `work_dir`, `change_file`, `release_dir` | keep the defaults | the roles' reports; not committed |
| Environment | interpreter | `.venv/bin/python` | the commands the roles run |
| Environment | `destructive_commands` | `none` | each run of one needs your yes |
| Commands | Lint / Tests / Touched tests / Local selection | `.venv/bin/ruff check .` · `.venv/bin/pytest -q` · `.venv/bin/pytest -q <files>` · `.venv/bin/pytest -q` | exact commands, from the folder shown |
| Local lane | Start / Health | `.venv/bin/uvicorn app.main:app --port 8000` · `http://127.0.0.1:8000/health` | the verifier and environment checker use them |
| Shared environments | `environments` | `none` | the deployer, GO checker and acceptance tester then skip |
| CI | jobs, `qa_report`, `skip_marker` | `lint, test` · `none` · `none` | push rules |
| Baseline | Commit / Results | the sha and the test counts of today | the verifier compares against it |
| Areas | table | `Cart · CART · docs/requirements/cart.md · app/cart/` | the analyst's area map |
| Limits | `max_agents`, `heavy_agents_per_machine`, `return_rounds` | keep the defaults | the coordinator's caps |
| Model tiers | table | empty | a row overrides one role's tier for this repo |
| Optional gates | every line | `none` | each declared gate turns on a step (claims, impact map, test-case files, rule guards, ...); an undeclared one is skipped with one line in the report |

## 3. Keep the work folder out of git

The roles' reports go in `docs/agents/work/`. They are not committed, and not in `.gitignore` either (that file is shared): use the repo's own exclude file.

```bash
printf '%s\n' 'docs/agents/work/' >> .git/info/exclude
git status --porcelain
```

## 4. Point CLAUDE.md at the profile

So a plain session also knows where the facts are:

```bash
printf '\n%s\n' 'Agents: read docs/agents/PROJECT.md first. Roles and the playbook live in the agent workbench at $AGENT_WORKBENCH.' >> CLAUDE.md
```

## 5. Check it with a dry run of kit-analyst

The analyst only reads code and writes its report and the requirement map; it never changes code. This shows that the roles are installed, the profile is found and the console sees the run.

VS Code: open the Claude Code panel in the `shop` window, start a new session, and send:

```
[PROJ-1] Follow <workbench>/kit/PLAYBOOK.md section 0 for PROJ-1, then spawn kit-analyst in mode as-is for the area cart. Stop after the analyst's report and show me its verdict line.
```

CLI, the same as one command:

```bash
cd ~/code/shop
claude -p "[PROJ-1] Follow ~/code/agent-workbench/kit/PLAYBOOK.md section 0 for PROJ-1, then spawn kit-analyst in mode as-is for the area cart. Stop after the analyst's report and show me its verdict line." --permission-mode acceptEdits < /dev/null
```

Expect:
- `docs/agents/work/PROJ-1/brief.md`, `status.md` and `analyst-as-is.md`; the report's first line is `PASS`, `BLOCKED` or `QUESTIONS`.
- The console (http://127.0.0.1:8790, Tickets) lists `PROJ-1` with a `kit-analyst` run.
- `BLOCKED: PROJECT.md missing` means the profile is not at `docs/agents/PROJECT.md`.
- `BLOCKED: workbench not found`: `AGENT_WORKBENCH` is not set (run `./install.sh` in the workbench without `--no-hooks`, then start a new session) and the profile has no `workbench_path`.
- "needs a permission" for a file under the workbench: the workbench is not in `permissions.additionalDirectories` (run `./install.sh` again without `--no-hooks`, or add `--add-dir ~/code/agent-workbench` to the `claude` command).
