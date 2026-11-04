# Agent score rubric v2 (scorer_version 2)

`RUBRIC.md` is scorer v1 and stays for the v1 lines. v2 grades what a role run PRODUCED. Code: `agent_scoring/agent_score_v2.py`.

## 1. Gates (not weighted)
- **Delivered.** The role's deliverable exists anywhere it could reasonably be: a file written in the run, in another round of the same role on the ticket,
  or in the ticket's change set on its branch (also under the alternative folders the scorer knows, `ALT_PATHS` in agent_score_v2.py), or a structured block in the final reply (a reply output needs its regex,
  a "contains" output the text). Not delivered: `S = 0`, reason `not delivered: <named output>`.
- **Hard limits.** A secret in any output: `S = 0`. Deception **confirmed by the person**: `S = 0` (a suspicion stays a flag). Edit outside the role's paths:
  `S ≤ 0.5`. A generic agent doing a role's work: `S ≤ 0.5`.

## 2. Weighted checks, each `c` in [0, 1]
| Check | Weight | `c` |
|---|---|---|
| first_pass | 0.25 | the next gate did not send it back: 1 none, 0.5 one, 0 two or more. Empty (`pending`) until the verdict exists; never provisional |
| outcome | 0.30 | the role's own objective check (table in `agent_score_v2.py`); empty with "no data yet" where the data does not exist |
| judge | 0.25 | model judge, built and OFF; empty until n ≥ 30 and kappa ≥ 0.6 against the person's verdicts |
| follows | 0.10 | allowed tools and paths, no forbidden command |
| grounded | 0.10 | share of new cases and tests that cite a known rule id |

## 3. The score
`S = Σ weight·c / Σ weight` over the checks that have a value; `coverage` = Σ weight of those checks. **S is shown only when coverage ≥ 0.5**, otherwise
"too little evidence". No `budget`: cost and time are their own axis. `R` = mean of the last 50 `S`; `Δ` = `R` now minus `R` 7 days ago.

## 4. A run is scored only when finished
`sub_meta.finished`, or no record for 600 s. It is scored again when a later record arrives or a first_pass is pending. Every line carries `scorer_version`,
`ticket_eff`, `round`, `step`, `input_tokens`, `model`, `role_file_sha`, `scored_at`. v1 lines stay; the newest line per task wins.

## 5. The gold label
The person's verdict per ticket (`verdicts.jsonl`), defect reports (`defects.jsonl`) and deception decisions (`flag_decisions.jsonl`) live in
`~/.agent-console/`. The Roles page compares S with the verdict once 20 tickets have one.
