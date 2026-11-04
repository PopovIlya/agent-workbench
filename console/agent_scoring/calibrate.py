#!/usr/bin/env python3
"""Calibrate the agent-score judge against the person's verdicts.

Plain words
- Main goal: find out whether the model judge agrees with the person well enough to carry weight in S. Cohen's kappa between "the judge says the ticket's
  work is acceptable" (mean judge score of its runs >= 0.7) and "the person accepted it" (verdict accepted or accepted after rework).
- Does: reads ~/.agent-console/verdicts.jsonl (the person) and judge.jsonl (the judge) and scores.jsonl (which run belongs to which ticket), writes
  ~/.agent-console/calibration.json (judge_version, n, kappa). The judge check gets its weight only when n >= 30 and kappa >= 0.6.
- Does not: call a model unless the judge is switched on in ~/.agent-console/judge.json. With `--run` and the judge off it says so and stops.
- Example: python console/agent_scoring/calibrate.py            (compute kappa from what is there)
           python console/agent_scoring/calibrate.py --run      (judge the verdict tickets first; only when the judge is on)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from agent_scoring import judge as J  # noqa: E402

ACCEPTABLE_VERDICTS = ("accepted", "accepted_after_rework")


def latest_verdicts(state: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for ln in (state / "verdicts.jsonl").read_text().splitlines():
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            if o.get("ticket") and o.get("verdict"):
                out[o["ticket"]] = o["verdict"]
    except OSError:
        pass
    return out


def run_tickets(scores: Path) -> dict[str, str]:
    """task_id -> ticket, from the v2 score lines."""
    out: dict[str, str] = {}
    try:
        for ln in scores.read_text().splitlines():
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            if o.get("scorer_version") == 2 and o.get("ticket_eff"):
                out[o["task_id"]] = o["ticket_eff"]
    except OSError:
        pass
    return out


def compute(state: Path, scores: Path, now: datetime | None = None) -> dict:
    verdicts, tickets, per_run = latest_verdicts(state), run_tickets(scores), J.judge_results(state)
    by_ticket: dict[str, list[float]] = {}
    for tid, s in per_run.items():
        if tid in tickets:
            by_ticket.setdefault(tickets[tid], []).append(s)
    pairs = [(sum(v) / len(v) >= J.ACCEPTABLE, verdicts[t] in ACCEPTABLE_VERDICTS) for t, v in by_ticket.items() if t in verdicts]
    judge_says, person_says = [p[0] for p in pairs], [p[1] for p in pairs]
    kappa = J.cohen_kappa(judge_says, person_says)
    cfg = J.load_config(state)
    return {"judge_version": cfg["judge_version"], "n": len(pairs), "kappa": None if kappa is None else round(kappa, 4),
            "agreement": round(sum(1 for a, b in pairs if a == b) / len(pairs), 4) if pairs else None,
            "weight_active": J.is_calibrated({"n": len(pairs), "kappa": kappa, "judge_version": cfg["judge_version"]}),
            "generated_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state", default=None, help="state folder (default ~/.agent-console)")
    ap.add_argument("--out", default=str(J.state_dir() / "calibration.json"))
    ap.add_argument("--run", action="store_true", help="judge the tickets that have a verdict first (needs the judge switched on)")
    ap.add_argument("--roles-ref", default=None)
    a = ap.parse_args(argv)
    state = Path(a.state).expanduser() if a.state else J.state_dir()
    scores = state / "scores.jsonl"
    if a.run:
        cfg = J.load_config(state)
        if not J.is_on(cfg):
            print("judge is off (~/.agent-console/judge.json needs enabled, model and the same confirmed_model): nothing was run")
            return 0
        verdicts, tickets, done = latest_verdicts(state), run_tickets(scores), set(J.judge_results(state))
        todo = [t for t, k in tickets.items() if k in verdicts and t not in done]
        repo = HERE.parents[1]   # the workbench checkout
        print(J.judge_runs(repo, state, todo, J.Judge(cfg, state=state), a.roles_ref))
    cal = compute(state, scores)
    Path(a.out).write_text(json.dumps(cal, indent=1, sort_keys=True) + "\n")
    print(f"calibration: n={cal['n']} kappa={cal['kappa']} weight_active={cal['weight_active']} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
