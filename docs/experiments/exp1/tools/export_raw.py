#!/usr/bin/env python3
"""Export the raw numbers behind tokens.md as small CSV files (no message text), so every figure can be recomputed.
Run from the console venv:  console/.venv/bin/python export_raw.py OUT_DIR
Needs count_tokens.py next to it (its paths at the top point to the workbench checkout and the session logs)."""
import csv, datetime, os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import count_tokens as C

def iso(x): return datetime.datetime.fromtimestamp(x, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for name in C.ARMS:
    a = C.arm(name); raw = a["_raw"]
    with open(os.path.join(out, "messages-%s.csv" % name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["message_id", "role", "model", "input", "output", "cache_write_5m", "cache_write_1h", "cache_read", "cost_usd"])
        for mid, role, model, tok in sorted(raw["messages"], key=lambda x: x[0]):
            cost, _ = C.PR.message_cost(model, tok)
            w.writerow([mid, role, model, tok["input"], tok["output"], tok["cache_w5m"], tok["cache_w1h"], tok["cache_read"], "" if cost is None else "%.8f" % cost])
    with open(os.path.join(out, "runs-%s.csv" % name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["file", "kind", "role", "first_ts_utc", "last_ts_utc", "duration_s"])
        for r in sorted(raw["runs"], key=lambda r: r["first_ts"]):
            w.writerow([r["file"], r["kind"], r["role"], iso(r["first_ts"]), iso(r["last_ts"]), "%.1f" % (r["last_ts"] - r["first_ts"])])
    with open(os.path.join(out, "waits-%s.csv" % name), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["stop_ts_utc", "person_message_ts_utc", "gap_s", "counts_as_wait(gap>=60)", "message_kind(human|ops)"])
        for gap, kind, t0, t1 in waits if (waits := raw["waits"]) else []:
            w.writerow([iso(t0), iso(t1), "%.1f" % gap, "yes" if gap >= 60 else "no", kind])
shutil.copy("<workbench>/console/pricing.yaml", os.path.join(out, "pricing.yaml"))
print("written to", out)
