#!/usr/bin/env python3
"""Hand-checkable expected values for the check dataset. Prices read from pricing.yaml (base), arithmetic written out here."""
import yaml
P = yaml.safe_load(open("<workbench>/console/pricing.yaml"))["models"]
def cost(model, i, o, cr, cw):
    p = P[model]; return (i*p["input"] + o*p["output"] + cr*p["cache_read"] + cw*p["cache_write_5m"]) / 1e6
# CMPA-1 messages: (model, in, out, cache_read, cache_write_5m)
S, O = "sonnet-5-5", "opus-5-5"
main = [(S,1000,200,3000,2000),(S,500,100,4000,0),(S,100,50,500,0),(S,100,20,0,0),(S,200,50,1000,0),(S,100,20,500,0),(S,100,10,0,0)]
subs = [(O,2000,500,10000,1000),(O,1000,100,0,0),(S,800,300,2000,500),(S,300,100,1000,0)]
def tot(rows, model):
    r = [x for x in rows if x[0] == model]
    return [sum(x[k] for x in r) for k in (1,2,3,4)]
print("CMPA-1 tokens per model (input, output, cache_read, cache_write):")
for m in (S, O):
    t = [a + b for a, b in zip(tot(main, m), tot(subs, m))]
    c = sum(cost(x[0],*x[1:]) for x in main+subs if x[0]==m)
    print("  %s: %s cost %.6f" % (m, t, c))
cm = sum(cost(x[0],*x[1:]) for x in main); cs = sum(cost(x[0],*x[1:]) for x in subs)
print("  cost total %.6f, main %.6f, sub-agents %.6f, share main/sub %.4f" % (cm+cs, cm, cs, cm/cs))
print("  role runs: 3 (builder 2, reviewer 1); failed 1 (the reviewer: no final reply); repeat rounds 1")
print("  wall: 10:00:00 to 12:30:30 = 9030 s (150.5 min -> 151 min)")
print("  active role time (sum of run durations): builder one 10:00:10-10:10:10 = 600 s; reviewer 10:11:05-10:16:05 = 300 s; builder two 10:17:00-10:20:00 = 180 s; total 1080 s = 18 min")
print("  wait: stops at 10:10:20 (next person message 10:10:50, gap 30 s -> 0), at 10:20:10 (-> 10:25:10, 300 s), at 10:25:20 (-> 12:30:20, 7500 s); total 7800 s = 130 min; over 2 h part 7500 s")
# CMPB-1
b = [(S,400,100,1000,300)]
print("CMPB-1: one sub-agent run (reviewer), no main session. tokens sonnet: in 400, out 100, cache_read 1000, cache_write 300; cost %.6f ; failed 0; repeat 0 (its wall time is not checked)" % cost(S,*b[0][1:]))
print("  main-session rows must say 'no main session', not zero")
