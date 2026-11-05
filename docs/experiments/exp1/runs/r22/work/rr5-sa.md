# Requirements review 5 (SA rule edits), EXP1-R22C — REJECT (written by coordinator from the reviewer's reply)
PASS: CON-015 v7, CON-022 v7, CON-034 v2 (non-blocking gap: is a value of only spaces "missing"?), Q-020, Q-022.
REJECT: CON-027 v3 — two definitions of "unknown" disagree; Q-021 goes against answer 6.
- Sentence 1 (= answer 6): unknown when no run and no session for it exists in any log. New sentence: known when the comparison finds data (effective key, CON-002).
- Differ for: (a) a key that is only a main session's own key while its effective key is another ticket (answer 6: known; Q-021: unknown -> error page/exit 2 instead of a comparison: not small); (b) a key whose only runs have deleted log files (index rows only).
- Fix: one definition, answer 6 literally: known when any run, main session (own or effective key) or counted spawn (CON-014) carries it; a known key with no data by CON-013 shows "no main session" and 0 runs (brief item 4). Rework Q-021 accordingly. State plainly whether index rows of runs whose log is gone count as "in any log".
