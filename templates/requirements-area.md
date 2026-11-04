# Requirements: <area>

File: `docs/requirements/<area>.md`. One block per rule. Questions go to `docs/requirements/QUESTIONS.md` with the rule ID.

Rule IDs are `<AREA>-NNN` (area prefix in capitals, three or more digits). An ID is never reused, even for a retired rule.

Status values:
- `observed` — the code does this today. Not yet confirmed as intended. No tests are written for it.
- `confirmed` — the human confirmed it is the intended behaviour. Tests required.
- `new` — comes from a ticket. Tests required.
- `retired` — no longer wanted. Tests for it are findings.

Only the human changes a status to `confirmed` or `retired`.

---

### AREA-001
- status: observed
- statement: <one fact in business language>
- source: <path:line, or the ticket key>
- scope: <ticket block this rule belongs to, e.g. 6.3; required on every rule>
- tests: none
- notes: <changes: AREA-0NN, UNVERIFIED:, CONFLICT:, anything else; optional>

### AREA-002
- status: new
- statement: <...>
- source: <KEY>
- scope: <...>
- tests: none
- notes:
