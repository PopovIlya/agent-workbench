"""Redaction of prompt/tool text before it is shown (only on explicit 'show').

Main goal: never show a secret from a session log.
Does: applies the repo's own rules from .gitleaks.toml (custom rules, with their secretGroup) plus a
built-in list reproducing the most common default gitleaks rules. Replaces the secret with [REDACTED:<rule>].
Does not: reproduce all ~160 default gitleaks rules (the page says so). Unknown formats can slip through,
which is why text is shown only on request and truncated.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

BUILTIN: list[tuple[str, str, int]] = [
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", 0),
    ("aws-access-key", r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b", 0),
    ("aws-secret", r"(?i)aws_secret_access_key[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9/+=]{30,})", 1),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*", 0),
    ("bearer", r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{16,})", 1),
    ("github-token", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", 0),
    ("gitlab-token", r"\bglpat-[A-Za-z0-9_-]{16,}\b", 0),
    ("slack-token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b", 0),
    ("anthropic-key", r"\bsk-ant-[A-Za-z0-9_-]{16,}\b", 0),
    ("url-credentials", r"[a-z][a-z0-9+.-]*://[^/\s:@]+:([^@\s/]{3,})@", 1),
    ("generic-secret", r"(?i)\b[a-z0-9_.-]*(?:api[_-]?key|secret|token|passwd|password|pwd)[a-z0-9_.-]*[\"']?\s*[:=]\s*[\"']?([^\s\"',;]{6,})", 1),
]


@dataclass
class Rule:
    name: str
    rx: re.Pattern[str]
    group: int


def _compile(name: str, pattern: str, group: int) -> Rule | None:
    try:
        return Rule(name, re.compile(pattern), group)
    except re.error:
        return None


def load_rules(gitleaks_toml: Path | None) -> list[Rule]:
    rules: list[Rule] = []
    if gitleaks_toml and gitleaks_toml.is_file():
        try:
            data = tomllib.loads(gitleaks_toml.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            data = {}
        for r in data.get("rules", []):
            if r.get("regex"):
                rule = _compile(f"gitleaks:{r.get('id', 'rule')}", r["regex"], int(r.get("secretGroup") or 0))
                if rule:
                    rules.append(rule)
    for name, pat, grp in BUILTIN:
        rule = _compile(name, pat, grp)
        if rule:
            rules.append(rule)
    return rules


class Redactor:
    def __init__(self, gitleaks_toml: Path | None):
        self.rules = load_rules(gitleaks_toml)

    def redact(self, text: str) -> tuple[str, int]:
        count = 0
        for rule in self.rules:
            def sub(m: re.Match[str], rule: Rule = rule) -> str:
                nonlocal count
                count += 1
                tag = f"[REDACTED:{rule.name}]"
                if rule.group and rule.group <= (m.re.groups or 0) and m.group(rule.group):
                    s, e = m.span(rule.group)
                    base = m.start()
                    return m.group(0)[: s - base] + tag + m.group(0)[e - base:]
                return tag
            text = rule.rx.sub(sub, text)
        return text, count
