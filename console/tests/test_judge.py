"""The judge, built and OFF: the switch, the caps, the JSON, 'unknown', the rubric split, kappa and calibration. A stubbed model only."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]   # console/
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "agent_scoring"))
from agent_scoring import judge as J  # noqa: E402
import calibrate  # noqa: E402


class Stub:
    """A stubbed model: records every prompt it receives."""

    def __init__(self, answer='{"score": 0.8, "evidence": ["file.md:3"]}', usd=0.01):
        self.answer, self.usd, self.prompts = answer, usd, []

    def __call__(self, prompt, model):
        self.prompts.append((prompt, model))
        return self.answer, self.usd


ON = {**J.DEFAULTS, "enabled": True, "model": "judge-model-x", "confirmed_model": "judge-model-x"}
DIM = J.Dimension("the_change_file", "The change file")


def judge(tmp_path, cfg=None, stub=None):
    return J.Judge(cfg or ON, runner=stub or Stub(), state=tmp_path, now=lambda: datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc))


def ask(j):
    return j.judge_dimension(task_id="S:a", role="lead-qa", dimension=DIM, spawn_prompt="do the thing", outputs="Final reply: done")


# ---------------- the switch
def test_the_judge_is_off_by_default_and_nothing_is_sent(tmp_path):
    cfg = J.load_config(tmp_path)                                       # no judge.json at all
    assert cfg["enabled"] is False and cfg["model"] == "" and J.is_on(cfg) is False
    stub = Stub()
    with pytest.raises(J.JudgeOff):
        ask(judge(tmp_path, cfg, stub))
    assert stub.prompts == [] and not (tmp_path / "judge.jsonl").exists()


@pytest.mark.parametrize("patch", [{"enabled": False}, {"model": ""}, {"confirmed_model": ""}, {"confirmed_model": "another-model"}])
def test_every_part_of_the_switch_is_needed_a_model_change_needs_the_persons_confirmation(tmp_path, patch):
    stub = Stub()
    with pytest.raises(J.JudgeOff):
        ask(judge(tmp_path, {**ON, **patch}, stub))
    assert stub.prompts == []


def test_a_config_file_turns_it_on_only_with_all_three_keys(tmp_path):
    (tmp_path / "judge.json").write_text(json.dumps({"enabled": True, "model": "m1"}))
    assert J.is_on(J.load_config(tmp_path)) is False
    (tmp_path / "judge.json").write_text(json.dumps({"enabled": True, "model": "m1", "confirmed_model": "m1"}))
    assert J.is_on(J.load_config(tmp_path)) is True
    (tmp_path / "judge.json").write_text("not json")
    assert J.load_config(tmp_path)["enabled"] is False


def test_no_code_path_reaches_the_model_without_the_switch():
    src = (ROOT / "agent_scoring" / "judge.py").read_text()
    assert src.count("self.runner(") == 1 and "def call(" in src                  # the single call site sits inside Judge.call, behind is_on
    assert "claude_runner" in src and 'subprocess.run(["claude"' in src
    other = "".join((ROOT / "agent_scoring" / f).read_text() for f in ("agent_score_v2.py", "agent_score.py"))
    assert "claude_runner" not in other and 'run(["claude"' not in other and "Judge(" not in other and "from . import judge" not in other     # the scorer never constructs a judge


# ---------------- a call
def test_one_isolated_call_per_dimension_and_the_prompt_has_no_reasoning(tmp_path):
    stub = Stub()
    rec = ask(judge(tmp_path, stub=stub))
    assert len(stub.prompts) == 1 and stub.prompts[0][1] == "judge-model-x"
    p = stub.prompts[0][0]
    assert "The change file" in p and "do the thing" in p and "Final reply: done" in p and "did NOT do this work" in p and "thinking" not in p.lower()
    assert rec["score"] == 0.8 and rec["evidence"] == ["file.md:3"] and rec["judge_version"] == "1" and rec["model"] == "judge-model-x"
    assert json.loads((tmp_path / "judge.jsonl").read_text().splitlines()[0])["dimension"] == "the_change_file"


@pytest.mark.parametrize("text,score,err", [
    ('{"score": 0.5, "evidence": ["a"]}', 0.5, False), ('```json\n{"score": 1, "evidence": []}\n```', 1.0, False),
    ('Here you go: {"score": 0.25, "evidence": ["x"]} done', 0.25, False),
    ('{"score": "unknown", "evidence": ["cannot see the file"]}', None, False), ('{"score": "Unknown"}', None, False),
    ('{"score": 1.5}', None, True), ('{"score": -0.1}', None, True), ('{"score": true}', None, True), ("sounds good to me", None, True), ("[1, 2]", None, True)])
def test_parsing_unknown_and_bad_answers_leave_the_check_empty(text, score, err):
    j = J.parse_judgement(text)
    assert j["score"] == score and (("error" in j) is err)


def test_evidence_is_capped():
    j = J.parse_judgement(json.dumps({"score": 0.5, "evidence": ["x" * 500] * 9}))
    assert len(j["evidence"]) == J.EVIDENCE_MAX and all(len(e) <= J.EVIDENCE_CHARS for e in j["evidence"])


def test_the_run_score_ignores_unknown_and_is_empty_when_all_are_unknown():
    assert J.run_score([{"score": 1.0}, {"score": 0.5}, {"score": None}]) == 0.75
    assert J.run_score([{"score": None}]) is None and J.run_score([]) is None


# ---------------- the caps
def test_the_per_call_cap_stops_a_call_before_it_is_sent(tmp_path):
    stub = Stub()
    cfg = {**ON, "per_call_usd_cap": 0.000001}
    with pytest.raises(J.JudgeOff, match="per-call"):
        ask(judge(tmp_path, cfg, stub))
    assert stub.prompts == []


def test_a_call_that_cost_more_than_the_cap_is_recorded_and_refused(tmp_path):
    with pytest.raises(J.JudgeOff, match="cost"):
        ask(judge(tmp_path, {**ON, "per_call_usd_cap": 0.05}, Stub(usd=0.5)))
    assert json.loads((tmp_path / "judge_spend.jsonl").read_text())["usd"] == 0.5          # the spend is still on the ledger


def test_the_daily_cap_stops_further_calls_and_resets_the_next_day(tmp_path):
    stub = Stub(usd=0.2)
    j = judge(tmp_path, {**ON, "daily_usd_cap": 0.3}, stub)
    ask(j)
    ask(j)                                                                                  # 0.4 spent: over the cap now
    with pytest.raises(J.JudgeOff, match="daily cap"):
        ask(j)
    assert len(stub.prompts) == 2
    tomorrow = J.Judge({**ON, "daily_usd_cap": 0.3}, runner=stub, state=tmp_path, now=lambda: datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc))
    ask(tomorrow)
    assert len(stub.prompts) == 3


# ---------------- the rubric split
def test_each_output_of_a_criteria_file_is_a_dimension_and_all_22_files_split():
    d = J.dimensions((ROOT.parent / "roles-22/criteria/lead-qa.md").read_text())
    assert [x.what for x in d] == ["Approvals recorded in the ticket's record", "A report: what is covered, how good it is, the biggest risks"]
    assert len({x.key for x in d}) == 2
    for f in [*(ROOT.parent / "roles-22/criteria").glob("*.md"), *(ROOT.parent / "kit/criteria").glob("*.md")]:
        assert J.dimensions(f.read_text()), f.name


# ---------------- kappa and calibration
def test_cohen_kappa():
    assert J.cohen_kappa([True, True, False, False], [True, True, False, False]) == 1.0
    assert J.cohen_kappa([True, False, True, False], [False, True, False, True]) == -1.0
    k = J.cohen_kappa([True, True, True, False, False, False], [True, True, False, False, False, True])
    assert k == pytest.approx(1 / 3)
    assert J.cohen_kappa([], []) is None and J.cohen_kappa([True], [True, False]) is None
    assert J.cohen_kappa([True, True], [True, True]) == 1.0                                 # no variance, full agreement


def test_the_judge_weight_needs_n_30_and_kappa_06_and_the_current_version():
    cfg = ON
    assert J.is_calibrated({"n": 30, "kappa": 0.6, "judge_version": "1"}, cfg)
    assert not J.is_calibrated({"n": 29, "kappa": 0.9, "judge_version": "1"}, cfg)
    assert not J.is_calibrated({"n": 40, "kappa": 0.59, "judge_version": "1"}, cfg)
    assert not J.is_calibrated({"n": 40, "kappa": 0.9, "judge_version": "0"}, cfg)          # calibrated for another judge version
    assert not J.is_calibrated({"n": 40, "kappa": 0.9, "judge_version": "1"}, {**cfg, "enabled": False})
    assert not J.is_calibrated({}, None)


def test_calibrate_computes_kappa_from_verdicts_and_judge_records_and_writes_the_file(tmp_path):
    scores = tmp_path / "scores.jsonl"
    lines, judged, verdicts = [], [], []
    for i in range(6):
        t = f"PROJ-{i}"
        lines.append({"task_id": f"S:{i}", "scorer_version": 2, "ticket_eff": t})
        judged.append({"task_id": f"S:{i}", "dimension": "d", "score": 0.9 if i < 3 else 0.2})
        verdicts.append({"ticket": t, "verdict": "accepted" if i in (0, 1, 5) else "rejected"})
    verdicts.append({"ticket": "PROJ-0", "verdict": "rejected"})                                # the latest verdict of a ticket wins
    verdicts.append({"ticket": "PROJ-0", "verdict": "accepted_after_rework"})
    scores.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    (tmp_path / "judge.jsonl").write_text("\n".join(json.dumps(x) for x in judged) + "\n")
    (tmp_path / "verdicts.jsonl").write_text("\n".join(json.dumps(x) for x in verdicts) + "\n")
    cal = calibrate.compute(tmp_path, scores, now=datetime(2026, 11, 3, tzinfo=timezone.utc))
    assert cal["n"] == 6 and cal["judge_version"] == "1" and cal["weight_active"] is False         # n < 30
    # judge says acceptable: PROJ-0,1,2; the person: PROJ-0,1,5 -> agree on 0,1,3,4 -> po = 4/6, pe = .5 -> kappa = 1/3
    assert cal["kappa"] == pytest.approx(1 / 3, abs=1e-3) and cal["agreement"] == pytest.approx(4 / 6, abs=1e-3)
    out = tmp_path / "cal.json"
    assert calibrate.main(["--state", str(tmp_path), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["n"] == 6


def test_calibrate_run_with_the_judge_off_does_nothing(tmp_path, capsys):
    assert calibrate.main(["--state", str(tmp_path), "--out", str(tmp_path / "c.json"), "--run"]) == 0
    assert "judge is off" in capsys.readouterr().out and not (tmp_path / "c.json").exists() and not (tmp_path / "judge.jsonl").exists()


def test_a_dry_run_on_fixtures_with_a_stubbed_model_judges_each_dimension_and_feeds_the_check(tmp_path):
    stub = Stub('{"score": 0.9, "evidence": ["x"]}')
    j = judge(tmp_path, stub=stub)
    dims = J.dimensions((ROOT.parent / "roles-22/criteria/lead-qa.md").read_text())
    recs = [j.judge_dimension(task_id="S:1", role="lead-qa", dimension=d, spawn_prompt="p", outputs="o") for d in dims]
    assert len(stub.prompts) == len(dims) == 2 and J.run_score(recs) == 0.9
    assert J.judge_results(tmp_path) == {"S:1": 0.9}
