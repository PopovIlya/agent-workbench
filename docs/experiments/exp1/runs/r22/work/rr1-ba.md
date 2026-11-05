# Requirements review 1 (BA part), EXP1-R22C — verdict REJECT (written by coordinator from the reviewer's reply)
Coverage brief 1-5, decisions, out of scope, answers 1-37: complete. Q-015 Agent decision accepted.
BLOCKING
1. CON-022 v3: wait gaps can overlap (several stops before one typed message counted several times; last stop with no typed message after it not covered). Proposed: one gap per typed message from the latest stop before it; never count an interval twice; a stop with no typed message after it adds nothing.
2. CON-015 v5: statement "ended in a permission denial" vs marker "last tool_result was a denial" disagree; a run that hits a denial then sends a final reply. Proposed (answer 3): a denial makes a run failed only when no final reply follows it (same last-turn rule as API errors).
NON-BLOCKING
3. CON-024/025: precedence when both "no main session" and "no sub-agents" apply; share display format. Default: "no main session" wins; share like the ratio, 2 decimals page/CLI, raw JSON.
4. CON-026: model on one side only. Default: absent model is 0; difference shows; ratio n/a when a is 0.
5. CON-014 v5, CON-021 v2: say "a spawn with no run file", not "a denied spawn"; state which parent key (default: effective key, CON-002).
6. CON-029 v6: negative dollar format (default `-$1.23`, no thousands separator); ratio tie rule (away from zero, answer 32).
