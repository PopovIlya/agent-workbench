"""EXP1-R22C: the one number formatter of the comparison page and CLI (CON-029), plus the strings both print (CON-024, CON-026).

Main goal: show tokens, dollars, minutes and ratios round half up on the shortest decimal text, never print `-0`,
and that page and CLI show the same strings. Pure-function cases need no fixture; cases that read logs use `env`.
Modules under test are imported inside each test, so a missing module fails that test (never a skip).
"""

from __future__ import annotations

import importlib
import json
import re

from conftest import PROJECT, add_sub, assistant, tool_use, usage, user_prompt, write_jsonl

PX = ("regional_multiplier: 1.0\nmodels:\n"
      "  m-one: {input: 1.00, output: 2.00, cache_write_5m: 3.00, cache_write_1h: 4.00, cache_read: 0.50}\n"
      "tier_defaults: {sonnet: m-one}\n")


def fmt():
    return importlib.import_module("agent_console.compare_format")


# ---------- local helpers for the cases that read logs ----------

def main_session(env, session, key, messages=(), subs=()):
    """A main file `[key] start` at t=0; `messages` = [(t, input, output)] main assistant messages; `subs` = [input tokens] one sub run each."""
    recs = [user_prompt(f"[{key}] start", t=0, session=session)]
    for i, (t, inp, out) in enumerate(messages):
        recs.append(assistant(f"{session}-m{i}", model="m-one", u=usage(inp, out), t=t, session=session))
    for i, inp in enumerate(subs):
        tid, agent = f"{session}-t{i}", f"{session}-ag{i}"
        recs.append(assistant(f"{session}-sp{i}", model="m-one", u=usage(0, 0), t=1 + i, session=session,
                              blocks=[tool_use(tid, "Agent", subagent_type="builder", description=f"[{key}] x", prompt="p")]))
        add_sub(env.root, session, agent, "builder", [assistant(f"{agent}-n", model="m-one", u=usage(inp, 0), t=10 + i, session=session, agent=agent)], tid)
    write_jsonl(env.root / PROJECT / f"{session}.jsonl", recs)


def px(env):
    (env.tmp / "pricing.yaml").write_text(PX)


def cli_run(args, capsys):
    rc = importlib.import_module("agent_console.compare_cli").main(list(args))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def line_cells(out, label):
    for ln in out.rstrip("\n").split("\n")[1:]:
        cells = [c.strip() for c in ln.split("|")]
        if cells[0] == label:
            return cells
    raise AssertionError(f"no line {label!r} in:\n{out}")


def page_rows(body):
    """{row id: (a, b, diff, ratio)} from the page markup (B2)."""
    pat = (r'<tr data-row="([^"]+)"><th scope="row">[^<]*</th><td class="a">([^<]*)</td><td class="b">([^<]*)</td>'
           r'<td class="d"><span class="diff">([^<]*)</span> \(<span class="ratio">([^<]*)</span>\)</td></tr>')
    return {m[0]: m[1:] for m in re.findall(pat, body)}


