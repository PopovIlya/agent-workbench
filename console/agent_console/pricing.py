"""Cost from token counts. No price is hardcoded: all values come from pricing.yaml.

Main goal: turn per-message token counts into a USD figure, or say "unknown".
Does: match the served model id to a table key by substring (longest key first, so `opus-5-5`
wins over `opus-5`), fall back to the model tier (flag "price by tier"), apply the over-100K tier
per request and the regional multiplier.
Does not: invent a price. No key and no tier default -> cost is None ("cost unknown").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PRICE_FIELDS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
TIERS = ("opus", "sonnet", "haiku")


@dataclass
class Match:
    key: str | None
    how: str  # "exact" | "tier" | "unknown"


class Pricing:
    def __init__(self, table: dict[str, Any] | None = None):
        t = table or {}
        self.multiplier = float(t.get("regional_multiplier") or 1.0)
        self.models: dict[str, dict[str, Any]] = {
            k: v for k, v in (t.get("models") or {}).items() if isinstance(v, dict)
        }
        self.tier_defaults: dict[str, str] = dict(t.get("tier_defaults") or {})

    @classmethod
    def load(cls, path: Path) -> "Pricing":
        try:
            return cls(yaml.safe_load(path.read_text()) or {})
        except (OSError, yaml.YAMLError):
            return cls({})

    @property
    def empty(self) -> bool:
        return not self.models

    def match(self, model_id: str | None) -> Match:
        mid = (model_id or "").lower()
        if not mid:
            return Match(None, "unknown")
        for key in sorted(self.models, key=len, reverse=True):  # longest key first
            if key.lower() in mid:
                return Match(key, "exact")
        for tier in TIERS:
            if tier in mid:
                key = self.tier_defaults.get(tier)
                if key in self.models:
                    return Match(key, "tier")
        return Match(None, "unknown")

    def message_cost_parts(self, model_id: str | None, tokens: dict[str, int]) -> tuple[dict[str, float] | None, Match]:
        """USD for one request split by token type: {input, output, cache_read, cache_write} (the two cache-write kinds are added), or (None, match)."""
        m = self.match(model_id)
        if m.key is None:
            return None, m
        entry = self.models[m.key]
        side = tokens.get("input", 0) + tokens.get("cache_read", 0) + tokens.get("cache_w5m", 0) + tokens.get("cache_w1h", 0)
        prices = entry.get("over_100k") if side > 100_000 and isinstance(entry.get("over_100k"), dict) else entry
        parts = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
        for tok, field, group in (("input", "input", "input"), ("output", "output", "output"), ("cache_read", "cache_read", "cache_read"),
                                  ("cache_w5m", "cache_write_5m", "cache_write"), ("cache_w1h", "cache_write_1h", "cache_write")):
            n = tokens.get(tok, 0)
            if not n:
                continue
            price = prices.get(field)
            if price is None:
                return None, Match(m.key, "unknown")  # a needed price is missing: do not guess
            parts[group] += n * float(price) / 1_000_000 * self.multiplier
        return parts, m

    def message_cost(self, model_id: str | None, tokens: dict[str, int]) -> tuple[float | None, Match]:
        """USD for one request (one API message), or (None, match) when no price applies."""
        parts, m = self.message_cost_parts(model_id, tokens)
        return (None if parts is None else sum(parts.values())), m
