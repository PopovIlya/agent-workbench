# Requirements review 2 (BA part), EXP1-R22C — verdict REJECT (written by coordinator from the reviewer's reply)
F2..F6 of rr1 closed; Q-016..Q-019 accepted as small and narrowest. Coverage complete. F5 parent key checked against store.py:480-489: holds.
BLOCKING
1. CON-022 v4: "The person's answer to an AskUserQuestion ends the gap" contradicts "Each typed message ends at most one gap, which starts at the latest stop before it (after the previous typed message); earlier stops before the same typed message add nothing." Example: typed msg -> AskUserQuestion stop answered after 300 s -> end_turn stop -> person types later. Proposed (Agent decision, answer 37): a gap ends at a typed message or an AskUserQuestion answer; each such end closes at most one gap, starting at the latest stop after the previous end; earlier stops in the same stretch add nothing.
NON-BLOCKING: none.
