#!/usr/bin/env python3
"""Show and switch which model each tier (opus / sonnet / haiku) runs, in the user settings of Claude Code.

Main goal: a model switch is always a person's decision. `show` only reads and runs anywhere. A switch (`use`, `set`) refuses to
run without an interactive terminal, has no --yes flag, shows the change before it makes it, and asks you to type `yes`.
Does: reads `env.ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL` and the main-session `model` from ~/.claude/settings.json and shows
them with the tier each role file asks for. Switches: `use no-opus` (the opus tier runs the sonnet tier's model, for an account
where opus is not enabled), `use sonnet-only` (every tier runs the sonnet tier's model), `use restore` (the mapping saved before the
last switch), `set <opus|sonnet|haiku> <model id>`, `set main <model or alias>`. Backs settings.json up before every write; keeps
every other key as it was.
Does not: print account values (AWS profile, region) or any secret; call a model; change a role file.
Example: python3 tools/ai_models.py show
         python3 tools/ai_models.py use no-opus
Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

TIERS = ("opus", "sonnet", "haiku")
VAR = {t: f"ANTHROPIC_DEFAULT_{t.upper()}_MODEL" for t in TIERS}
ROOT = Path(__file__).resolve().parents[1]


def settings_path(a: argparse.Namespace) -> Path:
    return Path(a.settings or os.environ.get("AI_MODELS_SETTINGS") or "~/.claude/settings.json").expanduser()


def state_dir(settings: Path) -> Path:
    return settings.parent / "backups" / "ai_models"


def load(p: Path) -> dict:
    return json.loads(p.read_text()) if p.is_file() else {}


def mapping(s: dict) -> dict[str, str | None]:
    env = s.get("env") or {}
    out: dict[str, str | None] = {t: env.get(VAR[t]) for t in TIERS}
    out["main"] = s.get("model")
    return out


def role_tiers() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {t: [] for t in TIERS}
    for d in ("roles-22/agents", "kit/agents"):
        for f in sorted((ROOT / d).glob("*.md")):
            m = re.search(r"^model:\s*(\w+)", f.read_text(), re.M)
            if m and m.group(1) in out:
                out[m.group(1)].append(f.stem)
    return out


def show(s: dict) -> None:
    m = mapping(s)
    env = s.get("env") or {}
    print("Provider: " + ("Bedrock (CLAUDE_CODE_USE_BEDROCK set)" if env.get("CLAUDE_CODE_USE_BEDROCK") else "Anthropic API (CLAUDE_CODE_USE_BEDROCK not set)"))
    print(f"Main session model: {m['main'] or '(not set: Claude Code default)'}")
    tiers = role_tiers()
    for t in TIERS:
        print(f"  {t:6} -> {m[t] or '(not set: the provider default for ' + t + ')'}   roles: {len(tiers[t])}")


def plan(s: dict, cmd: str, args: list[str], saved: dict | None) -> dict[str, str | None]:
    cur = mapping(s)
    new = dict(cur)
    if cmd == "use":
        preset = args[0]
        if preset in ("no-opus", "sonnet-only"):
            if not cur["sonnet"]:
                raise SystemExit("The sonnet tier has no model id set; set it first: set sonnet <model id>")
            new["opus"] = cur["sonnet"]
            if preset == "sonnet-only":
                new["haiku"] = cur["sonnet"]
        elif preset == "restore":
            if not saved:
                raise SystemExit("Nothing to restore: no mapping was saved by an earlier switch.")
            new = {k: saved.get(k) for k in (*TIERS, "main")}
        else:
            raise SystemExit(f"Unknown preset {preset!r}: no-opus, sonnet-only, restore")
    elif cmd == "set":
        what, value = args[0], args[1]
        if what not in (*TIERS, "main"):
            raise SystemExit(f"Unknown tier {what!r}: opus, sonnet, haiku, main")
        if not re.fullmatch(r"[\w.:/@\[\]-]{2,200}", value):
            raise SystemExit("That does not look like a model id.")
        new[what] = value
    return new


def apply(s: dict, new: dict[str, str | None]) -> dict:
    out = json.loads(json.dumps(s))
    env = out.setdefault("env", {})
    for t in TIERS:
        if new[t]:
            env[VAR[t]] = new[t]
        else:
            env.pop(VAR[t], None)
    if new["main"]:
        out["model"] = new["main"]
    else:
        out.pop("model", None)
    return out


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--settings", help="settings file (default ~/.claude/settings.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="show the current mapping")
    u = sub.add_parser("use", help="switch with a preset")
    u.add_argument("preset", choices=("no-opus", "sonnet-only", "restore"))
    st = sub.add_parser("set", help="set one tier (or the main session) to a model id")
    st.add_argument("what", choices=(*TIERS, "main"))
    st.add_argument("value")
    a = ap.parse_args(argv)
    p = settings_path(a)
    if a.cmd == "show":
        show(load(p))
        return 0
    if not interactive():
        print("ai_models.py: refusing to switch: no interactive terminal. A model switch needs a person; run it yourself in a terminal.", file=sys.stderr)
        return 2
    s = load(p)
    sd = state_dir(p)
    saved_file = sd / "last-mapping.json"
    saved = json.loads(saved_file.read_text()) if saved_file.is_file() else None
    args = [a.preset] if a.cmd == "use" else [a.what, a.value]
    new = plan(s, a.cmd, args, saved)
    cur = mapping(s)
    if new == cur:
        print("No change: the mapping is already like that.")
        return 0
    print(f"Settings: {p}")
    for k in (*TIERS, "main"):
        if new[k] != cur[k]:
            print(f"  {k:6}: {cur[k] or '(not set)'}  ->  {new[k] or '(not set)'}")
    if input("Type yes to write this: ").strip() != "yes":
        print("Nothing written.")
        return 1
    sd.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if p.is_file():
        shutil.copy2(p, sd / f"settings.json.{stamp}")
    if a.cmd != "use" or a.preset != "restore":
        saved_file.write_text(json.dumps(cur, indent=2) + "\n")
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(apply(s, new), indent=2) + "\n")
    os.replace(tmp, p)
    print(f"Written. Backup: {sd / f'settings.json.{stamp}'}. Start a new Claude Code session for it to take effect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
