"""Agent score v2 (plan: outcome-first quality checks).

Plain words
- Main goal: score a finished role run by what it PRODUCED, not by the path it took. A gate decides whether the deliverable exists;
  five weighted checks decide how good it is; checks that have no data stay EMPTY and the rest is renormalised. `coverage` says how much
  of the weight had a value; S is shown only when coverage >= 0.5.
- Does: reads runs through the agent console's index and parser (as v1), writes `scorer_version: 2` lines to ~/.agent-console/scores.jsonl
  next to the v1 lines (never edits or removes them), reads the person's verdicts, defect reports and flag decisions from ~/.agent-console/.
- Does not: call a model (the judge is built in qa_tools/judge.py and is OFF), write into the repository, or invent data. An outcome check
  without data is left empty with the reason "no data yet".
- Example: `cd console && .venv/bin/python -m agent_scoring agent-score --v2 --since 2026-01-01`

Weights: first_pass 0.25 · outcome 0.30 · judge 0.25 · follows 0.10 · grounded 0.10. `budget` is gone (cost and time are their own axis).
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import agent_score as v1
from . import layout, project as projectmod

SCORER_VERSION = 2
SCORE_SETTLE_S = 600            # a sub-agent run is finished when sub_meta.finished is set, or when nothing was written for this long
COVERAGE_MIN = 0.5              # S is shown only when the checks that have a value carry at least this share of the weight
BAR = v1.BAR
GENERIC_CAP = v1.GENERIC_CAP
OUT_OF_SCOPE_CAP = 0.5
WEIGHTS = {"first_pass": 0.25, "outcome": 0.30, "judge": 0.25, "follows": 0.10, "grounded": 0.10}
ORDER = ("first_pass", "outcome", "judge", "follows", "grounded")
ESCAPE_DAYS = 14
STRUCT_MIN_CHARS = 300          # a reply shorter than this is not a "structured block"

# Roles with an outcome check implemented from data the logs and the repo already hold.
TRACE_ROLES = ("business-analyst", "system-analyst", "qa-analyst")
MUTATION_ROLES = ("test-designer", "automation-engineer")
GATE_ESCAPE_ROLES = ("reviewer", "verifier", "security-engineer", "independent-auditor")
CONSUMED_ROLES = ("lead-qa", "test-manager", "environment-checker")

# Where a deliverable may reasonably be besides the path in its criteria file: a brief may name its own folders.
ALT_PATHS = {
    "qa/cases/*.yaml": ("**/drafts/*.yaml", "**/cases/*.yaml"),
    "docs/tasks/**/TRIAGE-*.md": ("**/*triage*.md", "**/*TRIAGE*.md"),
}


# ------------------------------------------------------------------------------------------------ small value types
@dataclass
class Check:
    key: str
    c: float | None
    reason: str = ""
    pending: bool = False       # first_pass only: the gate has not given a verdict yet
    omitted: str = ""           # why an empty check is empty ("no data yet", ...)

    def public(self) -> dict[str, Any]:
        d: dict[str, Any] = {"c": None if self.c is None else round(self.c, 4), "w": WEIGHTS[self.key], "reason": self.reason}
        if self.c is None:
            d["omitted"] = self.omitted or "no data yet"
        if self.pending:
            d["pending"] = True
        return d


@dataclass
class Gate:
    delivered: bool
    named: str = ""             # the output that was not found
    found_in: list[str] = field(default_factory=list)   # where each found output was found: run | ticket | git | reply

    def public(self) -> dict[str, Any]:
        d: dict[str, Any] = {"delivered": self.delivered, "found_in": self.found_in}
        if not self.delivered:
            d["reason"] = f"not delivered: {self.named}"
        return d


@dataclass
class Ticket:
    """Everything the checks need to know about one ticket besides the run being scored."""
    key: str | None
    runs: list[dict[str, Any]] = field(default_factory=list)          # all sub-runs of the ticket (index rows), by start
    cwds: list[str] = field(default_factory=list)
    git_files: set[str] = field(default_factory=set)                  # repo-relative paths changed on the ticket branch / worktree
    replies: dict[str, str] = field(default_factory=dict)             # run_id -> final reply text (lazy, filled by the runner)
    read: Callable[[str], str] | None = None                          # path -> text of that file on the ticket branch / the trunk
    project: projectmod.Project = field(default_factory=lambda: projectmod.Project(None))

    def text_of_files(self, limit: int = 40) -> str:
        """Text of the ticket's documents (md / yaml under docs/ and qa/), for a "contains" output written by a script."""
        if self.read is None:
            return ""
        paths = sorted(p for p in self.git_files if re.match(r"(docs|qa)/.*\.(md|ya?ml)$", p))[:limit]
        return "\n".join(self.read(p) for p in paths)


