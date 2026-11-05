#!/usr/bin/env python3
"""Usage: chk_json.py FILE -> prints 'parsed' and 'KEYS_SORTED True|False' (every object at every depth)."""
import json, sys
t = open(sys.argv[1]).read()
d = json.loads(t)
ok = True
def chk(o):
    global ok
    if isinstance(o, dict):
        if list(o) != sorted(o): ok = False
        for v in o.values(): chk(v)
    elif isinstance(o, list):
        for v in o: chk(v)
chk(json.loads(t))
print("parsed"); print("KEYS_SORTED", ok)
