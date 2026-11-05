#!/usr/bin/env python3
"""How much of the cost gap is the model mix? Re-price every message of the 22-role arm at sonnet-5-5 prices.
Reads the CSVs written by export_raw.py:  model_effect.py DIR   (DIR has messages-*.csv and pricing.yaml)"""
import csv, sys, os, yaml
d = sys.argv[1]
P = yaml.safe_load(open(os.path.join(d, "pricing.yaml")))["models"]
def key(model):
    for k in sorted(P, key=len, reverse=True):
        if k in model: return k
    return "opus-5-5" if "opus" in model else "sonnet-5-5" if "sonnet" in model else "haiku-4-5"
def cost(row, k):
    p = P[k]; g = lambda c: int(row[c])
    return (g("input") * p["input"] + g("output") * p["output"] + g("cache_write_5m") * p["cache_write_5m"] + g("cache_write_1h") * p["cache_write_1h"] + g("cache_read") * p["cache_read"]) / 1e6
res = {}
for arm in ("kit", "r22"):
    rows = list(csv.DictReader(open(os.path.join(d, "messages-%s.csv" % arm))))
    res[arm] = (sum(cost(r, key(r["model"])) for r in rows), sum(cost(r, "sonnet-5-5") for r in rows),
                sum(int(r[c]) for r in rows for c in ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")))
(ka, ks, kt), (ra, rs, rt) = res["kit"], res["r22"]
print("kit : actual %.2f, at sonnet prices %.2f, tokens %.2fM" % (ka, ks, kt / 1e6))
print("r22 : actual %.2f, at sonnet prices %.2f, tokens %.2fM" % (ra, rs, rt / 1e6))
print("gap actual %.2f; part from the model mix %.2f (%.0f%%); part from volume %.2f (%.0f%%)" % (ra - ka, ra - rs, 100 * (ra - rs) / (ra - ka), rs - ka, 100 * (rs - ka) / (ra - ka)))
print("cost ratio 22 roles / kit: actual %.1fx, at equal prices %.1fx; token ratio %.1fx" % (ra / ka, rs / ks, rt / kt))
print("cost per 1M tokens: kit %.2f, 22 roles %.2f" % (ka / kt * 1e6, ra / rt * 1e6))
