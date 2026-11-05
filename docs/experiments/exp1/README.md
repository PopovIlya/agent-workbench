# EXP-1: the same ticket on the 22 roles and on the six kit roles

Date: 2026-11-05. One run per arm (n = 1). Money figures are estimates from the repo's `console/pricing.yaml`, not an invoice. Every figure below can be recomputed from the files in `data/raw/` (section 11).

## Result in one line

On the same ticket the kit used about 14 times fewer tokens and cost about 15 times less (USD 7.67 against 117.42). Both results met all 5 brief requirements and killed 15 of 15 mutations. The 22 roles found more real problems and avoided one defect that the kit shipped (a wrong failed-run count on real logs, fixed afterwards in one commit). About 30 % of the cost gap is the model mix (opus against sonnet), about 70 % is token volume.

## 1. The task

The repo was `agent-workbench` itself. Both arms got the same brief (`brief.md`, byte for byte): a ticket comparison report in the console. A page `/compare?a=<KEY>&b=<KEY>` and a CLI `python -m agent_console compare <KEY> <KEY> [--json]` that show two tickets side by side (role runs, tokens per model, cost, wall time, active time, wait on a person, main-session share) with a difference column, clear errors, and stable JSON.

Goal: measure what the same ticket costs (tokens, dollars, wall time, human time) when run by the 22-role coordinator and by the six-role kit playbook, and how strong each result is.

## 2. How the experiment was run

| Condition | How it was held |
|---|---|
| Same task | One brief, copied unchanged into both work folders. |
| Same start | Both arms branched from the same commit (`0891a04`: the base plus the project profile) in their own worktrees. |
| Same decisions | Questions the brief did not answer were answered from `answers.md` (51 items), given to both arms in the same words. Every stop is logged in `interventions.md`. |
| Models | Each process as designed: the 22 roles on their own tiers (opus, sonnet, haiku), the kit on sonnet. |
| Measurement | One script (`tools/count_tokens.py`) over the raw session logs, both arms, the main session and every sub-agent log. Messages are deduplicated by message id (resumed sessions copy earlier turns). Cost uses the console's own `Pricing` class and `pricing.yaml` of the base commit. |
| Quality | A fresh session that saw neither run (`check/CHECK-INSTRUCTIONS.md`, 86 atomic steps, result in `check-report.md`): the full suites, a neutral synthetic log set with hand-computed expected values, 15 mutations, and each arm's new tests run against the other arm's code. After the check, each arm's CLI was also run on the real logs and compared with the raw-log script. |

Wait time follows the brief: the gap between an assistant message that ends with a stop for the person and the next message the person typed; gaps under 60 s count as zero. In this experiment an "ops" session answered the agents in the person's place, so those answers count as person messages.

