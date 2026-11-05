0891a04 + uncommitted · step SA design for CON-010 v3 (HV-1) · next: builder implements change.md "Scan in progress"; BA records the proposed Agent decision (failed/killed scan -> 503 until next scan) · open bugs: HV-1 (design given), HV-2
- Design: meta row 'scan:<pid>' committed at ingest start; removed (own + dead pids) in the same commit as the final rebuild; page checks it in its one read snapshot.
- No schema change, existing pages unchanged; not BLOCKING.
- change.md: B2 503 row updated (v3 condition and text); new section "Scan in progress" at the end. Brief untouched.
- Backup: /tmp/sa-change-bak-r8.md. No code, test, rule or QUESTIONS.md edited.
