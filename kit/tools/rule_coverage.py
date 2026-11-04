#!/usr/bin/env python3
"""Rule-to-test coverage for a repo that keeps a requirements map.

Reads `docs/requirements/*.md` (rule blocks, see templates/requirements-area.md) and the
`# rule: <ID>` comments in the repo's test files.

Exit code 1 when a rule with status `confirmed` or `new` (in scope) has no test.
With --strict, also when a test points to an unknown or retired rule ID, when a status is invalid,
when an ID is duplicated, when a `confirmed`/`new` rule has no `scope`, or when a rule's `tests:` field names
a file that has no `# rule: <ID>` marker for it.
With --write-tests, first rewrites the `tests:` field of every rule in the map (only the rules of --scope, if given)
from the markers: sorted, comma-separated file paths, or `none`. Nobody edits that field by hand.
Stdlib only; runs on Python 3.9+.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

RULE_HEADING = re.compile(r"^###\s+([A-Z][A-Z0-9]*-\d{3,})\s*$")
FIELD = re.compile(r"^-\s+([a-z_]+):\s*(.*)$")
TEST_COMMENT = re.compile(r"#\s*rule:\s*([A-Z][A-Z0-9]*-\d{3,}(?:\s*,\s*[A-Z][A-Z0-9]*-\d{3,})*)")
ID = re.compile(r"[A-Z][A-Z0-9]*-\d{3,}")

STATUSES = ("observed", "confirmed", "new", "retired")
IN_SCOPE_STATUSES = ("confirmed", "new")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
NOT_AREA_FILES = {"QUESTIONS.md"}


def parse_tests_field(value: str) -> list[str]:
    """The paths named in a `tests:` field (`none` or empty means no paths)."""
    return [part.strip() for part in value.split(",") if part.strip() and part.strip().lower() != "none"]


def parse_map(repo: Path) -> dict[str, dict]:
    """rule ID -> {area, status, scope, tests, file}. A later duplicate ID is kept and reported."""
    rules: dict[str, dict] = {}
    duplicates: list[str] = []
    req_dir = repo / "docs" / "requirements"
    if not req_dir.is_dir():
        return rules
    for path in sorted(req_dir.glob("*.md")):
        if path.name in NOT_AREA_FILES:
            continue
        current: dict | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            heading = RULE_HEADING.match(line)
            if heading:
                rule_id = heading.group(1)
                if rule_id in rules:
                    duplicates.append(rule_id)
                current = {"area": path.stem, "status": "", "scope": "", "tests": "", "file": path.name}
                rules[rule_id] = current
                continue
            if current is None:
                continue
            field = FIELD.match(line)
            if field and field.group(1) in ("status", "scope", "tests"):
                current[field.group(1)] = field.group(2).strip()
    for rule_id in duplicates:
        rules[rule_id]["duplicate"] = True
    return rules


def find_tests(repo: Path) -> dict[str, list[str]]:
    """rule ID -> list of 'path:line' of the `# rule:` comments that name it."""
    found: dict[str, list[str]] = {}
    for path in repo.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(repo).parts):
            continue
        in_tests = "tests" in path.relative_to(repo).parts or path.name.startswith("test_")
        if not in_tests:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            match = TEST_COMMENT.search(line)
            if not match:
                continue
            for rule_id in ID.findall(match.group(1)):
                found.setdefault(rule_id, []).append(f"{path.relative_to(repo)}:{number}")
    return found


def tests_value(places: list[str]) -> str:
    """The `tests:` field value for the marker places ('path:line') of one rule."""
    files = sorted({place.rsplit(":", 1)[0] for place in places})
    return ", ".join(files) if files else "none"


def write_tests_fields(repo: Path, scope: str | None = None) -> list[str]:
    """Rewrite the `tests:` field of the rules in the map from the `# rule:` markers.

    Returns the IDs whose field changed. A rule without a `tests:` line gets one after its last field line.
    """
    rules = parse_map(repo)
    tests = find_tests(repo)
    changed: list[str] = []
    for path in sorted((repo / "docs" / "requirements").glob("*.md")):
        if path.name in NOT_AREA_FILES:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        out: list[str] = []
        index = 0
        dirty = False
        while index < len(lines):
            heading = RULE_HEADING.match(lines[index])
            if not heading:
                out.append(lines[index])
                index += 1
                continue
            rule_id = heading.group(1)
            end = index + 1
            while end < len(lines) and not RULE_HEADING.match(lines[end]) and lines[end].strip() != "---":
                end += 1
            block = lines[index:end]
            info = rules.get(rule_id, {})
            if info.get("scope") is not None and (scope is None or info.get("scope") == scope):
                wanted = f"- tests: {tests_value(tests.get(rule_id, []))}"
                for position, line in enumerate(block):
                    field = FIELD.match(line)
                    if field and field.group(1) == "tests":
                        if line != wanted:
                            block[position] = wanted
                            changed.append(rule_id)
                            dirty = True
                        break
                else:
                    last_field = max((n for n, line in enumerate(block) if FIELD.match(line)), default=0)
                    block.insert(last_field + 1, wanted)
                    changed.append(rule_id)
                    dirty = True
            out.extend(block)
            index = end
        if dirty:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def check(repo: Path, scope: str | None = None) -> dict:
    rules = parse_map(repo)
    tests = find_tests(repo)

    counts: dict[str, Counter] = {}
    for info in rules.values():
        counts.setdefault(info["area"], Counter())[info["status"] or "no-status"] += 1

    def in_scope(info: dict) -> bool:
        return info["status"] in IN_SCOPE_STATUSES and (scope is None or info["scope"] == scope)

    missing = sorted(rule_id for rule_id, info in rules.items() if in_scope(info) and rule_id not in tests)
    unknown = sorted(
        (rule_id, places) for rule_id, places in tests.items() if rule_id not in rules
    )
    on_retired = sorted(
        (rule_id, places) for rule_id, places in tests.items()
        if rule_id in rules and rules[rule_id]["status"] == "retired"
    )
    no_scope = sorted(
        rule_id for rule_id, info in rules.items()
        if info["status"] in IN_SCOPE_STATUSES and not info["scope"] and rule_id
    )
    bad_status = sorted(
        rule_id for rule_id, info in rules.items() if info["status"] not in STATUSES
    )
    duplicates = sorted(rule_id for rule_id, info in rules.items() if info.get("duplicate"))
    retired = sorted(rule_id for rule_id, info in rules.items() if info["status"] == "retired")
    outdated = []
    unproven_paths = []
    for rule_id, info in sorted(rules.items()):
        claimed = set(parse_tests_field(info["tests"]))
        marked = {place.rsplit(":", 1)[0] for place in tests.get(rule_id, [])}
        if claimed != marked:
            outdated.append(rule_id)
        for claimed_path in sorted(claimed - marked):
            unproven_paths.append((rule_id, claimed_path))
    return {
        "rules": rules, "counts": counts, "missing": missing, "unknown": unknown,
        "on_retired": on_retired, "no_scope": no_scope, "bad_status": bad_status, "duplicates": duplicates, "retired": retired,
        "outdated": outdated, "unproven_paths": unproven_paths,
    }


def render(result: dict, scope: str | None) -> str:
    out: list[str] = []
    out.append(f"Rules: {len(result['rules'])}" + (f" (scope filter: {scope})" if scope else ""))
    for area, counter in sorted(result["counts"].items()):
        parts = ", ".join(f"{name}={counter[name]}" for name in (*STATUSES, "no-status") if counter[name])
        out.append(f"  {area}: {parts}")
    if result["missing"]:
        out.append("Rules in scope (confirmed/new) WITHOUT a test:")
        out.extend(f"  {rule_id}" for rule_id in result["missing"])
    if result["unknown"]:
        out.append("Tests pointing to UNKNOWN rule IDs:")
        out.extend(f"  {rule_id}  {', '.join(places)}" for rule_id, places in result["unknown"])
    if result["on_retired"]:
        out.append("Tests pointing to RETIRED rules:")
        out.extend(f"  {rule_id}  {', '.join(places)}" for rule_id, places in result["on_retired"])
    if result["retired"]:
        out.append(f"Retired rules: {', '.join(result['retired'])}")
    if result["no_scope"]:
        out.append("Rules (confirmed/new) WITHOUT a scope:")
        out.extend(f"  {rule_id}" for rule_id in result["no_scope"])
    if result["bad_status"]:
        out.append("Rules with a missing or invalid status:")
        out.extend(f"  {rule_id}" for rule_id in result["bad_status"])
    if result["duplicates"]:
        out.append("Duplicate rule IDs:")
        out.extend(f"  {rule_id}" for rule_id in result["duplicates"])
    if result["unproven_paths"]:
        out.append("`tests:` field names a file with no `# rule:` marker for the rule:")
        out.extend(f"  {rule_id}  {path}" for rule_id, path in result["unproven_paths"])
    if result["outdated"]:
        out.append(f"`tests:` field differs from the markers in {len(result['outdated'])} rule(s); run --write-tests")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rules in docs/requirements vs '# rule: <ID>' comments in tests.")
    parser.add_argument("repo", type=Path, help="repo root")
    parser.add_argument("--scope", help="only rules whose `scope` field equals this value (e.g. 6.3)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail on tests with unknown/retired IDs, invalid statuses, duplicate IDs, "
                             "confirmed/new rules without a scope, and `tests:` paths with no marker")
    parser.add_argument("--write-tests", action="store_true",
                        help="first rewrite the `tests:` field of the rules (of --scope, if given) from the "
                             "`# rule:` markers")
    args = parser.parse_args(argv)

    if not (args.repo / "docs" / "requirements").is_dir():
        print(f"No docs/requirements in {args.repo}", file=sys.stderr)
        return 2

    if args.write_tests:
        changed = write_tests_fields(args.repo, args.scope)
        print(f"tests: field written for {len(changed)} rule(s)" + (f": {', '.join(changed)}" if changed else ""))
    result = check(args.repo, args.scope)
    print(render(result, args.scope))

    failed = bool(result["missing"])
    if args.strict:
        failed = failed or bool(
            result["unknown"] or result["on_retired"] or result["no_scope"]
            or result["bad_status"] or result["duplicates"] or result["unproven_paths"]
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
