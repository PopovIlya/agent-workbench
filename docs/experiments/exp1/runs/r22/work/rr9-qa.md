# Requirements review 9 (DoR part 3 re-check), EXP1-R22C — PASS (written by coordinator from the reviewer's reply)
rr8 1-3 closed. CON-022 v10 consistent and testable (example 1800 s); CON-011 v5; Q-033 small and narrowest; surviving field not seen in real data: acceptable for DoR. qa.md 95 conditions, 227 items reconciled.
Non-blocking:
N1 CON-022: two gaps in one file sharing message.id+requestId (parallel stop records of one reply): narrowest = one gap; confirm at build time.
N2 CON-022: a copy with both keys rewritten is not matched (residual risk, in notes).
N3 change.md: SA rule-change list stops at CON-022 v7 / CON-011 v3; no reader detail for collecting stop keys (uuid, message.id, requestId).
