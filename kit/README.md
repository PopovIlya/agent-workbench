# Agent kit

Six universal role agents plus a playbook. A role file holds only the way of working. Everything project-specific comes from the repo's `docs/agents/PROJECT.md`.

| Role | When |
|---|---|
| `kit-analyst` | First: describes current behaviour (`as-is`) or adds the ticket's rules (`delta`); sizes S/M/L; lists security triggers |
| `kit-test-designer` | M/L tickets: failing tests per `confirmed`/`new` rule, proven to fail first |
| `kit-builder` | Smallest change that turns the tests green (writes the tests on S tickets) |
| `kit-reviewer` | Independent diff review and a mutation check on a throwaway copy |
| `kit-security` | Only when the analyst lists a security trigger |
| `kit-verifier` | Last: full gates, rule coverage, MR text, L3 checklist |

No LLM coordinator: the main session follows `PLAYBOOK.md` and passes file paths, not content.

## Layout
- `agents/kit-*.md` — role files. `install.sh` links `~/.claude/agents/kit-*.md` to them.
- `PLAYBOOK.md` — routes, spawn rules, return rounds, human stops.
- `criteria/kit-*.md` — what the agent console checks for each role.
- The formats live at the workbench root: `templates/PROJECT.md`, `templates/requirements-area.md`, `templates/work/*`.
- `tools/rule_coverage.py` — rules in `docs/requirements/*.md` vs `# rule: <ID>` comments in tests. Exit 1 when a `confirmed`/`new` rule has no test (`--scope` limits to one work block; `--strict` also fails on unknown/retired IDs, bad statuses, duplicate IDs, `confirmed`/`new` rules without `scope`, and `tests:` paths with no marker; `--write-tests` fills each rule's `tests:` field from the `# rule:` markers, so nobody edits it by hand).
- `tests/` — tests for the tool: `pytest tests`.

## Use in a repo
1. Copy `<workbench>/templates/PROJECT.md` to `docs/agents/PROJECT.md` and fill it in. The roles find the workbench through `AGENT_WORKBENCH` (set by `install.sh`); a `workbench_path` line in the profile overrides it.
2. Add `docs/agents/work/` to `.git/info/exclude`.
3. Follow `PLAYBOOK.md`.

## Rules
- Role names start with `kit-` (the 22 roles have their own `builder`, `reviewer`, `verifier`; a project-level agent with the same name would shadow a user-level one).
- Models: `sonnet`. Changing one needs the owner's confirmation.
- The kit is not edited during a ticket run; problems go into the run report as text.
- Report file names: `analyst-as-is.md`, `analyst-delta.md`, `builder-tests.md`, `builder-code.md`, and `<role>.md` for the others. A console that scores runs by report name needs these names in its criteria.
