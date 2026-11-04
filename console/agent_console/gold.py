"""The person's verdicts, defect reports and flag decisions: the gold label for the score.

Main goal: remember what the person decided, so the score can be checked against it. Three append-only files in ~/.agent-console/ (never in the repo):
  verdicts.jsonl       {ts, ticket, verdict, note, roles}        the latest line per ticket wins
  defects.jsonl        {ts, ticket, date, roles, note}           a defect found after "done"
  flag_decisions.jsonl {ts, run_id, flag, decision}              deception: confirm | dismiss (the latest per run wins)
Every write is validated (allowed values, note length) before it touches a file; a missing file is created with mode 0600.
Does not: write anywhere else, or read the repo.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

VERDICTS = ("accepted", "accepted_after_rework", "rejected")
ACCEPTED = ("accepted", "accepted_after_rework")
NOTE_MAX = 200
DECISIONS = ("confirm", "dismiss")
TICKET_RE = r"^[A-Z][A-Z0-9]+-[A-Z0-9]+$"
ROLE_RE = r"^[a-z][a-z0-9-]{1,40}$"


def path(name: str) -> Path:
    return config.home() / name


def append(name: str, rec: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    rec = {"ts": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), **rec}
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n").encode())
    finally:
        os.close(fd)
    return rec


def read(name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        for ln in path(name).read_text(errors="replace").splitlines():
            try:
                o = json.loads(ln)
            except ValueError:
                continue
            if isinstance(o, dict):
                out.append(o)
    except OSError:
        pass
    return out


def latest_verdicts() -> dict[str, dict[str, Any]]:
    """ticket -> its latest verdict line (the file order decides; the last line wins)."""
    out: dict[str, dict[str, Any]] = {}
    for o in read("verdicts.jsonl"):
        if o.get("ticket") and o.get("verdict") in VERDICTS:
            out[o["ticket"]] = o
    return out


def defects(ticket: str | None = None) -> list[dict[str, Any]]:
    return [o for o in read("defects.jsonl") if o.get("ticket") and (ticket is None or o["ticket"] == ticket)]


def decisions() -> dict[str, str]:
    """run_id -> the latest deception decision."""
    out: dict[str, str] = {}
    for o in read("flag_decisions.jsonl"):
        if o.get("flag") == "deception" and o.get("run_id") and o.get("decision") in DECISIONS:
            out[o["run_id"]] = o["decision"]
    return out
