#!/usr/bin/env python3
"""Add or remove the workbench's SessionStart hook and its read access in a Claude Code settings file, by merging.

Main goal: install.sh and uninstall.sh change only our own entry; every other key and hook stays as it was.
Does: `add <command>` appends {"type": "command", "command": <command>} to hooks.SessionStart unless an entry with that command
exists; `remove <path>` drops every hook whose command contains <path> (and empty groups left behind); `add-dir <path>` adds
<path> to permissions.additionalDirectories (so sessions in any repo may read the workbench's roles, playbook and templates);
`remove-dir <path>` takes it out again; `set-env <name> <value>` sets env.<name> (a different value already there is left alone and
reported, exit 1); `unset-env <name> <value>` removes env.<name> only while it still has that value; `get <key>` prints a
top-level value (empty when unset); `set-int <key> <n>` sets a top-level integer. Backs the file up to
<settings dir>/backups/settings.json.<time> before any change. Prints what it did. No change = no write, no backup.
Example: python3 tools/settings_hooks.py --settings ~/.claude/settings.json add '"/x/agent-workbench/hooks/session-start.sh"'
Stdlib only; Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path


def load(p: Path) -> dict:
    if not p.is_file() or not p.read_text().strip():
        return {}
    return json.loads(p.read_text())


def save(p: Path, data: dict) -> Path | None:
    backup = None
    if p.is_file():
        bdir = p.parent / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        backup = bdir / f"settings.json.{time.strftime('%Y%m%d-%H%M%S')}.{os.getpid()}"
        shutil.copy2(p, backup)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, p)
    return backup


def add(data: dict, command: str) -> bool:
    groups = data.setdefault("hooks", {}).setdefault("SessionStart", [])
    for g in groups:
        for h in g.get("hooks", []):
            if h.get("command") == command:
                return False
    groups.append({"hooks": [{"type": "command", "command": command}]})
    return True


def remove(data: dict, needle: str) -> int:
    hooks = data.get("hooks") or {}
    n = 0
    for event in list(hooks):
        kept = []
        for g in hooks[event]:
            hs = [h for h in g.get("hooks", []) if needle not in str(h.get("command", ""))]
            n += len(g.get("hooks", [])) - len(hs)
            if hs:
                kept.append({**g, "hooks": hs})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if "hooks" in data and not data["hooks"]:
        del data["hooks"]
    return n


def add_dir(data: dict, path: str) -> bool:
    dirs = data.setdefault("permissions", {}).setdefault("additionalDirectories", [])
    if path in dirs:
        return False
    dirs.append(path)
    return True


def remove_dir(data: dict, path: str) -> bool:
    perms = data.get("permissions") or {}
    dirs = perms.get("additionalDirectories") or []
    if path not in dirs:
        return False
    perms["additionalDirectories"] = [d for d in dirs if d != path]
    if not perms["additionalDirectories"]:
        del perms["additionalDirectories"]
    if not perms:
        del data["permissions"]
    return True


def set_env(data: dict, name: str, value: str) -> str:
    env = data.setdefault("env", {})
    cur = env.get(name)
    if cur == value:
        return "unchanged"
    if cur is not None:
        return "foreign"
    env[name] = value
    return "added"


def unset_env(data: dict, name: str, value: str) -> bool:
    env = data.get("env") or {}
    if env.get(name) != value:
        return False
    del env[name]
    if not env:
        data.pop("env", None)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--settings", default="~/.claude/settings.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("command")
    sub.add_parser("remove").add_argument("needle")
    sub.add_parser("add-dir").add_argument("path")
    sub.add_parser("remove-dir").add_argument("path")
    sub.add_parser("get").add_argument("key")
    si = sub.add_parser("set-int")
    si.add_argument("key")
    si.add_argument("value", type=int)
    for name in ("set-env", "unset-env"):
        sp = sub.add_parser(name)
        sp.add_argument("name")
        sp.add_argument("value")
    a = ap.parse_args(argv)
    p = Path(a.settings).expanduser()
    try:
        data = load(p)
    except ValueError:
        print(f"settings_hooks: {p} is not valid JSON; nothing changed", file=sys.stderr)
        return 1
    if a.cmd == "get":
        v = data.get(a.key)
        print("" if v is None else v)
        return 0
    if a.cmd == "set-int":
        if data.get(a.key) == a.value:
            print(f"{a.key}: unchanged ({a.value})")
            return 0
        data[a.key] = a.value
        b = save(p, data)
        print(f"{a.key}: set to {a.value} in {p}" + (f" (backup {b})" if b else ""))
        return 0
    if a.cmd == "set-env":
        r = set_env(data, a.name, a.value)
        if r == "unchanged":
            print(f"env {a.name}: unchanged")
            return 0
        if r == "foreign":
            print(f"env {a.name}: SKIPPED, it already points elsewhere ({data['env'][a.name]}); not ours, left alone")
            return 1
        b = save(p, data)
        print(f"env {a.name}: set in {p}" + (f" (backup {b})" if b else ""))
        return 0
    if a.cmd == "unset-env":
        if not unset_env(data, a.name, a.value):
            print(f"env {a.name}: none of ours in {p}")
            return 0
        b = save(p, data)
        print(f"env {a.name}: removed from {p}" + (f" (backup {b})" if b else ""))
        return 0
    if a.cmd in ("add-dir", "remove-dir"):
        changed = add_dir(data, a.path) if a.cmd == "add-dir" else remove_dir(data, a.path)
        if not changed:
            print(f"read access: unchanged ({a.path} {'already' if a.cmd == 'add-dir' else 'not'} in permissions.additionalDirectories)")
            return 0
        b = save(p, data)
        print(f"read access: {'added' if a.cmd == 'add-dir' else 'removed'} {a.path} {'to' if a.cmd == 'add-dir' else 'from'} permissions.additionalDirectories" + (f" (backup {b})" if b else ""))
        return 0
    if a.cmd == "add":
        if not add(data, a.command):
            print(f"hook: unchanged (already in {p})")
            return 0
        b = save(p, data)
        print(f"hook: added SessionStart to {p}" + (f" (backup {b})" if b else ""))
    else:
        n = remove(data, a.needle)
        if not n:
            print(f"hook: none of ours in {p}")
            return 0
        b = save(p, data)
        print(f"hook: removed {n} SessionStart entr{'y' if n == 1 else 'ies'} from {p}" + (f" (backup {b})" if b else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
