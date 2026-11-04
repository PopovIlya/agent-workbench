#!/usr/bin/env python3
"""Lint the workbench's role files: the 22 roles, the six kit roles, the shared rules and the playbook.

Main goal: a role file holds only the way of working, and every file it points to exists.
Does: checks per role file that the frontmatter has name (= the file name), description, tools and a model tier (opus / sonnet / haiku);
that no role text holds an absolute path, a host name, an e-mail address or a ticket key other than the placeholders; that every
`<workbench>/...` and `templates/...` path it names exists; that every role file carries the workbench resolver line of
tools/resolve-workbench.line verbatim, and none still asks for `kit_path` or `<workbench_path>`; that every role has a criteria file
whose `(blob ...)` matches the role file. Optional: AGENT_WORKBENCH_DENYLIST names a local file (outside the repo) with one forbidden word per line, for example the
names of projects or organisations that must never appear.
Does not: change any file, unless you pass --refresh-hashes (then it rewrites the `(blob ...)` of each criteria file).
Example: python3 tools/lint_roles.py            (exit 1 on any error)
         python3 tools/lint_roles.py --refresh-hashes
Stdlib only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess  # nosec B404 - `git hash-object`, fixed argv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE_DIRS = (("roles-22/agents", "roles-22/criteria"), ("kit/agents", "kit/criteria"))
TEXT_FILES = ("roles-22/SHARED-RULES.md", "kit/PLAYBOOK.md")
TIERS = {"opus", "sonnet", "haiku"}
REQUIRED = ("name", "description", "tools", "model")

ABS_PATH = re.compile(r"(?<![\w<{$.-])(?:/Users/|/home/|/opt/|/var/|/etc/|~/|[A-Z]:\\)")
HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|dev|internal|corp|local|cloud|app)\b", re.I)
HOST_OK = re.compile(r"(?:^|\.)(?:example\.(?:com|org|net|internal|test)|docs\.gitlab\.com)$", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
KEY = re.compile(r"(?<![\w-])[A-Z][A-Z0-9]{1,9}-\d{1,6}\b")
KEY_OK = re.compile(r"^(?:PROJ|ABC|CART|ORD)-\d+$")
NOT_KEYS = re.compile(r"^(?:UTF|ISO|SHA|AES|RFC|PEP|CVE|HTTP|TLS|SSL|RSA|CWE|ASVS|OWASP)-")
REF = re.compile(r"<workbench>/([\w./-]+)|(?<![\w/<.-])(templates/[\w./-]+\.md)")
RESOLVER = "tools/resolve-workbench.line"


def frontmatter(text: str) -> dict[str, str] | None:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    out = {}
    for ln in m.group(1).splitlines():
        k, sep, v = ln.partition(":")
        if sep:
            out[k.strip()] = v.strip()
    return out


def blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()[:7]


def denylist() -> list[str]:
    p = os.environ.get("AGENT_WORKBENCH_DENYLIST")
    if not p or not Path(p).expanduser().is_file():
        return []
    return [w.strip().lower() for w in Path(p).expanduser().read_text().splitlines() if w.strip() and not w.startswith("#")]


def check_text(rel: str, text: str, deny: list[str], errors: list[str]) -> None:
    if (ROOT / RESOLVER).is_file():
        text = text.replace((ROOT / RESOLVER).read_text().strip(), "<resolver line>")   # the canonical line is checked on its own
    body = re.sub(r"```.*?```", lambda m: m.group(0) if "/Users/" in m.group(0) or "~/" in m.group(0) else "", text, flags=re.S)
    for i, ln in enumerate(body.splitlines(), 1):
        if ABS_PATH.search(ln):
            errors.append(f"{rel}:{i}: absolute path ({ABS_PATH.search(ln).group(0)}...); use a profile field or <workbench>")
        for h in HOST.findall(ln):
            if not HOST_OK.search(h) and not re.fullmatch(r"[\w-]+\.(?:md|py|sh|yaml|yml|json|toml|txt)", h, re.I):
                errors.append(f"{rel}:{i}: host name {h}")
        if EMAIL.search(ln):
            errors.append(f"{rel}:{i}: e-mail address")
        for k in KEY.findall(ln):
            if not KEY_OK.match(k) and not NOT_KEYS.match(k):
                errors.append(f"{rel}:{i}: ticket key {k}; use PROJ-123 or <KEY>")
        low = ln.lower()
        for w in deny:
            if w in low:
                errors.append(f"{rel}:{i}: a word from the deny list")
    for m in REF.finditer(text):
        target = m.group(1) or m.group(2)
        target = target.rstrip(".,;:)")
        if "<" in target or "*" in target:
            continue
        if not (ROOT / target).exists():
            errors.append(f"{rel}: names {target}, which does not exist in the workbench")


def run(refresh: bool = False) -> list[str]:
    errors: list[str] = []
    deny = denylist()
    for adir, cdir in ROLE_DIRS:
        for f in sorted((ROOT / adir).glob("*.md")):
            rel = f.relative_to(ROOT).as_posix()
            text = f.read_text()
            fm = frontmatter(text)
            if fm is None:
                errors.append(f"{rel}: no frontmatter")
                continue
            for k in REQUIRED:
                if not fm.get(k):
                    errors.append(f"{rel}: frontmatter field '{k}' missing")
            if fm.get("name") and fm["name"] != f.stem:
                errors.append(f"{rel}: name '{fm['name']}' is not the file name")
            if fm.get("model") and fm["model"] not in TIERS:
                errors.append(f"{rel}: model '{fm['model']}' is not one of {', '.join(sorted(TIERS))}")
            check_text(rel, text, deny, errors)
            line = (ROOT / RESOLVER).read_text().strip() if (ROOT / RESOLVER).is_file() else None
            if line is None or line not in text:
                errors.append(f"{rel}: does not carry the workbench resolver line of {RESOLVER} verbatim")
            if "<workbench_path>" in text or re.search(r"`kit_path`|<kit_path>", text):
                errors.append(f"{rel}: still asks for kit_path / workbench_path; use the resolver line and <workbench>")
            crit = ROOT / cdir / f.name
            if not crit.is_file():
                errors.append(f"{rel}: no criteria file {cdir}/{f.name}")
                continue
            want = blob(f)
            ctext = crit.read_text()
            m = re.search(r"\(blob ([0-9a-f]{7})\)", ctext)
            if refresh and (not m or m.group(1) != want):
                crit.write_text(re.sub(r"\(blob [0-9a-f]{7}\)", f"(blob {want})", ctext, count=1) if m else ctext)
                print(f"refreshed {crit.relative_to(ROOT)} -> blob {want}")
            elif not m:
                errors.append(f"{cdir}/{f.name}: no '(blob ...)' line")
            elif m.group(1) != want:
                errors.append(f"{cdir}/{f.name}: blob {m.group(1)} is stale (role file is {want}); check the criteria, then run --refresh-hashes")
    for rel in TEXT_FILES:
        check_text(rel, (ROOT / rel).read_text(), deny, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--refresh-hashes", action="store_true", help="rewrite each criteria file's (blob ...) from its role file")
    a = ap.parse_args(argv)
    errors = run(a.refresh_hashes)
    for e in errors:
        print(e)
    n = len(list((ROOT / "roles-22/agents").glob("*.md"))) + len(list((ROOT / "kit/agents").glob("*.md")))
    print(f"lint_roles: {n} role files, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
