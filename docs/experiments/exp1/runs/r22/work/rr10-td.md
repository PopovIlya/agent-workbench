# Requirements review 10 (test design rule edits), EXP1-R22C — PASS (written by coordinator from the reviewer's reply)
CON-014 v7, CON-018 v2, CON-022 v11, CON-012 note: PASS. Q-034, Q-037, Q-038 small and narrowest; Q-037 fits answers 24 and 30.
Non-blocking:
1. Q-037 "other meta text" among ~100 isMeta records not checked: the reviewer's read-only scan of ~/.claude/projects was REFUSED: "Permission for this action was denied by the Claude Code auto mode classifier. Reason: [PII Data Handling]." Not retried. Proposed default: keep the decision (a typed slash command is its own non-isMeta record).
2. Rule versions changed after DoR READY: QA analyst / lead QA re-confirm that cases point at CON-014 v7, CON-018 v2, CON-022 v11 (incl. CI-022-30).
3. The reviewer did not read roles-22/SHARED-RULES.md.
