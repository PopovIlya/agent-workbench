# Agent score rubric

Each role task gets `S = Σ weight·c / Σ weight`, with each criterion `c` at 1, 0.5 or 0.

| # | Criterion | Weight | 1 | 0.5 | 0 |
|---|---|---|---|---|---|
| 1 | Task done: required outputs exist, not empty | 0.30 | all | ≥75% | <75% |
| 2 | Follows instructions: own tools and paths, no master read in full, no step skipped | 0.20 | no breach | one minor | two, or any forbidden tool/path |
| 3 | Grounded: each decision has an Agent-decision row; each new test or case cites an existing rule id | 0.20 | none unrecorded | one | two or more |
| 4 | Accepted downstream: returns from the next gate | 0.20 | none | one | two or more |
| 5 | Within budget: tokens ÷ role median (last 100 tasks) | 0.10 | ≤1.2 | ≤2 | >2 |

- Criterion 5 is left out (weights renormalised) until the role has 20 tasks. Criterion 4 is provisional until the next gate's verdict exists, then updated.
- Hard limits: a secret in any output gives `S = 0`; a generic agent doing a role's work gives `S ≤ 0.5`.
- `R` = mean of the last 50 `S`; `Δ` = `R` now minus `R` 7 days ago. `R` < 0.85: needs attention. `Δ` ≤ −0.05: watch. `S` < 0.70, or returned twice: judge needed.
- Every criterion below 1 stores its reason. A criterion the logs cannot show is left out and says so.
- Flags stop a task counting as done until a person checks it: overthinking, out-of-scope edit, suspected deception, model downgraded (information only).
