# EXP-1: the same ticket on the 22 roles and on the six kit roles

Date: 2026-11-05. One run per arm (n = 1). Money figures are estimates from the repo's `console/pricing.yaml`, not an invoice.

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
| Quality | A fresh session that saw neither run (`check/CHECK-INSTRUCTIONS.md`, 86 atomic steps, result in `check-report.md`): the full suites, a neutral synthetic log set with hand-computed expected values, 15 mutations, and each arm's new tests run against the other arm's code. |

Wait time follows the brief: the gap between an assistant message that ends with a stop for the person and the next message the person typed; gaps under 60 s count as zero. In this experiment an "ops" session answered the agents in the person's place, so those answers count as person messages.

Deviations from the plan are in `deviations.md`. The main ones: both arms ran in parallel (the plan said kit first); two earlier attempts were aborted (the sessions were opened on the wrong folder) and restarted with new ticket keys; the spend caps were raised to USD 80 per arm; extra review loops were allowed beyond the two return rounds (answers 38, 39, 41, 43, 46, 48, 49 and the kit's re-plan).

## 3. What was measured (run 3, the one that counts)

Source: `data/tokens.md`, `data/tokens.json` (raw logs).

| | Kit | 22 roles |
|---|---|---|
| Role runs (sub-agent runs) | 21 | 147 |
| Repeat rounds (runs minus distinct roles) | 15 | 133 |
| Tokens: input / output | 598 / 246,502 | 4,933 / 1,989,697 |
| Tokens: cache write / cache read | 1,003,046 / 13,503,150 | 10,154,470 / 199,887,331 |
| Models | sonnet 100% | opus 99.18 USD, sonnet 18.18 USD, haiku 0.06 USD |
| Cost, USD (estimate) | **7.67** (main 3.05, sub-agents 4.63) | **117.42** (main 51.97, sub-agents 65.45) |
| Main session cost / sub-agent cost | 0.66 | 0.79 |
| Wall time | 185 min | 314 min |
| Active role time (sum of run durations; parallel runs add up) | 46 min | 373 min |
| Wait on a person | 130 min (one pause while the kit waited for a decision) | about 1 min |
| Logged stops that needed an answer (all attempts, `interventions.md`) | 9 | 19 |
| Finished | yes (verifier FAIL only on a kit tool's own fixtures, accepted) | yes (READY FOR THE TRAIN) |
| Commits on the branch | 3 | 1 |
| Diff against base | 6 files, +2,146 | 19 files, +6,826 |
| Console suite | 554 passed | 798 passed |
| New test functions / test lines | 79 / 1,232 | 317 / 5,002 |

Where the 22-role money went (`tokens.md`): requirements and analysis 25 %, test design and automation 12 %, build 3 %, review / verify / security 16 %, the coordinator's own session 44 %. For the kit: analysis 11 %, tests 20 %, build 18 %, review 11 %, the main session 40 %.

All money spent in the experiment (raw logs, estimates): kit 7.67 + 22 roles 117.42 + four aborted attempts 12.09 (`data/tokens-all.md`) + the ops session about 25.5 + the check session about 1.5 = about USD 164. The plan's budget was USD 100.

### A measurement finding: the console undercounts the 22-role arm

The console's Tickets page showed USD 53.30 for the 22-role ticket (4 of 147 sub-agent runs). The console attributes a sub-agent run to a ticket by a leading `[KEY]` in the spawn description or a Jira-style key; the kit's descriptions start with the key, the coordinator's do not. For the kit the console and the raw logs agree to the cent. All spend watching during the run used the console figure, so the 22-role spend ran past its cap unnoticed. The raw-log numbers above are the source of record. The `compare` feature built in this experiment inherits the same attribution rule, as the brief required.

## 4. What the independent check gave

Source: `check-report.md` (86 steps: 85 MATCH, 1 could not complete: the removal of a scratch folder was refused by the harness and was done by hand afterwards).

| | Kit | 22 roles |
|---|---|---|
| Brief requirements met (of 5) | 5 | 5 |
| Figures against hand-computed expected values (synthetic set) | all equal | all equal |
| Mutations killed (of 15) | 15 | 15 |
| Own tests passing on the other arm's code | 74 of 109 (22-role code, kit tests) | 10 of 335 (kit code, 22-role tests) |
| Cross failures that are a real missing behaviour | 0 | 0 |

Every cross-test failure was classed as a design difference (function, module and field names, page markup, text labels), so the cross-test number mostly measures how different the two designs are, not which one is better. One group, how a "failed run" is defined, is flagged for a human: the brief does not say which events make a run failed.

### Accuracy on the real logs (run by the ops session after the check)

Source: `data/real-logs-compare-kit.json`, `data/real-logs-compare-r22.json` (each arm's CLI on the real logs, compared with the raw-log script).

- Tokens, cost, wall time, active time, wait time (130 min), repeat rounds (15) and main share (0.66) for the kit ticket: both CLIs equal the raw-log script.
- **Failed runs for the kit ticket: the kit's CLI reports 21 of 21 runs as failed; the 22-role CLI reports 0.** The kit counts a run as failed when it has no normal final reply, and every real kit run ends with a hand-back call, so every run is flagged. This is the risk the kit's own verifier warned about (L3 step 6), and neither the kit's tests nor the synthetic check set exposed it. The 22-role arm found and fixed this exact case during its review loops.
- For the 22-role ticket both CLIs show the console's attributed figures (4 runs, 53.30 USD), not the raw total, because of the attribution rule above.

## 5. What the numbers show and do not show

- n = 1 per arm, and agents vary between runs. The gap in cost is large (about 15 times) but the spread of one process is unknown (the second kit run in the plan was not made).
- The model tiers differ: the 22 roles ran mostly on opus (85 % of their cost), the kit on sonnet. Process and model effects are mixed; the split by model is in `tokens.md`.
- On the five brief requirements and the 15 mutations both results are equal. The difference is in depth: the 22-role arm wrote about four times the tests, ran a hostile verifier and a security engineer that found real problems (a false "unknown key" while the console rescans, compact-summary records counted as typed by the person, several input-handling issues), and avoided the failed-run defect. The kit result is much cheaper and has one confirmed defect on real data.
- The kit arm stood idle for 130 minutes waiting for a human decision; the 22-role arm was answered at once by the ops session. Wall and wait times are not comparable as process properties.
- The kit arm applied answers 24 to 38 only in a late extra loop; the 22-role arm had them as it went. Both arms could read the same `answers.md`.
- The ops session made many product decisions in the person's place ("narrowest reading", answers 37 onward). The same rulings went to both arms, but the decisions are the ops session's.
- The 22-role arm's code was committed by the ops session after the route finished; the kit committed its own.
- Prices are estimates; the check's synthetic data and the 15 mutations were written by the same person who ran the experiment.

## 6. Layout

| Path | What |
|---|---|
| `brief.md` | the ticket as given to both arms |
| `answers.md`, `interventions.md`, `deviations.md`, `baseline.md` | decisions, stops (with times and spend), deviations from the plan, baseline results |
| `data/` | token, cost and time tables from the raw logs; the `compare` output of both arms on the real logs |
| `tools/count_tokens.py` | the one counting script (set the paths at its top; `--all-keys` for the aborted attempts) |
| `check/` | the check instructions, the synthetic data generator, the expected values, the mutation list |
| `check-report.md` | the check's report |
| `runs/kit/work`, `runs/r22/work` | the agents' own reports for each arm (role reports, review findings, run reports) |

The two implementations are on the branches `exp1/kit` and `exp1/r22`, tagged `exp1-kit-final` and `exp1-r22-final`. Absolute paths in these files were replaced with placeholders (`<workbench>`, `<awb-kit>`, `<awb-r22>`, `<projects>`). No session text from the logs is included, only counts.
