#!/usr/bin/env python3
"""Neutral synthetic log root for the independent check: two tickets with known, hand-computable numbers."""
import json, os, shutil, datetime
ROOT = "/tmp/exp1-check-logs/-work-app"
shutil.rmtree("/tmp/exp1-check-logs", ignore_errors=True)
D = "2026-10-20"
def T(h, m, s): return "%sT%02d:%02d:%02d.000Z" % (D, h, m, s)
_n = [0]
def uid(): _n[0] += 1; return "u%04d" % _n[0]
def use(i, o, cr=0, cw=0):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw,
            "cache_creation": {"ephemeral_5m_input_tokens": cw, "ephemeral_1h_input_tokens": 0}}
def W(path, recs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write("\n".join(json.dumps(r) for r in recs) + "\n")
def base(typ, t, sess, side=False, agent=None):
    r = {"parentUuid": None, "isSidechain": side, "type": typ, "uuid": uid(), "timestamp": t, "sessionId": sess, "cwd": "/work/app", "gitBranch": "main"}
    if agent: r["agentId"] = agent
    return r
def prompt(t, sess, text, side=False, agent=None, human=True):
    r = base("user", t, sess, side, agent); r["message"] = {"role": "user", "content": text}
    if human and not side: r["origin"] = {"kind": "human"}
    return r
def asst(t, sess, mid, model, u, content, stop, side=False, agent=None):
    r = base("assistant", t, sess, side, agent)
    r["message"] = {"id": mid, "model": model, "stop_reason": stop, "usage": u, "content": content}
    return r
def text(s): return [{"type": "text", "text": s}]
def spawn(tid, role, desc): return [{"type": "tool_use", "id": tid, "name": "Agent", "input": {"subagent_type": role, "description": desc, "prompt": "do it"}}]
def result(t, sess, tid, err=False):
    r = base("user", t, sess); r["toolUseResult"] = {"status": "completed"}
    r["message"] = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "is_error": err, "content": "ok"}]}
    return r
def sub(sess, agent, role, tid, desc, recs):
    p = "%s/%s/subagents/agent-%s" % (ROOT, sess, agent)
    W(p + ".jsonl", recs)
    json.dump({"agentType": role, "toolUseId": tid, "spawnDepth": 1, "description": desc}, open(p + ".meta.json", "w"))
S, SON, OPU = "S-A", "claude-sonnet-5-5", "claude-opus-5-5"
# ---------- ticket CMPA-1 (main session S-A + 3 sub-agent runs) ----------
main = [prompt(T(10,0,0), S, "[CMPA-1] Build the thing."),
        asst(T(10,0,5), S, "mA1", SON, use(1000, 200, 3000, 2000), spawn("tA1", "builder", "[CMPA-1] builder one"), "tool_use")]
sub(S, "a1", "builder", "tA1", "[CMPA-1] builder one", [
    prompt(T(10,0,10), S, "do it", True, "a1"),
    asst(T(10,5,0), S, "sA1x", OPU, use(2000, 500, 10000, 1000), [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/work/app/x"}}], "tool_use", True, "a1"),
    asst(T(10,10,10), S, "sA1y", OPU, use(1000, 100, 0, 0), text("Built it. PASS"), "end_turn", True, "a1")])
main += [result(T(10,10,15), S, "tA1"),
         asst(T(10,10,20), S, "mA2", SON, use(500, 100, 4000, 0), text("Done, over to you."), "end_turn"),
         prompt(T(10,10,50), S, "ok, carry on"),                              # gap 30 s -> counts as zero
         asst(T(10,11,0), S, "mA3", SON, use(100, 50, 500, 0), spawn("tA2", "reviewer", "[CMPA-1] reviewer one"), "tool_use")]
sub(S, "a2", "reviewer", "tA2", "[CMPA-1] reviewer one", [                  # never gives a final reply: failed
    prompt(T(10,11,5), S, "review", True, "a2"),
    asst(T(10,16,5), S, "sA2x", SON, use(800, 300, 2000, 500), [{"type": "tool_use", "id": "r2", "name": "Read", "input": {"file_path": "/work/app/y"}}], "tool_use", True, "a2")])
main += [result(T(10,16,10), S, "tA2", err=True),
         asst(T(10,16,55), S, "mA3b", SON, use(100, 20, 0, 0), spawn("tA3", "builder", "[CMPA-1] builder two"), "tool_use")]
sub(S, "a3", "builder", "tA3", "[CMPA-1] builder two", [                    # second builder run: one repeat round
    prompt(T(10,17,0), S, "again", True, "a3"),
    asst(T(10,20,0), S, "sA3x", SON, use(300, 100, 1000, 0), text("Fixed. PASS"), "end_turn", True, "a3")])
main += [result(T(10,20,5), S, "tA3"),
         asst(T(10,20,10), S, "mA4", SON, use(200, 50, 1000, 0), text("Ready."), "end_turn"),
         prompt(T(10,25,10), S, "good"),                                      # gap 300 s counts
         asst(T(10,25,20), S, "mA5", SON, use(100, 20, 500, 0), text("Thanks."), "end_turn"),
         prompt(T(12,30,20), S, "one more thing"),                            # gap 7500 s counts; over 2 h
         asst(T(12,30,30), S, "mA6", SON, use(100, 10, 0, 0), text("Done."), "end_turn")]
W("%s/%s.jsonl" % (ROOT, S), main)
# ---------- ticket CMPB-1 (one sub-agent run, no main session of its own) ----------
S2 = "S-C"
m2 = [prompt(T(14,0,0), S2, "[CMPC-1] Other work."),
      asst(T(14,0,5), S2, "mC1", SON, use(50, 10, 0, 0), spawn("tB1", "reviewer", "[CMPB-1] reviewer"), "tool_use"),
      asst(T(14,0,6), S2, "mC2", SON, use(50, 10, 0, 0), spawn("tC1", "builder", "[CMPC-1] builder"), "tool_use")]
sub(S2, "b1", "reviewer", "tB1", "[CMPB-1] reviewer", [
    prompt(T(14,0,10), S2, "review", True, "b1"),
    asst(T(14,2,10), S2, "sB1x", SON, use(400, 100, 1000, 300), text("PASS"), "end_turn", True, "b1")])
sub(S2, "c1", "builder", "tC1", "[CMPC-1] builder", [
    prompt(T(14,0,12), S2, "build", True, "c1"),
    asst(T(14,1,12), S2, "sC1x", SON, use(10, 10, 0, 0), text("PASS"), "end_turn", True, "c1")])
m2 += [result(T(14,2,15), S2, "tB1"), result(T(14,2,16), S2, "tC1"),
       asst(T(14,2,20), S2, "mC3", SON, use(50, 10, 0, 0), text("done"), "end_turn")]
W("%s/%s.jsonl" % (ROOT, S2), m2)
print("written", ROOT)
