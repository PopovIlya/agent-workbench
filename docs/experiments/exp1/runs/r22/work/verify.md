# Verifier, EXP1-R22C — PASS (written by the coordinator from the verifier's reply; the role cannot write in the repo)
Throwaway consoles on 127.0.0.1:18931 / 18932, empty AGENT_CONSOLE_HOME and log root under /tmp/exp1-r22c-verify (deleted); synthetic logs (AAA-1, BBB-2 no main session, ZZZ-9, TTT-1/UUU-1).
Page: 200 table + difference column; figures match hand calculation; "no main session" in 8 main rows, totals real; "no sub-agents" share; 422 (missing b, empty, spaces); 404 "Unknown ticket key: NOPE-1"; 503 during first index (also for an unknown key), then 404; rounding ties away from zero, -0 -> $0.00, page == CLI text; Host guard (evil.com 404, wrong port 404); CSP, nosniff, DENY, no-referrer, no-store.
CLI: text table exit 0; --json byte-identical twice, sorted keys at every level, raw values; unknown key exit 2; usage exit 2; same key twice OK; guarded refresh refuses on another TZ, exit 2, index md5 unchanged; no-argument start binds only the chosen port.
Not tested: exit 1 (unreadable/locked index); repo suite. 503 body text not captured.
Open bugs: 0.
Coordinator note: the verifier said it wrote nothing in the repo, but an untracked console/out.html (17:49, synthetic AAA-1 compare page, 5748 bytes) appeared during its run; the coordinator removed it.
