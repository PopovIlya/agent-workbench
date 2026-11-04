"""The model judge for agent-score v2. BUILT AND SWITCHED OFF.

Plain words
- Main goal: for the quality a script cannot see, ask a model that did NOT see the agent's reasoning, one rubric dimension at a time, and take
  its answer only as far as a person has checked it (Cohen's kappa against the person's verdicts, see console/agent_scoring/calibrate.py).
- Does: split a role's criteria file into dimensions (one per output), build one isolated prompt per dimension (the role's input, its outputs and the
  dimension; never the agent's reasoning), call a headless `claude -p` session, parse `{score: 0..1 | "unknown", evidence: [...]}`, keep a per-call
  and a daily cost cap, and append every answer to ~/.agent-console/judge.jsonl.
- Does not: run unless ~/.agent-console/judge.json says `enabled: true` AND names a `model` AND repeats it as `confirmed_model` (the person confirms
  a model switch by writing it twice). With no file, or any of the three missing, `Judge.call` raises JudgeOff and nothing is sent anywhere.
- Example: Judge(load_config(state), runner=stub).judge_dimension(task_id=..., role="lead-qa", dimension=dim, spawn_prompt=..., outputs=...)
"""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404 - fixed argv, no shell
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import layout

JUDGE_VERSION = "1"
ACCEPTABLE = 0.7                 # a judge score at or above this counts as "acceptable" when comparing with the person's verdict
CALIBRATION_MIN_N = 30
CALIBRATION_MIN_KAPPA = 0.6
EVIDENCE_MAX = 5
EVIDENCE_CHARS = 200
OUTPUT_CHARS = 6000              # the most of an output (file, diff, reply) the judge is shown
DEFAULTS: dict[str, Any] = {"enabled": False, "model": "", "confirmed_model": "", "per_call_usd_cap": 0.25, "daily_usd_cap": 5.0,
                            "usd_per_mtok_in": 3.0, "judge_version": JUDGE_VERSION}


class JudgeOff(RuntimeError):
    """The judge is switched off, or its model was not confirmed, or a cost cap would be exceeded. Nothing was sent."""


def state_dir() -> Path:
    return Path(os.environ.get("AGENT_CONSOLE_HOME", "~/.agent-console")).expanduser()


def load_config(state: Path | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        cfg.update({k: v for k, v in json.loads(((state or state_dir()) / "judge.json").read_text()).items() if k in DEFAULTS})
    except (OSError, ValueError, AttributeError):
        pass
    return cfg


def is_on(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get("enabled")) and bool(cfg.get("model")) and cfg.get("confirmed_model") == cfg.get("model")


# ------------------------------------------------------------------------------------------------ rubric dimensions
@dataclass
class Dimension:
    key: str
    what: str


def dimensions(criteria_text: str) -> list[Dimension]:
    """One dimension per output of the criteria file (`- what | check | source`)."""
    m = re.search(r"^## Outputs[^\n]*\n(.*?)(?=^## |\Z)", criteria_text, re.S | re.M)
    out = []
    for ln in (m.group(1).splitlines() if m else []):
        if ln.startswith("- "):
            what = ln[2:].split(" | ")[0].strip()
            out.append(Dimension(re.sub(r"[^a-z0-9]+", "_", what.lower()).strip("_")[:40] or f"d{len(out) + 1}", what))
    return out


PROMPT = """You are a strict reviewer who did NOT do this work and has not seen how it was done.
Role under review: {role}
Rubric dimension: {what}

The task the role was given:
<task>
{task}
</task>

What the role produced:
<outputs>
{outputs}
</outputs>

Judge ONLY this dimension: does the produced work satisfy "{what}" as a careful person in this role would expect?
Answer with JSON only, no other text: {{"score": <number from 0 to 1>, "evidence": ["<short quote or file:line>", ...]}}
Use "unknown" instead of a number when the outputs above do not let you decide. Do not reward length or confident wording."""


def build_prompt(role: str, dim: Dimension, spawn_prompt: str, outputs: str) -> str:
    return PROMPT.format(role=role, what=dim.what, task=(spawn_prompt or "")[:OUTPUT_CHARS], outputs=(outputs or "")[:OUTPUT_CHARS])


def parse_judgement(text: str) -> dict[str, Any]:
    """{score: float | None, evidence: [str]}; None = "unknown". Anything that is not the asked-for JSON is "unknown" with the reason."""
    t = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.S)
    if fence:
        t = fence.group(1)
    elif not t.startswith("{"):
        m = re.search(r"\{.*\}", t, re.S)
        t = m.group(0) if m else t
    try:
        o = json.loads(t)
    except ValueError:
        return {"score": None, "evidence": [], "error": "not JSON"}
    if not isinstance(o, dict):
        return {"score": None, "evidence": [], "error": "not an object"}
    s = o.get("score")
    ev = [str(x)[:EVIDENCE_CHARS] for x in (o.get("evidence") or []) if isinstance(x, (str, int, float))][:EVIDENCE_MAX] if isinstance(o.get("evidence"), list) else []
    if isinstance(s, str) and s.strip().lower() == "unknown":
        return {"score": None, "evidence": ev}
    if isinstance(s, bool) or not isinstance(s, (int, float)) or not 0 <= float(s) <= 1:
        return {"score": None, "evidence": ev, "error": "score outside 0..1"}
    return {"score": float(s), "evidence": ev}


