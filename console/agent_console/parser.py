"""Log parser: one Claude Code session file (main or subagent) -> small metadata events.

Main goal: read each JSONL file incrementally (resume from a byte offset) and keep only
metadata and counts. Prompt and tool text is NOT kept; the byte offset of the record is kept so
the text can be re-read (and redacted) on explicit request.
Does not: compute cost, flags or runs (index.py and flags.py do).
Example: events, new_off = parse_file(path, 0)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from . import config
from .tickets import KEY_RE as TICKET_RE, lead_key
WANTED_TYPES = {"assistant", "user", "system", "cost-state", "agent-setting"}
# Bash commands that write a file (best effort, labelled "from Bash command" in the UI).
_BASH_WRITE_RES = [
    re.compile(r"(?:^|[\s;&|])>>?\s*([~\w./\\-][^\s;&|><]*)"),
    re.compile(r"\btee\s+(?:-a\s+)?([~\w./\\-][^\s;&|><]*)"),
    re.compile(r"\bsed\s+-i(?:\s*'')?(?:\s+-e)?\s+(?:'[^']*'|\"[^\"]*\")\s+([~\w./\\-][^\s;&|><]*)"),
]
_BASH_WRITE_IGNORE = ("/dev/", "&1", "&2")   # /dev/null, /dev/tcp/host/port (a port probe), /dev/stderr ...

# ---- command CLASS of a Bash call. Only the class is ever kept, never the command (privacy rule, tested). ----
TEST_CLASSES = ("pytest", "ruff", "mypy", "frontend_test", "make_test")
_QUOTED = re.compile(r'''\'[^\']*\'|"(?:\\.|[^"\\])*"''')
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\b", re.S)
_SEGMENT = re.compile(r"&&|\|\||;|\||\n|\(|\)|`|\$\(")
_RUNNER = (r"(?:\w+=\S+\s+)*(?:(?:time|timeout\s+\d+)\s+)?"
           r"(?:(?:poetry|uv)\s+run\s+|(?:\S*python[\d.]*|\$\{?\w+\}?|\"\")\s+-m\s+|npx\s+|npm\s+(?:run\s+)?|pnpm\s+(?:run\s+)?|yarn\s+)?(?:\S*/)?")
_CLASS_RES = [
    ("pytest", re.compile(r"^" + _RUNNER + r"(?:pytest|py\.test)\b")),
    ("ruff", re.compile(r"^" + _RUNNER + r"ruff\b")),
    ("mypy", re.compile(r"^" + _RUNNER + r"mypy\b")),
    ("frontend_test", re.compile(r"^" + _RUNNER + r"(?:vitest|jest|playwright\s+test|test(?::[\w-]+)?|test-unit|test-e2e)\b")),
    ("make_test", re.compile(r"^(?:\w+=\S+\s+)*make\b.*\btest")),
]
_GIT_RE = re.compile(r"^(?:\w+=\S+\s+)*git\s")


VERDICT_RE = re.compile(r"(PASS|FAIL|BLOCKED|QUESTIONS)\b")


def first_line_verdict(text: str) -> str | None:
    """The kit roles' verdict word when the FIRST line of a reply is one (`FAIL`, `**BLOCKED**: why`), else None.
    Upper case only: prose that starts with "Failing tests" or "Passed" is not a verdict."""
    for line in text.splitlines():
        line = line.strip().lstrip("#*_` >").lstrip()
        if line:
            m = VERDICT_RE.match(line)
            return m.group(1) if m else None
    return None


def classify_command(cmd: str) -> str:
    """pytest | ruff | mypy | frontend_test | make_test | git | other. Quoted strings and heredoc bodies are blanked first, so a word
    inside a commit message or a here-document never classifies the call. A command with a test segment takes the (first) test class."""
    text = _HEREDOC.sub(" ", cmd or "")
    text = _QUOTED.sub('""', text)
    segs = [s.strip() for s in _SEGMENT.split(text) if s.strip()]
    for seg in segs:
        for name, rx in _CLASS_RES:
            if rx.search(seg):
                return name
    return "git" if any(_GIT_RE.search(s) for s in segs) else "other"


@dataclass
class FileInfo:
    path: Path
    kind: str  # "main" | "sub"
    project_dir: str
    session_id: str
    agent_id: str | None  # only for subagent files

    @property
    def run_id(self) -> str:
        return f"{self.session_id}:{self.agent_id}" if self.agent_id else self.session_id


def classify(path: Path) -> FileInfo | None:
    """Map a path under the log root to a FileInfo, or None if it is not a session file."""
    if path.suffix != ".jsonl":
        return None
    if path.parent.name == "subagents" and path.name.startswith("agent-"):
        return FileInfo(path, "sub", path.parent.parent.parent.name, path.parent.parent.name, path.stem[len("agent-"):])
    return FileInfo(path, "main", path.parent.name, path.stem, None)


@dataclass
class Event:
    kind: str  # message | tool_use | tool_result | api_error | ticket_hint | cost_state | record
    ts: str | None
    data: dict[str, Any] = field(default_factory=dict)
    off: int = 0


def error_category(status: Any, message: str, error_code: str | None = None) -> str:
    """Map an API error to a coarse category. Never keep the message text (it holds account ids)."""
    m = (message or "").lower()
    code = (error_code or "").lower()
    if status == 403 or "403" in m[:12]:
        return "aws_403"
    if "cloud_credential" in code or "credentials" in m or "sso" in m:
        return "credentials_expired"
    if "timed out" in m or "connection" in m or "enotfound" in m or "econn" in m:
        return "network"
    if "server_error" in code or (isinstance(status, int) and status >= 500):
        return "server_error"
    return "other"


def _plausible_path(p: str) -> bool:
    """A redirect target that looks like a file: has a directory or an extension (not `0`, `1`, `_`, `Notes` from a quoted string)."""
    return len(p) > 2 and ("/" in p or re.search(r"\.\w{1,6}$", p) is not None) and not re.fullmatch(r"[&\d_\-]+", p)


def _bash_write_paths(cmd: str) -> list[str]:
    out: list[str] = []
    for rx in _BASH_WRITE_RES:
        for m in rx.finditer(cmd):
            p = m.group(1).strip("'\"")
            if p and not p.startswith(_BASH_WRITE_IGNORE) and _plausible_path(p) and p not in out:
                out.append(p)
    return out


def handback_text(content: Any) -> str:
    """A subagent hands its report back through the SubagentHandback tool (`message`), not as a text block."""
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "SubagentHandback":
                m = (b.get("input") or {}).get("message")
                if isinstance(m, str):
                    out.append(m)
    return "\n".join(out)


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _usage(u: dict[str, Any]) -> dict[str, int]:
    cc = u.get("cache_creation") or {}
    w5 = int(cc.get("ephemeral_5m_input_tokens") or 0)
    w1 = int(cc.get("ephemeral_1h_input_tokens") or 0)
    wtot = int(u.get("cache_creation_input_tokens") or 0)
    if w5 + w1 == 0:
        w5 = wtot  # no split available: count as 5-minute writes
    return {
        "input": int(u.get("input_tokens") or 0),
        "output": int(u.get("output_tokens") or 0),
        "cache_read": int(u.get("cache_read_input_tokens") or 0),
        "cache_w5m": w5,
        "cache_w1h": w1,
    }


def events_from_record(o: dict[str, Any], off: int, st: dict[str, Any] | None = None) -> Iterator[Event]:
    """`st` carries what the NEXT record needs from the previous one: {"prev_ts": ts of the previous kept record}. With it a user prompt
    knows how long the session had been idle (a wait), and an assistant record knows how long the model took since its input."""
    st = st if st is not None else {}
    t = o.get("type")
    ts = o.get("timestamp")
    base = {"cwd": o.get("cwd"), "branch": o.get("gitBranch"), "session": o.get("sessionId")}
    yield Event("record", ts, base, off)
    if t == "agent-setting":   # the session was started with `--agent <role>`
        if isinstance(o.get("agentSetting"), str):
            yield Event("agent_setting", ts, {"agent": o["agentSetting"][:80]}, off)
        return
    if t == "cost-state":
        yield Event("cost_state", ts, {"total_cost_usd": o.get("totalCostUSD")}, off)
        return
    if t == "system":
        if o.get("subtype") == "api_error":
            err = o.get("error") or {}
            status = err.get("status") if isinstance(err, dict) else None
            msg = (err.get("message") if isinstance(err, dict) else str(err)) or ""
            yield Event("api_error", ts, {"category": error_category(status, msg), "status": status}, off)
            yield from _idle(st, ts, "error", off)
            if ts:
                st["prev_ts"] = ts
        return
    msg = o.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if t == "assistant":
        if o.get("isApiErrorMessage") or msg.get("model") == "<synthetic>":
            code = o.get("error") if isinstance(o.get("error"), str) else None
            if o.get("isApiErrorMessage"):
                yield Event("api_error", ts, {"category": error_category(o.get("apiErrorStatus"), "", code),
                                              "status": o.get("apiErrorStatus")}, off)
                yield from _idle(st, ts, "error", off)
                if ts:
                    st["prev_ts"] = ts
            return
        text = ""
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    text += b.get("text", "")
        text = (text + "\n" + handback_text(content)).strip()   # the handback message is the run's real final report
        yield Event("message", ts, {
            "msg_id": msg.get("id") or o.get("uuid"),
            "request_id": o.get("requestId"),
            "model": msg.get("model"),
            "requested_model": o.get("requestedModel"),
            "text_chars": len(text),
            "says_reject": 1 if "REJECT" in text[:300] else 0,
            "verdict": first_line_verdict(text),
            "has_text": 1 if text.strip() else 0,
            "gap_s": _gap(st.get("prev_ts"), ts),   # model time: from its input (prompt / tool result / earlier block) to this record
            **_usage(msg.get("usage") or {}),
        }, off)
        yield from _idle(st, ts, "assistant", off)
        if ts:
            st["prev_ts"] = ts
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    yield from _tool_use(b, ts, off)
    elif t == "user":
        ids: list[str] = []
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    ids.append(str(b.get("tool_use_id")))
                    yield Event("tool_result", ts, {"tool_use_id": b.get("tool_use_id"), "is_error": 1 if b.get("is_error") else 0,
                                                    "out_chars": _chars(b.get("content"))}, off)
        if ids and not o.get("isMeta"):
            yield from _idle(st, ts, "result", off, tool_ids=ids)
        if not o.get("isMeta") and not o.get("toolUseResult"):
            full = _text_of(content)
            text = full[:2000]
            m = TICKET_RE.search(text)
            origin = o.get("origin")
            kind = origin.get("kind") if isinstance(origin, dict) and isinstance(origin.get("kind"), str) else None
            yield Event("user_prompt", ts, {"ticket": m.group(0) if m else None, "lead": lead_key(text),
                                            "origin": kind, "prev_ts": st.get("prev_ts"), "chars": len(full)}, off)
            if not ids:
                yield from _idle(st, ts, "prompt", off, origin=kind)
        if ts and not o.get("isMeta"):
            st["prev_ts"] = ts


def _idle(st: dict[str, Any], ts: str | None, to: str, off: int, **extra: Any) -> Iterator[Event]:
    """A silent gap before this record, kept only when it is long (see config.IDLE_STORE_S). Lengths and ids only, never text."""
    g = _gap(st.get("prev_ts"), ts)
    if g > config.IDLE_STORE_S:
        yield Event("idle_gap", ts, {"prev_ts": st.get("prev_ts"), "to": to, "dur_s": g, **extra}, off)


def _chars(v: Any) -> int:
    """Length of a tool input or result, in characters. The text itself is never kept."""
    if isinstance(v, str):
        return len(v)
    if isinstance(v, list):
        return sum(_chars(x.get("text") if isinstance(x, dict) and "text" in x else x) for x in v)
    if isinstance(v, dict):
        return sum(_chars(x) for x in v.values())
    return len(str(v)) if v is not None else 0


def _gap(prev: str | None, ts: str | None) -> float:
    if not prev or not ts:
        return 0.0
    try:
        a = datetime.fromisoformat(prev.replace("Z", "+00:00"))
        b = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (b - a).total_seconds())


def _tool_use(b: dict[str, Any], ts: str | None, off: int) -> Iterator[Event]:
    name = b.get("name") or ""
    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
    d: dict[str, Any] = {"id": b.get("id"), "name": name, "path": None, "via_bash": 0,
                         "subagent_type": None, "spawn_model": None, "background": 0, "ticket": None, "ticket_src": None, "cmd_class": None,
                         "in_chars": _chars(inp)}
    if name == "Bash":
        d["cmd_class"] = classify_command(str(inp.get("command") or ""))   # the class only; the command is dropped here
        d["background"] = 1 if inp.get("run_in_background") else 0
    if name in ("Edit", "Write", "Read", "NotebookEdit"):
        d["path"] = inp.get("file_path") or inp.get("notebook_path")
    elif name in ("Agent", "Task"):
        d["subagent_type"] = inp.get("subagent_type")
        d["spawn_model"] = inp.get("model")
        d["background"] = 1 if inp.get("run_in_background") else 0
        desc = str(inp.get("description") or "")
        m = TICKET_RE.search(desc) or TICKET_RE.search(str(inp.get("prompt") or "")[:2000])
        d["ticket"] = m.group(0) if m else None
        d["ticket_src"] = "lead" if lead_key(desc) else "text"
        if lead_key(desc):
            d["ticket"] = lead_key(desc)
    if name == "Bash" and re.search(r"(?:^|[;&|(\n])\s*git\s", str(inp.get("command") or "")):
        keys = TICKET_RE.findall(str(inp.get("command")))
        if keys:  # only the key is kept, never the command
            d["ticket"], d["ticket_src"] = min(set(keys), key=lambda k: (-keys.count(k), k)), "git"
    yield Event("tool_use", ts, d, off)
    if name == "Bash":
        for p in _bash_write_paths(str(inp.get("command") or "")):
            yield Event("tool_use", ts, {**d, "id": f"{d['id']}#w:{p}", "name": "Bash-write", "path": p, "via_bash": 1, "cmd_class": None, "background": 0, "in_chars": 0}, off)


def parse_file(path: Path, start: int = 0, state: dict[str, Any] | None = None) -> tuple[list[Event], int]:
    """Parse complete lines from `start`. Returns (events, new_offset); a partial last line is left.
    `state` ({"prev_ts": ...}) is read and updated in place so a later chunk of the same file continues where this one stopped."""
    events: list[Event] = []
    st = state if state is not None else {}
    with open(path, "rb") as fh:
        fh.seek(start)
        off = start
        for raw in fh:
            if not raw.endswith(b"\n"):
                break  # partial line: leave it for the next pass
            line_off, off = off, off + len(raw)
            # Cheap skip of record types we ignore, before the costly json.loads. In user/assistant
            # records "type" comes after the big "message", so only the type-first records and the
            # attachment records (whose key comes right after isSidechain) can be told apart here.
            if raw.startswith(b'{"type":"'):
                if raw[9:raw.index(b'"', 9)].decode("ascii", "replace") not in WANTED_TYPES:
                    continue
            elif b'"attachment":' in raw[:250]:
                continue
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            events.extend(events_from_record(o, line_off, st))
    return events, off


def read_record(path: Path, off: int) -> dict[str, Any] | None:
    """Re-read one record by byte offset (for the explicit, redacted 'show' feature)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(off)
            return json.loads(fh.readline())
    except (OSError, ValueError):   # the file was removed or rewritten after it was indexed: no record, not a crash
        return None
