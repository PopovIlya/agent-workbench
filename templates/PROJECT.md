# Project profile: <project name>

Path in the repo: `docs/agents/PROJECT.md`. Every role reads it first: the six `kit-*` roles and the 22 roles.
Keep it factual and short. A placeholder in angle brackets is not a value: fill it in or write `none`. A line whose value is `none` is off.
Lines written `` - `key`: value `` are read by name, by the roles and by the agent console; keep the key as it is.

## Repo
- Trunk branch: <main / master>
- Layout: <directories and what lives in each>
- Packages: <list, with the directory of each>
- Commit style: <e.g. `<KEY> <Sentence>`, with two real examples from git log>
- `protected_branches`: <branches no agent ever pushes to, e.g. main>
- `mr_target`: <the default target branch of a change MR, e.g. main>
- `release_branch`: <how a person's release branch is named, e.g. release/<person>-<n>, or none>
- `merger`: <the person who opens and merges MRs; agents never merge>

## People and rulings
Roles, not names.
- `product_owner`: <the role that rules on product questions, e.g. the product manager>
- `approver`: <the role whose recorded yes a deploy or any shared-environment action needs>
- `questions`: <where a blocking question goes: a file (e.g. docs/requirements/QUESTIONS.md) or "the questions_inbox gate">

## Documents
- `test_strategy`: <path of the binding test process, or none>
- `dev_strategy`: <path of the build / merge / ship process, or none>
- `decisions`: <path of the decisions file, or none>
- `conventions`: <files or skills roles read for code rules, with the sections that matter, or none>
- `security_rules`: <path of the binding security rules, or none>

## Requirements map
- `requirements`: docs/requirements/*.md
- Format: one block per rule, `### <ID>` with fields (see `<workbench>/templates/requirements-area.md`). Another format: declare the `requirements_master` gate below.
- `rule_marker`: <how a test names its rule, e.g. a `# rule: <ID>` comment above the test>
- `questions_file`: docs/requirements/QUESTIONS.md

## Work folder
Not committed: add `docs/agents/work/` to `.git/info/exclude`.
- `work_dir`: docs/agents/work/<KEY>/
- `change_file`: docs/agents/work/<KEY>/change.md
- `release_dir`: docs/agents/work/releases/<id>/

## Environment
- Interpreter or virtualenv the commands use: <path, or how to activate it; say which binaries to call>
- Packages that are NOT installed in it (so their suites cannot run locally): <list, or none>
- Commands that must not be run (installs from a new index, deploys): <list>
- `destructive_commands`: <scripts that wipe or rewrite data; each run needs the person's yes for that run, or none>

## Commands
Run from the directory shown. Give the exact command.

| What | Directory | Command |
|---|---|---|
| Lint | | |
| Types | | |
| Tests, package 1 | | |
| Tests, package 2 | | |
| Touched tests only | | |
| Local selection before a push | | |
| Full suite (the person runs it, not an agent) | | |
| Secret scan | | |
| Route access tests (deny by default) | | |

## Local lane
How a role runs the app on its own machine.
- Start: <commands, ports>
- Health: <URLs that answer when it is up>
- Test accounts and seeds: <how to get them; where the dev login is, if any>
- Must not be touched: <shared databases, other people's lanes>

## Shared environments
- `environments`: <dev, staging, ... or none>
- `deploy`: <the documented deploy path, or none>
- `version_check`: <how to read the deployed version back>
- `smoke`: <the smoke suite command>
- `test_record_prefix`: <prefix that marks test records in a shared environment, e.g. QA-, or none>

## CI
- Jobs a branch pipeline runs: <list, with the commands they run>
- Jobs that must not be triggered by agents: <deploy, ops>
- `qa_report`: <where the pipeline's test report is read, or none>
- `skip_marker`: <how an intermediate push skips the pipeline, e.g. `[skip ci]` in the head commit, or none>

## Baseline
- Commit: <sha>
- Results: <lint result; per suite: passed / failed / skipped>

## Scratch services for L2
How the verifier starts a throwaway real service to check what the fixtures cannot (for example a single-node replica set for transactions). Give: the start command (a new container with a unique name, never a shared one), the connection URI, the cleanup command, and what must not be touched. Write `none` if there is no recipe; those checks then stay on the human's L3 list.

## Test fixtures and their limits
- <fixture or mock, what it fakes, what it cannot test, e.g. "an in-memory database: no transactions">

## Running tests against a throwaway copy
How the reviewer's mutation check runs the tests on a copy of the repo under `/tmp` (for example, an editable install points at the original path, so say how to override it): <command or `not possible`>

## Areas
| Area | Prefix | Map file | Main code paths |
|---|---|---|---|

## Limits
- `max_agents`: 20
- `heavy_agents_per_machine`: 3
- `return_rounds`: 2

## Model tiers
A role's tier comes from its role file (`model:`). A row here overrides it for this project: the session that spawns the role passes `model: <tier>` in the Agent call. Leave empty to keep the role files' tiers.

| Role | Tier | Why |
|---|---|---|

## Optional gates
Each gate is off unless its line has a value. A role that reaches a step needing an undeclared gate skips that step and writes one line in its report: `gate <name>: not declared in PROJECT.md, skipped`.
- `claims`: <commands to claim, check and release modules for a ticket, with `<KEY>` and `<modules>`; or none>
- `impact_map`: <glob of the impact map files, and the field names for a module id and its code globs; or none>
- `test_case_files`: <glob of the test-case files, e.g. qa/cases/*.yaml; each case lists its rule ids under `rules:`; or none>
- `rule_guards`: <commands that check rule / case / test consistency; or none>
- `requirements_master`: <glob, when the requirement map is not docs/requirements/*.md; ids as `### ID` headings, `| ID |` table rows or `- **ID**` bullets; or none>
- `change_files`: <glob of change files, when they are not in the work folder; or none>
- `questions_inbox`: <commands to ask and to list questions; or none>
- `ci_limit`: <a command that answers SLOT FREE before a pipeline push, and the wait command; or none>
- `tracker`: <system · the env var that names your release task · the status names an agent may set; or none>
- `suites`: <suite file pattern, e.g. qa/suites/<id>.yaml · the runner command; or none>
- `test_selection`: <a command that picks the tests a diff needs; or none>
- `coverage_report`: <where rule coverage is read (an artifact or a command); or none>
- `timing_check`: <a timing rule per changed page or endpoint, e.g. "usable in under 3 s on the local lane"; or none>

## Project conventions
- <rules the roles must follow that are not obvious from the code>