Deviations from the plan are in `deviations.md`. The main ones: both arms ran in parallel (the plan said kit first); two earlier attempts were aborted (the sessions were opened on the wrong folder) and restarted with new ticket keys; the spend caps were raised to USD 80 per arm; extra review loops were allowed beyond the two return rounds (answers 38, 39, 41, 43, 46, 48, 49 and the kit's re-plan).

## 3. What was measured (run 3, the one that counts)

Source: `data/tokens.md`, `data/tokens.json`, and the per-message rows in `data/raw/`.

| | Kit | 22 roles | 22 roles / kit |
|---|---|---|---|
| Tokens, all types | 14.75 M | 212.04 M | 14.4 x |
| Cost, USD (estimate) | **7.67** | **117.42** | 15.3 x |
| Cost per 1 M tokens, USD | 0.52 | 0.55 | 1.07 x |
| Role runs (sub-agent runs) | 21 | 147 | 7 x |
| Repeat rounds (runs minus distinct roles) | 15 | 133 | |
| Tokens: input / output | 598 / 246,502 | 4,933 / 1,989,697 | |
| Tokens: cache write / cache read | 1,003,046 / 13,503,150 | 10,154,470 / 199,887,331 | |
| Models (cost) | sonnet 100 % | opus 99.18 (84 %), sonnet 18.18, haiku 0.06 | |
| Main session cost / sub-agent cost | 0.66 | 0.79 | |
| Cost of the coordinator or main session | 3.05 (40 %) | 51.97 (44 %) | |
| Cost of the build roles | 1.40 (18 %) | 3.33 (3 %) | |
| Cost of requirements and analysis roles | 0.88 (11 %) | 29.51 (25 %) | |
| Wall time | 185 min | 314 min | |
| Active role time (sum of run durations; parallel runs add up) | 46 min | 373 min | 8 x |
| Wait on a person | 130 min (one pause while the kit waited for a decision) | about 1 min | |
| Logged stops that needed an answer (all attempts) | 9 | 19 | |
| Finished | yes (verifier FAIL only on a kit tool's own fixtures, accepted) | yes (READY FOR THE TRAIN) | |
| Commits on the branch | 3 | 1 | |
| Diff against base | 6 files, +2,146 | 19 files, +6,826 | |
| Console suite | 554 passed | 798 passed | |
| New tests / test lines | 79 / 1,232 | 317 / 5,002 | 4 x |

Cost split by role is in `data/tokens.md` (per role and per model, both arms).

All money spent in the experiment (raw logs, estimates): kit 7.67 + 22 roles 117.42 + four aborted attempts 12.09 (`data/tokens-all.md`) + the ops session about 25.5 + the check session about 1.5 = about USD 164. The plan's budget was USD 100.

## 4. What this settles

- **The gap is mostly volume, not price per token.** Cost per million tokens is almost the same in both arms (0.52 and 0.55 USD) because cache reads dominate both. The 22-role arm used 14.4 times the tokens. Re-pricing every message of the 22-role arm at sonnet prices gives USD 85.27 instead of 117.42, so the model mix explains USD 32.15 of the USD 109.75 gap (29 %) and token volume the other USD 77.60 (71 %). At equal prices the cost ratio is 11.1 x instead of 15.3 x. Reproduce with `tools/model_effect.py` (section 11).
- **The 22 roles spend on coordination, not on code.** The coordinator's own session took 44 % of their cost and the build roles 3 %; requirements and analysis took 25 %. 133 of the 147 runs were repeat rounds of a role that had already run (rule rewrites, review returns, test-design rounds).
- **Both results are complete on the brief.** 5 of 5 requirements, every figure equal to the hand-computed expected values, 15 of 15 mutations killed in each arm.

## 5. What the independent check gave

Source: `check-report.md` (86 steps: 85 MATCH, 1 could not complete: the removal of a scratch folder was refused by the harness and was done by hand afterwards).

| | Kit | 22 roles |
|---|---|---|
| Brief requirements met (of 5) | 5 | 5 |
| Figures against hand-computed expected values (synthetic set) | all equal | all equal |
| Mutations killed (of 15) | 15 | 15 |
| Own tests passing on the other arm's code | 74 of 109 (22-role code, kit tests) | 10 of 335 (kit code, 22-role tests) |
| Cross failures that are a real missing behaviour | 0 | 0 |

Every cross-test failure was classed as a design difference (function, module and field names, page markup, text labels), so that number measures how different the two designs are, not which one is better.

### Accuracy on the real logs (run by the ops session after the check)

Source: `data/real-logs-compare-kit.json`, `data/real-logs-compare-r22.json` (each arm's CLI on the real logs, compared with the raw-log script).

- Tokens, cost, wall time, active time, wait time (130 min), repeat rounds (15) and main share (0.66) for the kit ticket: both CLIs equal the raw-log script.
- **Failed runs for the kit ticket: the kit's CLI reported 21 of 21 runs as failed; the 22-role CLI reported 0.** The kit counted a run as failed when it had no normal final reply, and every real kit run ends with a hand-back call, so every run was flagged. This is the risk the kit's own verifier warned about (L3 step 6). Neither the kit's tests nor the synthetic check set exposed it; only the real-log step did. The 22-role arm found and fixed this exact case during its review loops.
- For the 22-role ticket both CLIs show the console's attributed figures (4 runs, 53.30 USD), not the raw total, because of the attribution described in section 8 (with `AGENT_CONSOLE_KEY_PREFIXES=EXP1` they show 117.42).

## 6. What it does not settle

- **The check reached its ceiling.** Both arms scored 5 of 5 and 15 of 15, so the check could not tell them apart. The real difference appeared only on real logs. The mutations and the synthetic data were written by the same session that ran the experiment.
- **Cross-tests measure design difference, not quality.**
- **n = 1.** The second kit run in the plan was not made, so the spread of one process is unknown.
- **Wall and wait time are not comparable as process properties.** The kit arm stood idle for 130 minutes waiting for a human decision; the 22-role arm was answered at once.
- **The "person" was an ops session** that made product decisions in the person's place (answer 37 onward, "narrowest reading"). The same rulings went to both arms, but the decisions are the ops session's. Extra review loops beyond the two return rounds were allowed (listed in section 2).
- The kit arm applied answers 24 to 38 only in a late extra loop; the 22-role arm had them as it went. Both arms could read the same `answers.md`.
- The 22-role arm's code was committed by the ops session after the route finished; the kit committed its own.
- Prices are estimates in `pricing.yaml`, not an invoice.

## 7. What the 22 roles' extra USD 110 bought

- The failed-run defect avoided (the kit's code was fixed afterwards in one small commit, `404ab91`).
- Problems found by the hostile verifier, the security engineer and the review rounds: a false "unknown key" while the console rescans the index (HV-1), compact-summary records counted as typed by the person (B4), input-handling issues (SEC-1 to SEC-4, NEW-2, NEW-3), a pairing bug for sub-agent files without metadata (B5).
- About four times the tests (317 against 79 new test functions).

A code review of the kit diff afterwards (section 9) found five more known limits, none fixed.

## 8. Findings outside the comparison

- **The console undercounted the 22-role arm.** The Tickets page showed USD 53.30 (4 of 147 sub-agent runs); the raw logs say USD 117.42. The cause: the coordinator's sub-agent prompts mention rule and case ids such as `CON-011` or `EP-018-01`. These look like Jira-style keys, so the console filed those runs under about 16 pseudo-tickets (`CON-011` USD 10.28, `CON-015` USD 7.07, and so on) instead of under `EXP1-R22C`. The kit's sub-agent descriptions start with `[EXP1-KITC]`, which wins, so for the kit the console and the raw logs agree to the cent. Started with `AGENT_CONSOLE_KEY_PREFIXES=EXP1` the console shows `EXP1-R22C` = USD 117.42 (main 51.97, sub-agents 65.45, 148 runs), equal to the raw-log script; the price is that only keys with the listed prefixes are recognized.
- **Spend watching was blind.** All watching during the run (the USD 60 pause, the USD 80 caps) used the console figure, so the 22-role spend ran past its cap unnoticed. The raw-log numbers in this document are the source of record.
- **A check on real data found what the tests missed.** Running each CLI against the raw-log script was the only step that exposed a defect.
- **The `compare` feature** built here uses the console's attribution, as the brief required, so its numbers for a ticket are right only when the console files the ticket's runs correctly.

## 9. After the run: what went into `main`

The kit implementation was taken into `main` after the check, with one fix and a review:

- **Fix (commit `404ab91`, on top of the run's last commit `76b5322`):** a sub-agent run that ends with a `SubagentHandback` call counts as completed. The run's own rule, test and map text said the opposite. After the fix the kit CLI reports 0 failed runs on the real logs, like the 22-role CLI; the console suite stays green and ruff is clean. The run's final state stays on the tag `exp1-kit-final`.
- **Review of the diff** (the `code-review` skill, medium effort). Not fixed, recorded as known limits of the kit implementation:
  - the CLI refreshes the console's shared index with its own environment settings (the 22-role arm refuses when settings differ);
  - a key whose runs are all re-keyed to another ticket can show as an empty column instead of "unknown";
  - denied spawns are keyed by the raw ticket, runs by the effective one, so a re-keyed spawn can be counted on the wrong ticket;
  - the page re-reads the session logs on each request (no cache);
  - a denial in the middle of a run is forgotten when the run goes on, as the run's rule says ("the final state decides").
- **Session marking (commit `1b7022f`):** the SessionStart hook now tells Claude to ask for a ticket key at the start of a session and to start every sub-agent description with `[KEY]`, so the console files the runs under the right ticket (see the project README, "Tell Claude how to mark a session").
- The 22-role implementation was not taken into `main`; its commit stays reachable by the tag `exp1-r22-final`.

## 10. Proposed next steps

1. Mark sessions with a ticket key (done in the hook, section 9) and re-check the attribution before any further cost measurement; consider making the console attribute a sub-agent run to its parent session's explicit key.
2. Add a real-data accuracy step to the kit verifier, where a feature reads real data: run the feature on real inputs and compare with an independent count.
3. Next experiment: the kit plus one independent hostile-verifier or security run, to see whether it catches the defects the 22 roles found at a fraction of their cost. Run the kit twice to measure its spread.
4. Write the mutations and the expected values in a session separate from the one that runs the arms.

## 11. Raw data and how to verify

`data/raw/` holds no message text, only counts and timestamps:

| File | Content |
|---|---|
| `messages-kit.csv`, `messages-r22.csv` | One row per API message (deduplicated by message id): role, model, the five token counts, cost in USD. |
| `runs-kit.csv`, `runs-r22.csv` | One row per session file: kind (main or sub), role, first and last timestamp, duration. |
| `waits-kit.csv`, `waits-r22.csv` | Every stop for the person and the next person message: both times, the gap, and whether it counts (gap of 60 s or more). |
| `pricing.yaml` | The price table used (the base commit's). |

To check the headline figures from these files (from the repo root, with the console's virtualenv):

```bash
console/.venv/bin/python docs/experiments/exp1/tools/model_effect.py docs/experiments/exp1/data/raw
```

It prints the actual and the sonnet-priced cost of each arm, the token totals, the split of the gap between model mix and volume, and the cost per million tokens. Summing `cost_usd` per file gives 7.67 and 117.42; summing the token columns gives 14.75 M and 212.04 M; the number of rows in `runs-*.csv` minus the main file gives 21 and 147 runs; the sum of the `gap_s` rows marked "yes" in `waits-kit.csv` gives the 130 minutes of waiting. `tools/export_raw.py` regenerates the CSV files from the session logs (it needs the logs and the paths at the top of `tools/count_tokens.py`).

## 12. Layout

| Path | What |
|---|---|
| `brief.md` | the ticket as given to both arms |
| `answers.md`, `interventions.md`, `deviations.md`, `baseline.md` | decisions, stops (with times and spend), deviations from the plan, baseline results |
| `data/` | token, cost and time tables from the raw logs; the `compare` output of both arms on the real logs; `raw/` the per-message, per-run and per-wait rows |
| `tools/` | `count_tokens.py` (the counting script), `export_raw.py` (writes `data/raw`), `model_effect.py` (the model-mix split) |
| `check/` | the check instructions, the synthetic data generator, the expected values, the mutation list |
| `check-report.md` | the check's report |
| `runs/kit/work`, `runs/r22/work` | the agents' own reports for each arm (role reports, review findings, run reports) |

The two implementations are the commits tagged `exp1-kit-final` and `exp1-r22-final`. Absolute paths in these files were replaced with placeholders (`<workbench>`, `<awb-kit>`, `<awb-r22>`, `<projects>`). No session text from the logs is included, only counts.