Runner = Callable[[str, str], "tuple[str, float]"]      # (prompt, model) -> (answer text, cost in USD)


def claude_runner(prompt: str, model: str) -> tuple[str, float]:
    """A separate headless session. Only reached when the judge is on."""
    r = subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", prompt], capture_output=True, text=True, timeout=300)  # nosec B603 B607
    if r.returncode != 0:
        raise RuntimeError("claude -p failed")
    d = json.loads(r.stdout)
    return str(d.get("result", "")), float(d.get("total_cost_usd") or 0.0)


class Judge:
    def __init__(self, cfg: dict[str, Any], runner: Runner | None = None, state: Path | None = None, now: Callable[[], datetime] | None = None):
        self.cfg, self.runner, self.state = cfg, runner or claude_runner, state or state_dir()
        self.now = now or (lambda: datetime.now(timezone.utc))

    def spent_today(self) -> float:
        day = self.now().strftime("%Y-%m-%d")
        total = 0.0
        try:
            for ln in (self.state / "judge_spend.jsonl").read_text().splitlines():
                o = json.loads(ln)
                if o.get("day") == day:
                    total += float(o.get("usd") or 0)
        except (OSError, ValueError):
            pass
        return total

    def call(self, prompt: str) -> tuple[str, float]:
        """The only place a model is reached. Raises JudgeOff before anything is sent."""
        if not is_on(self.cfg):
            raise JudgeOff("the judge is off: judge.json needs enabled, model and the same confirmed_model")
        est = len(prompt) / 4 / 1e6 * float(self.cfg["usd_per_mtok_in"])
        if est > float(self.cfg["per_call_usd_cap"]):
            raise JudgeOff(f"estimated cost ${est:.3f} is over the per-call cap ${self.cfg['per_call_usd_cap']}")
        if self.spent_today() >= float(self.cfg["daily_usd_cap"]):
            raise JudgeOff(f"the daily cap ${self.cfg['daily_usd_cap']} is reached")
        text, usd = self.runner(prompt, self.cfg["model"])
        self.state.mkdir(parents=True, exist_ok=True)
        with open(self.state / "judge_spend.jsonl", "a") as fh:
            fh.write(json.dumps({"day": self.now().strftime("%Y-%m-%d"), "usd": usd, "model": self.cfg["model"]}) + "\n")
        if usd > float(self.cfg["per_call_usd_cap"]):
            raise JudgeOff(f"the call cost ${usd:.3f}, over the per-call cap")
        return text, usd

    def judge_dimension(self, *, task_id: str, role: str, dimension: Dimension, spawn_prompt: str, outputs: str) -> dict[str, Any]:
        text, usd = self.call(build_prompt(role, dimension, spawn_prompt, outputs))
        j = parse_judgement(text)
        rec = {"ts": self.now().isoformat(timespec="seconds"), "task_id": task_id, "role": role, "dimension": dimension.key, "score": j["score"], "evidence": j["evidence"],
               "judge_version": self.cfg["judge_version"], "model": self.cfg["model"], "usd": round(usd, 5)}
        if j.get("error"):
            rec["error"] = j["error"]
        with open(self.state / "judge.jsonl", "a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec


def run_score(records: list[dict[str, Any]]) -> float | None:
    """The mean of the dimension scores that are not "unknown"; None when every one is unknown (the check stays empty)."""
    xs = [r["score"] for r in records if r.get("score") is not None]
    return sum(xs) / len(xs) if xs else None


def judge_results(state: Path) -> dict[str, float]:
    """task_id -> judge score, from the latest judge.jsonl records of each (task, dimension)."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        for ln in (state / "judge.jsonl").read_text().splitlines():
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            latest[(o.get("task_id"), o.get("dimension"))] = o
    except OSError:
        return {}
    by: dict[str, list[dict[str, Any]]] = {}
    for (t, _), o in latest.items():
        by.setdefault(t, []).append(o)
    return {t: s for t, rs in by.items() if (s := run_score(rs)) is not None}


# ------------------------------------------------------------------------------------------------ calibration
def cohen_kappa(a: list[bool], b: list[bool]) -> float | None:
    if not a or len(a) != len(b):
        return None
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def calibration(state: Path) -> dict[str, Any]:
    try:
        d = json.loads((state / "calibration.json").read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def is_calibrated(cal: dict[str, Any], cfg: dict[str, Any] | None = None) -> bool:
    """The judge check gets its weight only when it is on, n >= 30 and kappa >= 0.6 (for the current judge version)."""
    if cfg is not None and not is_on(cfg):
        return False
    return int(cal.get("n") or 0) >= CALIBRATION_MIN_N and (cal.get("kappa") or -1) >= CALIBRATION_MIN_KAPPA and (cfg is None or cal.get("judge_version") == cfg.get("judge_version"))


# ------------------------------------------------------------------------------------------------ running it on runs (only when it is on)
def run_inputs(ctx: Any, run: dict[str, Any], role: str, queries_m: Any) -> tuple[str, str]:
    """(spawn prompt, outputs text) of a run. Outputs = the final reply, the paths written and the first part of each written text. Never the
    agent's reasoning (the log's thinking blocks are not read)."""
    from . import agent_score as v1
    ev = v1.build_evidence(ctx, run, role, None)
    p = queries_m.show_text(ctx.store, run["run_id"], "prompt")
    parts = ["Final reply:\n" + (ev.reply or "(none)")[:3000], "Files written: " + (", ".join(w.path for w in ev.writes[:30]) or "(none)")]
    for w in ev.writes[:6]:
        if w.text:
            parts.append(f"--- {w.path}\n{w.text[:1500]}")
    return (p or {}).get("text") or "", "\n\n".join(parts)


def judge_runs(repo: Path, state: Path, task_ids: list[str], judge: Judge, roles_ref: str | None = None) -> dict[str, Any]:
    """Judge the given runs, one call per dimension. Raises JudgeOff at once when the judge is off."""
    if not is_on(judge.cfg):
        raise JudgeOff("the judge is off: nothing was run")
    from . import agent_score as v1
    store_m, parser_m, redact_m, scope_m, queries_m = v1._console(repo)
    st = store_m.Store()
    roles = v1.load_roles(repo, roles_ref)
    ctx = v1.Ctx(repo, st, parser_m, scope_m, redact_m.Redactor(repo / ".gitleaks.toml"), roles, set())
    db = st.reader()
    try:
        runs = {r["run_id"]: dict(r) for r in db.execute("SELECT * FROM runs WHERE kind='sub'")}
    finally:
        db.close()
    done = skipped = 0
    for tid in task_ids:
        run = runs.get(tid)
        if not run or run["role"] not in roles:
            skipped += 1
            continue
        crit = layout.criteria_path(repo, run["role"])
        dims = dimensions(crit.read_text(errors="replace")) if crit is not None else []
        task, outputs = run_inputs(ctx, run, run["role"], queries_m)
        for d in dims:
            judge.judge_dimension(task_id=tid, role=run["role"], dimension=d, spawn_prompt=task, outputs=outputs)
        done += 1
    return {"judged_runs": done, "skipped": skipped}