def page_body(env, a, b):
    from fastapi.testclient import TestClient
    from agent_console import config, server
    from agent_console.pricing import Pricing
    from agent_console.store import Store
    st = Store()
    st.ingest()
    client = TestClient(server.create_app(store=st, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")
    r = client.get("/compare", params={"a": a, "b": b})
    assert r.status_code == 200, r.text
    return r.text


def shapes(text):
    return (set(re.findall(r"-?\d+k", text)), set(re.findall(r"-?\$\d+\.\d\d", text)), set(re.findall(r"\d+ min", text)))


# ---------- CON-029: tokens ----------

# rule: CON-029
def test_bva_015_tokens_499_rounds_down_to_0k():
    """BVA-015 (CI-029-01): one below the .5 tie."""
    assert fmt().tokens(499) == "0k"
    assert fmt().tokens(499.0) == "0k"


# rule: CON-029
def test_bva_016_tokens_500_rounds_up_to_1k():
    """BVA-016 (CI-029-02): the tie goes up (Python round() would give 0k)."""
    assert fmt().tokens(500) == "1k"
    assert fmt().tokens(500.0) == "1k"


# rule: CON-029
def test_bva_017_tokens_above_a_million_have_no_separator():
    """BVA-017 (CI-029-03)."""
    assert fmt().tokens(1234567) == "1235k"
    assert fmt().tokens(1234567.0) == "1235k"


# rule: CON-029
def test_bva_018_negative_tokens_rounding_to_zero_have_no_sign():
    """BVA-018 (CI-029-04): never `-0k`."""
    assert fmt().tokens(-400) == "0k"
    assert fmt().tokens(-400.0) == "0k"


# rule: CON-029
def test_bva_019_negative_token_tie_keeps_the_sign_and_rounds_away_from_zero():
    """BVA-019 (CI-029-05)."""
    assert fmt().tokens(-500) == "-1k"
    assert fmt().tokens(-500.0) == "-1k"


# ---------- CON-029: dollars ----------

# rule: CON-029
def test_bva_020_dollars_at_the_half_cent_tie_round_up():
    """BVA-020 (CI-029-06)."""
    assert fmt().usd(0.005) == "$0.01"


# rule: CON-029
def test_bva_021_negative_dollars_rounding_to_zero_have_no_sign():
    """BVA-021 (CI-029-07)."""
    assert fmt().usd(-0.004) == "$0.00"


# rule: CON-029
def test_bva_022_negative_dollars_put_the_sign_before_the_dollar_sign():
    """BVA-022 (CI-029-08)."""
    assert fmt().usd(-1.234) == "-$1.23"


# rule: CON-029
def test_bva_023_dollars_of_a_thousand_or_more_have_no_separator():
    """BVA-023 (CI-029-09)."""
    assert fmt().usd(1234.56) == "$1234.56"


# rule: CON-029
def test_bva_024_negative_dollar_tie_rounds_away_from_zero():
    """BVA-024 (CI-029-10)."""
    assert fmt().usd(-0.005) == "-$0.01"


# ---------- CON-029: minutes ----------

# rule: CON-029
def test_bva_025_29_seconds_is_0_min():
    """BVA-025 (CI-029-11)."""
    assert fmt().minutes(29) == "0 min"
    assert fmt().minutes(29.0) == "0 min"


# rule: CON-029
def test_bva_026_30_seconds_is_1_min():
    """BVA-026 (CI-029-12): the tie goes up."""
    assert fmt().minutes(30) == "1 min"
    assert fmt().minutes(30.0) == "1 min"


# rule: CON-029
def test_bva_027_zero_seconds_is_0_min_not_a_bare_zero():
    """BVA-027 (CI-029-13)."""
    assert fmt().minutes(0) == "0 min"
    assert fmt().minutes(0.0) == "0 min"


# rule: CON-029
def test_bva_028_negative_time_rounding_to_zero_has_no_sign():
    """BVA-028 (CI-029-14)."""
    assert fmt().minutes(-20) == "0 min"
    assert fmt().minutes(-20.0) == "0 min"


# rule: CON-029
def test_bva_029_an_hour_or_more_stays_in_minutes():
    """BVA-029 (CI-029-15)."""
    assert fmt().minutes(8100) == "135 min"
    assert fmt().minutes(8100.0) == "135 min"


# ---------- CON-029 / CON-024: ratio and cost share ----------

# rule: CON-029
# rule: CON-024
def test_bva_030_ratio_and_share_round_half_up_with_two_decimals():
    """BVA-030 (CI-029-17 and CI-024-06; BVA-012 merged): 0.125 -> 0.13 (round() gives 0.12); the share 0.25 prints 0.25, no %."""
    f = fmt()
    assert f.ratio(0.125) == "0.13"
    assert f.ratio(2.125) == "2.13"
    assert f.ratio(0.005) == "0.01"
    assert f.ratio(0.124) == "0.12"
    assert f.ratio(0.25) == "0.25"


# ---------- CON-029: page and CLI print the same strings ----------

# rule: CON-029
def test_ep_029_16_page_and_cli_show_the_same_formatted_figures(env, capsys):
    """EP-029-16 (CI-029-16): one fixed row per figure; the sets of `Nk`, `$N.NN`, `N min` match on page and CLI; row cells exact."""
    px(env)
    main_session(env, "S1", "ABC-1", messages=[(100, 1500, 616_000)])
    main_session(env, "S2", "ABC-2", messages=[(400, 2500, 1_250_000)])
    body = page_body(env, "ABC-1", "ABC-2")
    rc, out, err = cli_run(["ABC-1", "ABC-2"], capsys)
    assert (rc, err) == (0, "")
    page_sets, cli_sets = shapes(body), shapes(out)
    assert page_sets == cli_sets
    assert all(page_sets)
    assert {"2k", "3k", "1k", "616k", "1250k", "634k"} <= page_sets[0]
    assert {"$1.23", "$2.50", "$1.27"} <= page_sets[1]
    assert {"2 min", "7 min", "5 min"} <= page_sets[2]
    rows = page_rows(body)
    expected = {"tokens.main.input": ("2k", "3k", "1k", "1.67"), "tokens.main.output": ("616k", "1250k", "634k", "2.03"),
                "cost_usd.total": ("$1.23", "$2.50", "$1.27", "2.03"), "time_s.wall": ("2 min", "7 min", "5 min", "4.00")}
    labels = {"tokens.main.input": "Main-session tokens, input", "tokens.main.output": "Main-session tokens, output",
              "cost_usd.total": "Cost", "time_s.wall": "Wall time"}
    for rid, cells in expected.items():
        assert tuple(rows[rid]) == cells
        a, b, diff_cell = line_cells(out, labels[rid])[1:]
        assert (a, b, diff_cell) == (cells[0], cells[1], f"{cells[2]} ({cells[3]})")


# rule: CON-029
def test_ep_029_18_json_keeps_raw_numbers_without_units(env, capsys):
    """EP-029-18 (CI-029-18): --json holds raw ints and floats; no `k`, `$` or `min` in any value."""
    px(env)
    main_session(env, "S1", "ABC-1", messages=[(29, 1499, 0)])
    main_session(env, "S9", "ABC-9", messages=[(50, 10, 0)])
    rc, out, err = cli_run(["ABC-1", "ABC-9", "--json"], capsys)
    assert (rc, err) == (0, "")
    a = json.loads(out)["a"]
    assert a["tokens"]["main"]["input"] == 1499 and isinstance(a["tokens"]["main"]["input"], int)
    assert isinstance(a["cost_usd"]["main"], float)
    assert abs(a["cost_usd"]["main"] - 0.001499) < 1e-12
    assert a["time_s"]["wall"] == 29

    def leaves(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from leaves(v)
        else:
            yield node

    text = [v for v in leaves(a) if isinstance(v, str)]
    assert not [v for v in text if re.search(r"\d+k\b|\$|\bmin\b", v)]


# ---------- CON-026: the difference and its ratio as printed ----------

# rule: CON-026
def test_ep_026_06_difference_is_rounded_from_the_raw_value_not_from_rounded_sides(env, capsys):
    """EP-026-06 (CI-026-06; CLI half, page half is in test_compare_page.py): 1499 vs 2501 -> 1k, 3k and a difference of 1k (1002), not 2k."""
    main_session(env, "S1", "ABC-1", subs=[1499])
    main_session(env, "S2", "ABC-2", subs=[2501])
    rc, out, err = cli_run(["ABC-1", "ABC-2", "--json"], capsys)
    assert (rc, err) == (0, "")
    assert json.loads(out)["diff"]["tokens"]["total"]["input"]["diff"] == 1002
    rc, out, err = cli_run(["ABC-1", "ABC-2"], capsys)
    assert (rc, err) == (0, "")
    cells = line_cells(out, "Tokens, input")
    assert cells[1:3] == ["1k", "3k"]
    assert cells[3].startswith("1k ")
    assert "2k" not in cells[3]


# rule: CON-026
def test_bva_013_ratio_tie_at_one_eighth_and_17_eighths_prints_half_up(env, capsys):
    """BVA-013 (CI-026-07): 1/8 = 0.125 -> 0.13 and 17/8 = 2.125 -> 2.13 in the CLI text; JSON keeps the raw ratio."""
    for i, (key, runs) in enumerate((("EXP1-100", 8), ("EXP1-101", 1), ("EXP1-102", 8), ("EXP1-103", 17))):
        main_session(env, f"S{i}", key, subs=[10] * runs)
    rc, out, err = cli_run(["EXP1-100", "EXP1-101", "--json"], capsys)
    assert (rc, err) == (0, "")
    assert json.loads(out)["diff"]["runs"]["total"] == {"diff": -7, "ratio": 0.125}
    rc, out, err = cli_run(["EXP1-100", "EXP1-101"], capsys)
    assert line_cells(out, "Role runs")[3] == "-7 (0.13)"
    rc, out, err = cli_run(["EXP1-102", "EXP1-103", "--json"], capsys)
    assert json.loads(out)["diff"]["runs"]["total"] == {"diff": 9, "ratio": 2.125}
    rc, out, err = cli_run(["EXP1-102", "EXP1-103"], capsys)
    assert line_cells(out, "Role runs")[3] == "9 (2.13)"
    assert fmt().ratio(0.125) == "0.13"
    assert fmt().ratio(2.125) == "2.13"


# rule: CON-035
def test_safe_shows_tab_newline_del_and_c1_as_backslash_x_escapes():
    """Review 6, 3: safe() writes every C0/C1 control and DEL as the text `\\xNN` (lower-case hex), never `?` or nothing."""
    assert fmt().safe("\t\n\x7f\x9f") == "\\x09\\x0a\\x7f\\x9f"
    assert fmt().safe("a\x1b[2Jb") == "a\\x1b[2Jb"
    assert fmt().safe("plain 12 | x") == "plain 12 | x"
