"""Cost: no hardcoded prices; missing prices mean 'cost unknown'; matching and tiers."""

from pathlib import Path

import pytest

from agent_console.pricing import Pricing

# Fixture values only (the follow-up task's estimates). The shipped pricing.yaml is empty.
TABLE = {
    "regional_multiplier": 1.10,
    "models": {
        "opus-5-5": {"input": 4.0, "output": 20.0, "cache_write_5m": 5.0, "cache_write_1h": 8.0, "cache_read": 0.2, "source": "estimate"},
        "opus-5": {"input": 5.0, "output": 25.0, "cache_write_5m": 6.25, "cache_write_1h": 10.0, "cache_read": 0.5, "source": "estimate"},
        "sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_write_5m": 2.5, "cache_write_1h": 4.0, "cache_read": 0.2, "source": "estimate"},
        "haiku-5-5": {"input": 0.1, "output": 0.5, "cache_write_5m": 0.125, "cache_write_1h": 0.2, "cache_read": 0.01, "source": "estimate",
                      "over_100k": {"input": 0.5, "output": 2.5, "cache_write_5m": 0.625, "cache_write_1h": 1.0, "cache_read": 0.05}},
    },
    "tier_defaults": {"opus": "opus-5-5", "sonnet": "sonnet-5-5", "haiku": "haiku-5-5"},
}
M = 1_000_000


def tok(**kw):
    return {"input": 0, "output": 0, "cache_read": 0, "cache_w5m": 0, "cache_w1h": 0, **kw}


SHIPPED = Pricing.load(Path(__file__).resolve().parents[1] / "pricing.yaml")


def test_shipped_pricing_yaml_is_all_estimates_and_matches_the_common_model_ids():
    assert not SHIPPED.empty and SHIPPED.multiplier == 1.0
    assert all(v["source"] == "estimate" for v in SHIPPED.models.values())   # nothing here was checked against an invoice
    assert not any(v["source"] == "invoice" for v in SHIPPED.models.values())  # never presented as the invoice
    for mid, key, how in [("claude-sonnet-5", "sonnet-5", "exact"), ("claude-sonnet-5-5", "sonnet-5-5", "exact"),
                          ("us.anthropic.claude-sonnet-5-5", "sonnet-5-5", "exact"),
                          ("anthropic.claude-haiku-4-5-20251001-v1:0", "haiku-4-5", "exact"),
                          ("claude-opus-5-5", "opus-5-5", "exact"), ("claude-opus-5", "opus-5", "exact"), ("claude-haiku-5-5", "haiku-5-5", "exact")]:
        m = SHIPPED.match(mid)
        assert (m.key, m.how) == (key, how), mid
    m = SHIPPED.match("claude-sonnet-9")             # an unknown minor version: priced by tier and flagged
    assert (m.key, m.how) == ("sonnet-5-5", "tier")
    assert SHIPPED.match("some-other-model").how == "unknown" and SHIPPED.message_cost("some-other-model", tok(input=5))[0] is None


def test_missing_pricing_file_is_empty_not_a_crash(tmp_path):
    assert Pricing.load(tmp_path / "nope.yaml").empty


@pytest.mark.parametrize("mid", ["claude-opus-5-5", "anthropic.claude-opus-5-5-v1:0", "us.anthropic.claude-opus-5-5"])
def test_provider_ids_match_by_substring(mid):
    assert Pricing(TABLE).match(mid).key == "opus-5-5"


def test_longest_key_wins_over_its_prefix_key():
    p = Pricing(TABLE)
    assert p.match("claude-opus-5-5").key == "opus-5-5" and p.match("claude-opus-5").key == "opus-5" and p.match("claude-opus-5-1").key == "opus-5"


def test_unknown_minor_version_falls_back_to_tier_and_is_flagged():
    p = Pricing(TABLE)
    m = p.match("claude-sonnet-5")  # real id in the logs: no minor version
    assert (m.key, m.how) == ("sonnet-5-5", "tier")
    m = p.match("anthropic.claude-haiku-4-5-20251001-v1:0")  # real id in the logs: haiku 4.5
    assert (m.key, m.how) == ("haiku-5-5", "tier")


def test_unknown_model_has_no_price():
    p = Pricing(TABLE)
    assert p.match("gpt-something").how == "unknown" and p.message_cost("gpt-something", tok(input=5))[0] is None
    assert p.message_cost(None, tok(input=5))[0] is None


def test_unknown_tier_without_default_has_no_price():
    p = Pricing({"models": TABLE["models"], "tier_defaults": {"opus": "opus-5-5"}})
    assert p.match("claude-sonnet-9").how == "unknown"


def test_cost_arithmetic_with_multiplier():
    c, _ = Pricing(TABLE).message_cost("claude-sonnet-5-5", tok(input=M, output=M, cache_read=M, cache_w5m=M, cache_w1h=M))
    assert c == pytest.approx((2.0 + 10.0 + 0.2 + 2.5 + 4.0) * 1.10)


def test_haiku_over_100k_tier_applies_per_request():
    p = Pricing(TABLE)
    small, _ = p.message_cost("claude-haiku-5-5", tok(input=50_000, output=M))
    big, _ = p.message_cost("claude-haiku-5-5", tok(input=90_000, cache_read=20_000, output=M))  # input side 110K > 100K
    assert small == pytest.approx((50_000 * 0.1 / M + 0.5) * 1.10)
    assert big == pytest.approx((90_000 * 0.5 / M + 20_000 * 0.05 / M + 2.5) * 1.10)


def test_over_100k_not_defined_means_normal_price():
    c, _ = Pricing(TABLE).message_cost("claude-sonnet-5-5", tok(input=500_000))
    assert c == pytest.approx(500_000 * 2.0 / M * 1.10)


def test_a_missing_needed_price_gives_unknown_not_zero():
    t = {"models": {"opus-5-5": {"input": 4.0, "output": 20.0}}}
    assert Pricing(t).message_cost("claude-opus-5-5", tok(input=10, cache_read=10))[0] is None
    assert Pricing(t).message_cost("claude-opus-5-5", tok(input=10, output=10))[0] is not None  # unused fields may be absent


def test_ui_labels_say_unknown_and_estimate(env):
    from agent_console import queries
    from agent_console.store import Store
    from conftest import PROJECT, assistant, usage, write_jsonl
    write_jsonl(env.root / PROJECT / "S1.jsonl", [assistant("m1", model="claude-sonnet-5", u=usage(1000, 500)), assistant("m2", model="claude-weird", u=usage(1, 1), t=3)])
    s = Store()
    s.ingest()
    db = s.reader()
    rows = queries.usage_rows(db, scope="all")

    def label(pr):
        return queries._total(queries.aggregate(rows, lambda r: "w", pr).get("w"), pr)["cost_label"]
    assert label(Pricing({})) == "cost unknown" and Pricing({}).empty
    lbl = label(Pricing(TABLE))
    assert lbl.startswith("≈ $") and "(estimate)" in lbl and "unpriced" in lbl and "price by tier" in lbl
