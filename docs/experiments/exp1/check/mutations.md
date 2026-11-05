# Mutations (private: never show to either arm)

Each is a small break of the expected behaviour in that arm's own code. Names of functions differ per arm, so find
the place that does the thing described, break it as described, run that arm's own tests, record killed/survived, revert.
Killed = at least one of the arm's own tests fails.

| # | Brief item | Break |
|---|---|---|
| M1 | 2 tokens | cache read tokens are added to the input tokens (and not reported as their own field) |
| M2 | 2 tokens | cache write tokens are dropped (reported as 0) |
| M3 | 2 main sessions | the main session's tokens and cost are left out of the ticket totals |
| M4 | 2 wait | wait gaps under 60 s count as their real length (the threshold is removed) |
| M5 | 2 wait | wait counts the gap after every assistant message, not only after a stop for the person |
| M6 | 2 per model | the per-model split is summed into one model (all tokens and cost under a single model name) |
| M7 | 2 cost | cost uses a wrong price: input and output prices swapped for the cost calculation |
| M8 | 2 share | main-session share is computed against the total cost (main + sub-agents) instead of the sub-agents' cost |
| M9 | 3 diff | the difference column returns b divided by a in place of b minus a (or the reverse for the ratio) |
| M10 | 3 diff | the ratio b/a is computed as a/b |
| M11 | 4 unknown key | the CLI exits 0 (not 2) on an unknown key |
| M12 | 4 unknown key | the page answers 200 with an empty report on an unknown key (instead of a clear error) |
| M13 | 4 no main | a ticket with no main session shows 0 (or an empty cell) instead of "no main session" |
| M14 | 5 JSON | JSON keys are not sorted (sort_keys removed or ordering changed) |
| M15 | 2 roles | failed role runs are counted as ok (failed = 0), or repeat rounds counted as 0 |

Scoring: killed count out of 15 for each arm (only mutations that apply to that arm's design; mark "n/a" with the reason if the arm has no such code path).