def structured_block(reply: str | None) -> bool:
    """A reply that carries its result as a structure: a fenced block, a table, a list of 4+ items or 3+ labelled lines. Long enough to be a report."""
    if not reply or len(reply.strip()) < STRUCT_MIN_CHARS:
        return False
    if re.search(r"```[^\n]*\n(?:.*\n){2,}?.*```", reply):
        return True
    if len(re.findall(r"(?m)^\s*\|.*\|\s*$", reply)) >= 3:
        return True
    if len(re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+\S", reply)) >= 4:
        return True
    return len(re.findall(r"(?m)^\s*(?:#{1,4}\s+\S|\*\*[^*\n]{2,40}:?\*\*:?)", reply)) >= 3


def _glob_any(path: str, pats: list[str]) -> bool:
    return v1.glob_match(path, pats)


VERDICT_RE = re.compile(r"\b(PASS(?:ED)?|APPROVE[D]?|ACCEPT(?:ED)?|REJECT(?:ED)?)\b")


def verdict_of(reply: str | None) -> str | None:
    """PASS or REJECT from a gate's reply. APPROVE / ACCEPT count as PASS (lead-qa answers APPROVE); the first verdict word wins."""
    if not reply:
        return None
    m = VERDICT_RE.search(reply)
    if not m:
        return None
    return "REJECT" if m.group(1).startswith("REJECT") else "PASS"


def known_rule_ids(top: Path | None) -> set[str]:
    """Rule ids of the project's requirement map: headings, table rows and bullet rules (project.rule_ids)."""
    return v1.known_rule_ids(top)


# ------------------------------------------------------------------------------------------------ A1: the delivered gate
def delivered(ev: v1.Evidence, f: v1.RoleFacts, tk: Ticket, role_runs_writes: list[v1.Write]) -> Gate:
    """The role's deliverable exists anywhere it could reasonably be. For each checkable output: a file written in this run, in an earlier or
    later round of the same role on the ticket, or on the ticket branch / worktree (git), at the path of the criteria file or at an alternative
    place a brief may name; for a file output also a structured block in the final reply. A reply output needs its regex; a "contains" output
    needs the text in something written. Not delivered = the first output that none of these satisfies."""
    checkable = [o for o in f.outputs if o.kind != "none"]
    if not checkable:
        return Gate(True, found_in=["not checkable"])
    where: list[str] = []
    for o in checkable:
        if o.kind == "write":
            raw = [p.strip() for p in o.arg.split(",") if p.strip()]
            pats = projectmod.expand(raw, ev.project)
            if not pats:
                where.append("not checkable here")      # its gate is not declared in this project
                continue
            alts = [a for p in raw for a in ALT_PATHS.get(p, ())]
            if any(w.nonempty and _glob_any(w.path, pats + alts) for w in ev.writes):
                where.append("run")
            elif any(w.nonempty and _glob_any(w.path, pats + alts) for w in role_runs_writes):
                where.append("ticket")
            elif any(_glob_any(p, pats + alts) for p in tk.git_files):
                where.append("git")
            elif structured_block(ev.reply):
                where.append("reply")
            else:
                return Gate(False, o.what)
        elif o.kind == "reply":
            if ev.reply and ev.reply.strip() and (not o.arg or re.search(o.arg, ev.reply)):
                where.append("reply")
            else:
                return Gate(False, o.what)
        elif o.kind == "contains":
            if any(o.arg.lower() in w.text.lower() for w in ev.writes if w.nonempty):
                where.append("run")
            elif any(o.arg.lower() in w.text.lower() for w in role_runs_writes if w.nonempty):
                where.append("ticket")
            elif o.arg.lower() in tk.text_of_files().lower():
                where.append("git")
            elif ev.reply and o.arg.lower() in ev.reply.lower():
                where.append("reply")
            else:
                return Gate(False, o.what)
    return Gate(True, found_in=where)


# ------------------------------------------------------------------------------------------------ A2: the checks
def check_first_pass(f: v1.RoleFacts, ev: v1.Evidence, verdicts: list[v1.Verdict]) -> Check:
    """The next gate accepted the work without sending it back: 1 = no return, 0.5 = one, 0 = two or more. Pending until a verdict exists."""
    if not f.next_gates:
        return Check("first_pass", None, omitted="no next gate is defined for this role")
    if not ev.ticket:
        return Check("first_pass", None, "ticket key unknown: cannot link a gate verdict", pending=True, omitted="pending: ticket unknown")
    got = [v for v in verdicts if v.verdict]
    if not got:
        return Check("first_pass", None, f"no verdict from {' / '.join(f.next_gates)} yet", pending=True, omitted="pending: waiting for the gate's verdict")
    returns = sum(1 for v in got if v.verdict == "REJECT")
    c = 1.0 if returns == 0 else 0.5 if returns == 1 else 0.0
    return Check("first_pass", c, "" if returns == 0 else f"returned {returns}x: " + ", ".join(f"{v.gate} REJECT" for v in got if v.verdict == "REJECT"))


def check_follows(ev: v1.Evidence, f: v1.RoleFacts) -> Check:
    c = v1.c2_follows(ev, f)
    return Check("follows", c.c, c.reason)


def grounded_items(ev: v1.Evidence, rule_ids: set[str]) -> tuple[int, int]:
    """(unrecorded, total) over the new cases and tests the run wrote: the share makes partial credit possible."""
    bad = total = 0
    for w in ev.writes:
        if not w.in_repo or not w.text:
            continue
        if (ev.project.case_globs and projectmod.glob_any(w.path, ev.project.case_globs)) or re.search(r"(^|/)drafts/[^/]+\.ya?ml$", w.path):
            for blk in re.split(r"(?m)^\s*-\s+id:", w.text)[1:]:
                total += 1
                mm = re.search(r"rules?:(.*?)(?:\n\s*\w+:|\Z)", blk, re.S)
                cited = v1.RULE_ID_RE.findall(mm.group(1) if mm else "")
                if not cited or not any(c in rule_ids for c in cited):
                    bad += 1
        elif re.search(r"(^|/)(test_[^/]*\.py|[^/]*\.(test|spec)\.tsx?)$", w.path):
            found = list(re.finditer(r"(?:def (test_\w+)|\b(?:it|test)\(\s*['\"]([^'\"]+))", w.text))
            for i, m in enumerate(found):
                total += 1
                above = []
                for ln in reversed(w.text[: m.start()].splitlines()):
                    if ln.strip().startswith(("@", "#")) or not ln.strip():
                        above.append(ln)
                    else:
                        break
                below = w.text[m.end(): found[i + 1].start() if i + 1 < len(found) else len(w.text)][:300]
                cited = v1.RULE_ID_RE.findall("\n".join(above) + "\n" + below)
                if not cited or not any(c in rule_ids for c in cited):
                    bad += 1
    return bad, total


def check_grounded(ev: v1.Evidence, f: v1.RoleFacts, rule_ids: set[str]) -> Check:
    if not f.criterion3:
        return Check("grounded", None, omitted="this role makes no decisions or tests that need a rule id (criteria file)")
    bad, total = grounded_items(ev, rule_ids)
    if not total:
        return Check("grounded", None, omitted="no new case or test in this run to check")
    return Check("grounded", 1 - bad / total, "" if not bad else f"{bad} of {total} new cases or tests cite no known rule id")


# ---- outcome ----
def check_traceability(ev: v1.Evidence, tk: Ticket, rule_ids: set[str], referenced: set[str], change_text: str) -> Check:
    """Share of the requirement ids in the role's output that at least one test case references at the end of the ticket,
    times (1 - share of UNVERIFIED / CONFLICT markers left open)."""
    ids = set()
    for w in ev.writes:
        ids |= {i for i in v1.RULE_ID_RE.findall(w.text or "") if i in rule_ids}
    ids |= {i for i in v1.RULE_ID_RE.findall(ev.reply or "") if i in rule_ids}       # the report names the rules it changed
    if not ids:
        return Check("outcome", None, omitted="no requirement id in this run's output")
    if not referenced and not tk.git_files and not tk.key:
        return Check("outcome", None, omitted="no test cases found for the ticket yet")
    share = len(ids & referenced) / len(ids)
    # a marker is `UNVERIFIED:` / `CONFLICT:` (the repo's convention); a line that also says it is done, closed or corrected is not open
    marks = [ln for ln in change_text.splitlines() if re.search(r"\b(UNVERIFIED|CONFLICT)\s*:", ln)]
    open_marks = sum(1 for ln in marks if not re.search(r"(?i)\b(done|resolved|closed|answered|corrected|can close|fixed)\b", ln))
    share_open = (open_marks / len(marks)) if marks else 0.0
    c = share * (1 - share_open)
    parts = [f"{len(ids & referenced)} of {len(ids)} requirement ids are referenced by a test case"]
    if open_marks:
        parts.append(f"{open_marks} of {len(marks)} UNVERIFIED / CONFLICT marker(s) still open")
    return Check("outcome", c, "; ".join(parts) if c < 1 else "")


def check_escapes_requirements(run: dict[str, Any], tk: Ticket, verdict: str | None) -> Check:
    """requirements-reviewer: no requirement defect it passed was sent back later by test-designer or builder on the same ticket."""
    if verdict != "PASS":
        return Check("outcome", None, omitted="the reviewer did not pass the work: nothing to escape")
    later = [r for r in tk.runs if r["role"] in ("test-designer", "builder") and (r["start_ts"], r["run_id"]) > (run["start_ts"], run["run_id"])]
    if not later:
        return Check("outcome", None, omitted="pending: no test-designer or builder run after it yet")
    words = r"(?:defect\w*|conflict\w*|ambiguous|contradict\w*|unclear|missing|wrong)"
    pat = re.compile(rf"(?i)\b(?:requirement|rule)s?\b[^.\n]{{0,80}}\b{words}\b|\b{words}\b[^.\n]{{0,80}}\b(?:requirement|rule)s?\b")
    hits = [r["role"] for r in later if pat.search(tk.replies.get(r["run_id"]) or "") and v1.RULE_ID_RE.search(tk.replies.get(r["run_id"]) or "")]
    return Check("outcome", 0.0 if hits else 1.0, f"{hits[0]} reported a requirement defect after it passed the work" if hits else "")


def check_mutation(ticket: str | None, state: Path) -> Check:
    p = state / "mutation" / f"{ticket}.json" if ticket else None
    if not p or not p.is_file():
        return Check("outcome", None, omitted="no mutation run for this ticket yet")
    try:
        d = json.loads(p.read_text())
        planted, killed = int(d["planted"]), int(d["killed"])
    except (ValueError, KeyError, TypeError):
        return Check("outcome", None, omitted="the mutation result file is unreadable")
    if planted <= 0:
        return Check("outcome", None, omitted="the mutation run planted no mutant")
    c = killed / planted
    return Check("outcome", c, "" if c == 1 else f"{killed} of {planted} planted mutants were killed by the tests")


def check_green_first_time(run: dict[str, Any], tk: Ticket, suite_runs: list[dict[str, Any]]) -> Check:
    """builder: the first full local suite run after its change is green (1); green after one fix round (0.5); else 0."""
    if not suite_runs:
        return Check("outcome", None, omitted="no suite run (pytest) found after the builder's change")
    first = suite_runs[0]
    if not first["error"]:
        return Check("outcome", 1.0)
    if len(suite_runs) > 1 and not suite_runs[1]["error"]:
        return Check("outcome", 0.5, "the first suite run was red; green after one fix round")
    return Check("outcome", 0.0, "the first suite run was red" + ("" if any(not s["error"] for s in suite_runs[1:]) else " and no later run is green") + (" (green only after more than one fix round)" if any(not s["error"] for s in suite_runs[1:]) else ""))


def check_gate_escapes(role: str, run: dict[str, Any], verdict: str | None, defects: list[dict[str, Any]], now: datetime, defects_exist: bool) -> Check:
    """reviewer, verifier, security-engineer, independent-auditor: no defect was reported later on work they passed, within ESCAPE_DAYS."""
    if verdict != "PASS":
        return Check("outcome", None, omitted="it did not pass the work: nothing to escape")
    if not defects_exist:
        return Check("outcome", None, omitted="no defect reports yet")
    mine = [d for d in defects if role in (d.get("roles") or []) and d.get("ticket") == run.get("ticket_eff")]
    if mine:
        return Check("outcome", 0.0, f"{len(mine)} defect report(s) name this role on the ticket")
    age = (now - datetime.fromisoformat(run["end_ts"].replace("Z", "+00:00"))).total_seconds() / 86400
    if age < ESCAPE_DAYS:
        return Check("outcome", None, omitted=f"pending: {ESCAPE_DAYS} days have not passed since it passed the work")
    return Check("outcome", 1.0)


COUNT_RES = {"passed": re.compile(r"(\d+)\s+passed"), "failed": re.compile(r"(\d+)\s+failed"), "errors": re.compile(r"(\d+)\s+errors?\b"), "skipped": re.compile(r"(\d+)\s+skipped")}
SUMMARY_RE = re.compile(r"=+ .*?(?:passed|failed|error).*? in [\d.]+s.*?=+|^\d+ (?:passed|failed).*? in [\d.]+s", re.M)


def counts_of(text: str) -> dict[str, int]:
    return {k: int(m.group(1)) for k, rx in COUNT_RES.items() if (m := rx.search(text))}


def check_honest_report(reply: str | None, pytest_summaries: list[str]) -> Check:
    """test-runner: the pass, fail and error counts in its report equal the pytest summary line in the log."""
    if not pytest_summaries:
        return Check("outcome", None, omitted="no pytest summary line in the log")
    said = counts_of(reply or "")
    said = {k: v for k, v in said.items() if k in ("passed", "failed", "errors")}
    if not said:
        return Check("outcome", None, omitted="the report states no pass, fail or error count")
    real = counts_of(pytest_summaries[-1])
    wrong = [k for k, v in said.items() if real.get(k, 0) != v]
    return Check("outcome", 1 - len(wrong) / len(said), "" if not wrong else "the report says " + ", ".join(f"{k} {said[k]} (log: {real.get(k, 0)})" for k in wrong))


def check_consumed(run: dict[str, Any], tk: Ticket) -> Check:
    """lead-qa, test-manager, environment-checker: the next role used its output without a return (the role is not run again as rework)."""
    later = [r for r in tk.runs if (r["start_ts"], r["run_id"]) > (run["start_ts"], run["run_id"])]
    if not later:
        return Check("outcome", None, omitted="pending: no later role has used it yet")
    again = [r for r in later if r["role"] == run["role"] and "returned" in (r.get("flag_names") or [])]
    return Check("outcome", 0.0 if again else 1.0, "the role had to run again as rework after a gate" if again else "")


def check_judge(task_id: str, state: Path, calibrated: bool, results: dict[str, float]) -> Check:
    """The model judge's rubric score. Empty until the judge is switched on AND calibrated (n >= 30, kappa >= 0.6)."""
    if not calibrated:
        return Check("judge", None, omitted="judge off or not calibrated yet")
    if task_id not in results:
        return Check("judge", None, omitted="no judge verdict for this run")
    return Check("judge", results[task_id])


# ------------------------------------------------------------------------------------------------ the score
def combine(checks: list[Check]) -> tuple[float | None, float]:
    """(S renormalised over the checks that have a value, coverage = the sum of their weights)."""
    used = [c for c in checks if c.c is not None]
    cov = sum(WEIGHTS[c.key] for c in used)
    if not used:
        return None, 0.0
    return sum(WEIGHTS[c.key] * c.c for c in used) / cov, round(cov, 4)  # type: ignore[operator]


def score_v2(checks: list[Check], gate: Gate, *, secrets: list[tuple[str, str]], confirmed_deception: bool, out_of_scope: bool, generic_for: str | None,
             agent_type: str) -> dict[str, Any]:
    s, cov = combine(checks)
    hard = None
    shown = s is not None and cov >= COVERAGE_MIN
    s_out: float | None = s if shown else None
    if secrets:
        s_out, hard = 0.0, {"limit": "secret", "detail": "; ".join(f"{r} in {w}" for r, w in secrets[:5])}
    elif confirmed_deception:
        s_out, hard = 0.0, {"limit": "deception_confirmed", "detail": "confirmed by the person"}
    elif not gate.delivered:
        s_out, hard = 0.0, {"limit": "not_delivered", "detail": f"not delivered: {gate.named}"}
    else:
        if out_of_scope and s_out is not None and s_out > OUT_OF_SCOPE_CAP:
            s_out, hard = OUT_OF_SCOPE_CAP, {"limit": "out_of_scope_edit", "detail": "edited outside the role's paths or the ticket's modules"}
        if generic_for and s_out is not None and s_out > GENERIC_CAP:
            s_out, hard = GENERIC_CAP, {"limit": "generic_for_role", "detail": f"{agent_type} did the work of {generic_for}"}
    returns = 0
    fp = next(c for c in checks if c.key == "first_pass")
    m = re.match(r"returned (\d+)x", fp.reason)
    if m:
        returns = int(m.group(1))
    return {"S": None if s_out is None else round(s_out, 4), "S_partial": None if s is None else round(s, 4), "coverage": cov, "too_little_evidence": bool(s is not None and not shown and hard is None),
            "checks": {c.key: c.public() for c in checks}, "gate": gate.public(), "hard_limit": hard, "returns": returns,
            "judge_needed": bool((s_out is not None and s_out < v1.JUDGE_BELOW) or returns >= 2)}


# ------------------------------------------------------------------------------------------------ the person's data (in ~/.agent-console, never in the repo)
def state_dir() -> Path:
    return Path(os.environ.get("AGENT_CONSOLE_HOME", "~/.agent-console")).expanduser()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if isinstance(o, dict):
                out.append(o)
    except OSError:
        pass
    return out


def confirmed_deception(state: Path) -> set[str]:
    """run ids whose deception flag the person CONFIRMED (the latest decision per run wins; a dismissal removes it again)."""
    latest: dict[str, str] = {}
    for o in read_jsonl(state / "flag_decisions.jsonl"):
        if o.get("flag") == "deception" and o.get("run_id") and o.get("decision") in ("confirm", "dismiss"):
            latest[o["run_id"]] = o["decision"]
    return {r for r, d in latest.items() if d == "confirm"}


def read_scores_v2(path: Path) -> dict[str, dict[str, Any]]:
    """Latest v2 line per task id."""
    best: dict[str, dict[str, Any]] = {}
    for o in read_jsonl(path):
        if o.get("scorer_version") == SCORER_VERSION and "task_id" in o and (o["task_id"] not in best or o.get("rev", 0) >= best[o["task_id"]].get("rev", 0)):
            best[o["task_id"]] = o
    return best


def max_rev(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for o in read_jsonl(path):
        if "task_id" in o:
            out[o["task_id"]] = max(out.get(o["task_id"], 0), int(o.get("rev", 0)))
    return out


# ------------------------------------------------------------------------------------------------ run context
def is_finished(run: dict[str, Any], meta_finished: bool, now: datetime) -> bool:
    """A sub-agent run is finished when sub_meta.finished is set, or when no record has arrived for SCORE_SETTLE_S."""
    if meta_finished:
        return True
    end = run.get("end_ts")
    if not end:
        return False
    return (now - datetime.fromisoformat(end.replace("Z", "+00:00"))).total_seconds() >= SCORE_SETTLE_S


def needs_rescore(prev: dict[str, Any] | None, run: dict[str, Any], rescore: bool) -> bool:
    """Score again when there is no v2 line, when the run got a record after the last scoring, or when a first_pass is still pending."""
    if prev is None or rescore:
        return True
    if (run.get("end_ts") or "") > (prev.get("scored_at") or ""):
        return True
    return bool(((prev.get("checks") or {}).get("first_pass") or {}).get("pending"))


def git_change_set(repo: Path, cwd: str) -> set[str]:
    """Repo-relative paths changed on the branch checked out in `cwd` (against the project's trunk) plus uncommitted and untracked files.
    Empty when the directory is gone or is not a git checkout."""
    if not cwd or not Path(cwd).is_dir():
        return set()
    out: set[str] = set()
    trunk = projectmod.for_cwd(cwd).trunk
    a = v1._git(Path(cwd), "diff", "--name-only", f"{trunk}...HEAD") if trunk != "HEAD" else None
    b = v1._git(Path(cwd), "status", "--porcelain")
    if a:
        out |= {x for x in a.splitlines() if x}
    if b:
        out |= {ln[3:].strip().strip('"') for ln in b.splitlines() if len(ln) > 3}
    return {x.rstrip("/") for x in out}


def ticket_files(proj: projectmod.Project, key: str | None, cache: dict) -> set[str]:
    """Files that belong to a ticket in git: touched by a commit whose message names the key (any branch), or tracked on the trunk with the
    key in the file name (a change file `changes/<KEY>.md`). A ticket that was merged long ago is found this way."""
    if not key or proj.top is None:
        return set()
    ck = (str(proj.top), key)
    if ck in cache:
        return cache[ck]
    out: set[str] = set()
    log = v1._git(proj.top, "log", "--all", "-F", f"--grep={key}", "--name-only", "--pretty=format:")
    if log:
        out |= {x for x in log.splitlines() if x}
    tree = v1._git(proj.top, "ls-tree", "-r", "--name-only", proj.trunk)
    if tree:
        out |= {x for x in tree.splitlines() if key in x}
    cache[ck] = out
    return out


def repo_reference_ids(proj: projectmod.Project, rule_ids: set[str]) -> set[str]:
    """Rule ids that at least one test case or test references at the end of the ticket: the profile's test-case files and the test files
    on the trunk, plus the cases / drafts in a worktree that has not been merged yet (passed in by the caller)."""
    if proj.top is None or not rule_ids:
        return set()
    specs = [f":(glob){g}" for g in proj.case_globs + proj.test_globs]
    out = v1._git(proj.top, "grep", "-h", "-o", "-E", r"[A-Z][A-Z0-9]{1,7}(-[A-Z0-9]{1,10}){1,3}", proj.trunk, "--", *specs)
    return {i.split(":", 1)[-1] for i in (out or "").splitlines() if i.split(":", 1)[-1] in rule_ids}


def role_file_sha(repo: Path, ref: str | None, role: str, start: str, cache: dict) -> str | None:
    """git blob (7 chars) of the role file in the workbench as it was when the run started."""
    rel = layout.role_rel(repo, role)
    if rel is None:
        return None
    key = (role, start[:13])
    if key in cache:
        return cache[key]
    commit = v1._git(repo, "rev-list", "-1", f"--before={start}", ref or "HEAD", "--", rel)
    blob = v1._git(repo, "rev-parse", "--short=7", f"{commit.strip()}:{rel}") if commit and commit.strip() else None
    cache[key] = blob.strip() if blob else None
    return cache[key]


def step_label(description: str | None) -> str | None:
    """A short label from the spawn description: the leading [KEY] removed, 60 characters at most."""
    if not description:
        return None
    t = re.sub(r"^\s*\[[A-Z0-9-]+\]\s*", "", description.strip())
    t = re.sub(r"\s+", " ", t)
    return t[:60] or None


def referenced_ids(texts: list[str], rule_ids: set[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        out |= {i for i in v1.RULE_ID_RE.findall(t or "") if i in rule_ids}
    return out


def read_repo_file(cwd: str, rel: str) -> str:
    try:
        return (Path(cwd) / rel).read_text(errors="replace")
    except OSError:
        return ""


# ------------------------------------------------------------------------------------------------ the runner
def suite_results(parser_m: Any, path: Path) -> list[dict[str, Any]]:
    """Every pytest-class Bash call of a log with its result: {ts, error, summary}. Only the pytest summary line is kept, never other output."""
    pending: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    try:
        fh = open(path, "rb")
    except OSError:
        return out
    with fh:
        for raw in fh:
            if b'"tool_use"' not in raw and b'"tool_result"' not in raw:
                continue
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            c = (o.get("message") or {}).get("content")
            if not isinstance(c, list):
                continue
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") == "Bash":
                    cmd = str((b.get("input") or {}).get("command") or "")
                    if parser_m.classify_command(cmd) == "pytest" and not (b.get("input") or {}).get("run_in_background"):
                        pending[b["id"]] = o.get("timestamp") or ""
                elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                    ts = pending.pop(b["tool_use_id"])
                    body = b.get("content")
                    text = body if isinstance(body, str) else "\n".join(x.get("text", "") for x in body if isinstance(x, dict)) if isinstance(body, list) else ""
                    m = SUMMARY_RE.findall(text)
                    out.append({"ts": ts, "error": bool(b.get("is_error")) or bool(re.search(r"\b\d+ (?:failed|error)", m[-1] if m else "")), "summary": m[-1] if m else ""})
    return out


PROBE_RE = re.compile(r"not real work|trivial check-in|\b(?:model-check|denial|region|tool-restriction)\s+test\b|\btest control\b|reply with (?:exactly|the single word)", re.I)


def not_scorable_reason(description: str | None, prompt: str | None, ended_on_api_error: bool) -> tuple[str, str] | None:
    """(kind, reason) for a run that is not the role's work, or None. Kinds: `probe` (a setup test the person started: model access, tool denial,
    a check-in) and `api_error` (the log ends on an API error after its last text: the environment ended it, not the role).
    A probe is recognised ONLY from what the person wrote to start the run (the Agent call's description and prompt), never from the run's own
    reply: a role cannot make itself a probe by what it says."""
    if PROBE_RE.search(f"{description or ''}\n{(prompt or '')[:600]}"):
        return "probe", "probe run: a setup test, not the role's work"
    if ended_on_api_error:
        return "api_error", "run ended on an API error (environment, not the role)"
    return None


def run_scoring_v2(repo: Path, *, scores_path: Path, since: str | None = None, ticket: str | None = None, rescore: bool = False,
                   roles_ref: str | None = None, now: datetime | None = None, store: Any = None, state: Path | None = None,
                   judge_results: dict[str, float] | None = None, judge_calibrated: bool = False) -> dict[str, Any]:
    store_m, parser_m, redact_m, scope_m, queries_m = v1._console(repo)
    st = store or store_m.Store()
    if store is None:
        v1._refresh_index(st)
    state = state or state_dir()
    now = now or datetime.now(timezone.utc)
    roles = v1.load_roles(repo, roles_ref)
    ctx = v1.Ctx(repo, st, parser_m, scope_m, redact_m.Redactor(repo / ".gitleaks.toml"), roles, set())
    ids_cache: dict[str, tuple[set[str], set[str]]] = {}

    def project_ids(proj: projectmod.Project) -> tuple[set[str], set[str]]:
        """(rule ids of the map, ids referenced by its cases and tests), once per project."""
        k = str(proj.top)
        if k not in ids_cache:
            ids = ctx.rule_ids | known_rule_ids(proj.top)
            ids_cache[k] = (ids, repo_reference_ids(proj, ids))
        return ids_cache[k]
    key_files_cache: dict = {}
    db = st.reader()
    try:
        runs = [dict(r) for r in db.execute("SELECT r.*, coalesce(m.finished, 0) AS meta_finished FROM runs r LEFT JOIN sub_meta m ON m.run_id = r.run_id "
                                            "WHERE r.kind='sub' ORDER BY r.start_ts, r.run_id")]
        failed = {r["run_id"] for r in db.execute("SELECT run_id FROM flags WHERE flag='spawn_failure'")}
        flag_names: dict[str, list[str]] = defaultdict(list)
        for r in db.execute("SELECT run_id, flag FROM flags"):
            flag_names[r["run_id"]].append(r["flag"])
        first_ctx: dict[str, int] = {}      # first call of each run; one pass, the earliest timestamp wins
        for r in db.execute("SELECT run_id, ts, input + cache_read + cache_w5m + cache_w1h AS ctx FROM usage ORDER BY run_id, ts"):
            first_ctx.setdefault(r["run_id"], r["ctx"])
        write_ts = defaultdict(list)
        for r in db.execute("SELECT run_id, ts FROM tool_calls WHERE name IN ('Edit','Write','Bash-write') ORDER BY ts"):
            write_ts[r["run_id"]].append(r["ts"])
    finally:
        db.close()
    for r in runs:
        r["flag_names"] = flag_names.get(r["run_id"], [])
    prev_all = read_scores_v2(scores_path)
    revs = max_rev(scores_path)
    confirmed = confirmed_deception(state)
    verdicts_cache: dict[str, str | None] = {}
    evidence_cache: dict[str, v1.Evidence] = {}
    by_type: dict[str, list[dict[str, Any]]] = {}
    by_ticket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in runs:
        by_type.setdefault(r["role"], []).append(r)
        key = r.get("ticket_eff") or r["ticket"]
        if key:
            by_ticket[key].append(r)
    defects = read_jsonl(state / "defects.jsonl")
    sha_cache: dict = {}
    git_cache: dict[str, set[str]] = {}

    def reply_of(run_id: str) -> str | None:
        d = st.reader()
        try:
            f = d.execute("SELECT path, last_text_off FROM files WHERE run_id=?", (run_id,)).fetchone()
        finally:
            d.close()
        if not f or f["last_text_off"] is None:
            return None
        rec = parser_m.read_record(Path(f["path"]), f["last_text_off"]) or {}
        return v1.reply_text(parser_m, (rec.get("message") or {}).get("content"))

    def ended_on_error(run_id: str) -> bool:
        d = st.reader()
        try:
            return d.execute("SELECT 1 FROM errors e JOIN files f ON f.run_id = e.run_id WHERE e.run_id=? AND e.off > coalesce(f.last_text_off, -1) LIMIT 1", (run_id,)).fetchone() is not None
        finally:
            d.close()

    def gate_verdict(run: dict[str, Any]) -> str | None:
        if run["run_id"] not in verdicts_cache:
            verdicts_cache[run["run_id"]] = verdict_of(reply_of(run["run_id"]))
        return verdicts_cache[run["run_id"]]

    def evidence_of(run: dict[str, Any], role: str, generic_for: str | None = None) -> v1.Evidence:
        if run["run_id"] not in evidence_cache:
            evidence_cache[run["run_id"]] = v1.build_evidence(ctx, run, role, generic_for)
        return evidence_cache[run["run_id"]]

    def mention(run: dict[str, Any]) -> str | None:
        t = queries_m.show_text(st, run["run_id"], "description")
        p = queries_m.show_text(st, run["run_id"], "prompt")
        return v1.role_work_mention(set(roles), (t or {}).get("text") or "", (p or {}).get("text") or "")

    stats: Counter = Counter()

    def ticket_context(run: dict[str, Any]) -> Ticket:
        key = run.get("ticket_eff") or run["ticket"]
        rs = sorted(by_ticket.get(key, []), key=lambda r: (r["start_ts"], r["run_id"])) if key else []
        tk = Ticket(key, rs)
        for cwd in sorted({r["cwd"] for r in rs if r.get("cwd")} | ({run["cwd"]} if run.get("cwd") else set())):
            if cwd not in git_cache:
                git_cache[cwd] = git_change_set(repo, cwd)
            tk.git_files |= git_cache[cwd]
            tk.cwds.append(cwd)
        tk.project = projectmod.for_cwd(run.get("cwd") or (tk.cwds[0] if tk.cwds else None))
        proj = tk.project
        tk.git_files |= ticket_files(proj, key, key_files_cache)
        tk.read = lambda p, _c=tk.cwds[:1]: (read_repo_file(_c[0], p) if _c and (Path(_c[0]) / p).is_file()
                                              else ((v1._git(proj.top, "show", f"{proj.trunk}:{p}") or "") if proj.top else ""))
        return tk

    def outcome(role: str, run: dict[str, Any], ev: v1.Evidence, facts: v1.RoleFacts, tk: Ticket) -> Check:
        if role in TRACE_ROLES:
            texts = []
            change_text = ""
            for r in tk.runs:
                if r["role"] in ("test-designer", "automation-engineer", "builder", "qa-analyst"):
                    texts += [w.text for w in evidence_of(r, r["role"]).writes if w.text]
            for p in tk.git_files:
                if re.search(r"(^|/)(cases|drafts)/[^/]+\.ya?ml$|(^|/)tests?/.*test_[^/]*\.py$", p):
                    texts += [read_repo_file(c, p) for c in tk.cwds[:1]]
                if projectmod.glob_any(p, tk.project.change_globs):
                    change_text += read_repo_file(tk.cwds[0], p) if tk.cwds else ""
            for w in ev.writes:
                if projectmod.glob_any(w.path, tk.project.change_globs):
                    change_text += "\n" + w.text
            for p in tk.git_files:
                if projectmod.glob_any(p, tk.project.change_globs) and not change_text and tk.project.top:
                    show = v1._git(tk.project.top, "show", f"{tk.project.trunk}:{p}")
                    change_text += show or ""
            ids, ref_ids = project_ids(tk.project)
            return check_traceability(ev, tk, ids, referenced_ids(texts, ids) | ref_ids, change_text)
        if role == "requirements-reviewer":
            for r in tk.runs:
                if r["role"] in ("test-designer", "builder") and r["run_id"] not in tk.replies:
                    tk.replies[r["run_id"]] = reply_of(r["run_id"]) or ""
            return check_escapes_requirements(run, tk, verdict_of(ev.reply))
        if role in MUTATION_ROLES:
            return check_mutation(tk.key, state)
        if role == "builder":
            first_write = (write_ts.get(run["run_id"]) or [""])[0]
            suites = []
            for r in [run] + [x for x in tk.runs if x["role"] == "test-runner" and x["start_ts"] >= run["start_ts"]]:
                f = st.reader().execute("SELECT path FROM files WHERE run_id=?", (r["run_id"],)).fetchone()
                if f:
                    suites += [s for s in suite_results(parser_m, Path(f["path"])) if s["ts"] >= first_write]
            suites.sort(key=lambda s: s["ts"])
            return check_green_first_time(run, tk, suites)
        if role in GATE_ESCAPE_ROLES:
            return check_gate_escapes(role, run, verdict_of(ev.reply), defects, now, bool(defects))
        if role == "test-runner":
            f = st.reader().execute("SELECT path FROM files WHERE run_id=?", (run["run_id"],)).fetchone()
            sums = [s["summary"] for s in suite_results(parser_m, Path(f["path"])) if s["summary"]] if f else []
            return check_honest_report(ev.reply, sums)
        if role in CONSUMED_ROLES:
            return check_consumed(run, tk)
        return Check("outcome", None, omitted="no outcome check is defined for this role yet")

    def process(run: dict[str, Any]) -> dict[str, Any] | None:
        agent_type = run["role"]
        prev = prev_all.get(run["run_id"])
        if not needs_rescore(prev, run, rescore):
            stats["unchanged"] += 1
            return None
        generic_for = mention(run) if agent_type in v1.GENERIC_TYPES else None
        role = agent_type if agent_type in roles else generic_for
        ev = evidence_of(run, role or agent_type, generic_for)
        flags = sorted(ev.console_flags)
        fe: dict[str, Any] = dict(ev.console_flags)
        if ev.soft_secrets:
            flags = sorted(set(flags) | {"secret_suspected"})
            fe["secret_suspected"] = {"rules": sorted({r for r, _ in ev.soft_secrets}), "where": sorted({w for _, w in ev.soft_secrets})[:5],
                                      "note": "password-like literal (a test fixture or a doc example is common); a person checks"}
        sec_files = v1.secrets_file_edits(ev.writes)
        if sec_files:
            flags = sorted(set(flags) | {"secrets_file_edited"})
            fe["secrets_file_edited"] = {"paths": sec_files[:5], "count": len(sec_files)}
        dec = v1.deception(ev, lambda p: v1.repo_file_lines(ctx, p, run.get("cwd")))
        if dec:
            flags = sorted(set(flags) | {"deception"})
            fe["deception"] = {"suspected": True, "reasons": dec, "confirmed": run["run_id"] in confirmed}
        key = run.get("ticket_eff") or run["ticket"]
        same_role = [r for r in by_ticket.get(key, []) if r["role"] == run["role"]] if key else [run]
        round_ = 1 + sum(1 for r in same_role if (r["start_ts"], r["run_id"]) < (run["start_ts"], run["run_id"]))
        models = json.loads(run["models"] or "{}")
        d = st.reader()
        try:
            desc = queries_m.show_text(st, run["run_id"], "description")
        finally:
            d.close()
        line: dict[str, Any] = {"schema": 2, "scorer_version": SCORER_VERSION, "task_id": run["run_id"], "role": role or agent_type, "agent_type": agent_type, "ticket": run["ticket"],
                                "ticket_eff": key, "ticket_src": run["ticket_src"], "start": run["start_ts"], "end": run["end_ts"], "flags": flags, "flag_evidence": fe,
                                "round": round_, "step": step_label((desc or {}).get("text")), "input_tokens": first_ctx.get(run["run_id"]),
                                "model": max(models, key=models.get) if models else None,
                                "role_file_sha": role_file_sha(repo, roles_ref, role or agent_type, run["start_ts"] or "", sha_cache) if (role or agent_type) in roles else None}
        if run["run_id"] in failed and not run["rounds"]:
            line.update(S=None, scored=False, skipped="spawn_failure: the run died before any reply (environment, not the role)", judge_needed=False, checks={}, criteria={}, hard_limit=None, coverage=0.0)
        elif (skip_why := not_scorable_reason((desc or {}).get("text"), (queries_m.show_text(st, run["run_id"], "prompt") or {}).get("text"), ended_on_error(run["run_id"]))) and not ev.secrets:
            line.update(S=None, scored=False, skipped=skip_why[1], skip_kind=skip_why[0], judge_needed=False, checks={}, criteria={}, hard_limit=None, coverage=0.0)
            if skip_why[0] == "api_error" and "spawn_failure" not in line["flags"]:
                line["flags"] = sorted(set(line["flags"]) | {"spawn_failure"})
                line["flag_evidence"] = {**line["flag_evidence"], "spawn_failure": {"reason": "the run's log ends on an API error after its last text"}}
            stats["not_scorable_" + skip_why[0]] += 1
        elif role is None:
            if ev.secrets:
                line.update(S=0.0, scored=True, checks={}, criteria={}, coverage=0.0, judge_needed=True,
                            hard_limit={"limit": "secret", "detail": "; ".join(f"{a} in {b}" for a, b in ev.secrets[:5])})
            else:       # a skip line is written even without flags, so the next pass sees the run as done and does not read its log again
                line.update(S=None, scored=False, skipped="not a role task (generic or built-in agent)" + (": flags only" if flags else "; no flags"), judge_needed=False,
                            checks={}, criteria={}, hard_limit=None, coverage=0.0)
                stats["not_a_role_no_flags" if not flags else "flag_or_skip_line"] += 1
        elif generic_for:
            if ev.secrets:
                line.update(S=0.0, hard_limit={"limit": "secret", "detail": "; ".join(f"{a} in {b}" for a, b in ev.secrets[:5])})
            else:
                line.update(S=GENERIC_CAP, hard_limit={"limit": "generic_for_role", "detail": f"{agent_type} did the work of {generic_for}; S is the cap, checks not evaluated"})
            line.update(scored=True, checks={}, criteria={}, coverage=0.0, judge_needed=bool(ev.secrets), generic_for=generic_for)
        else:
            facts = roles[role]
            tk = ticket_context(run)
            role_writes = [w for r in tk.runs if r["role"] == role and r["run_id"] != run["run_id"] for w in evidence_of(r, role).writes]
            gate = delivered(ev, facts, tk, role_writes)
            verdicts = v1._verdicts_after(by_type, facts, run, gate_verdict)
            checks = [check_first_pass(facts, ev, verdicts), outcome(role, run, ev, facts, tk),
                      check_judge(run["run_id"], state, judge_calibrated, judge_results or {}), check_follows(ev, facts), check_grounded(ev, facts, project_ids(ev.project)[0])]
            sc = score_v2(checks, gate, secrets=ev.secrets, confirmed_deception=run["run_id"] in confirmed, out_of_scope="out_of_scope_edit" in ev.console_flags,
                          generic_for=None, agent_type=agent_type)
            line.update(scored=sc["S"] is not None, criteria=sc["checks"], **{k: sc[k] for k in ("S", "S_partial", "coverage", "too_little_evidence", "gate", "hard_limit", "judge_needed", "returns")},
                        checks=sc["checks"])
            if facts.stale:
                line["note"] = facts.stale
        if prev and {k: v for k, v in prev.items() if k not in ("scored_at", "rev", "ts")} == {k: v for k, v in line.items() if k not in ("scored_at", "rev", "ts")} \
                and (prev.get("scored_at") or "") >= (run.get("end_ts") or ""):
            stats["unchanged"] += 1       # same result, and the line is already newer than the run's last record
            return None
        line["scored_at"] = now.isoformat(timespec="seconds")
        line["ts"] = line["scored_at"]
        line["rev"] = revs.get(run["run_id"], 0) + 1
        stats["scored" if line.get("scored") else "flag_or_skip_line"] += 1
        return line

    new_lines: list[dict[str, Any]] = []
    for run in runs:
        selected = (not since or (run["start_ts"] or "") >= since) and (not ticket or (run.get("ticket_eff") or run["ticket"]) == ticket)
        if not selected or not (run["rounds"] or run["run_id"] in failed):
            continue
        if not is_finished(run, bool(run["meta_finished"]), now):
            stats["unsettled"] += 1
            continue
        line = process(run)
        if line:
            new_lines.append(line)
    if new_lines:
        scores_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(scores_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, ("".join(json.dumps(x, sort_keys=True, ensure_ascii=False) + "\n" for x in new_lines)).encode())
        finally:
            os.close(fd)
    return {"written": len(new_lines), "stats": dict(stats), "lines": new_lines}
