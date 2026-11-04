"""The person's verdicts, defect reports and flag decisions: validated writes, files created on first use, the latest verdict wins."""

import json

import pytest
from fastapi.testclient import TestClient

from agent_console import gold, server
from agent_console.pricing import Pricing
from agent_console.store import Store
from ctq_fixtures import A, P, TU, add_sub, main_file


@pytest.fixture
def api(env):
    spawn = TU("sp", "Agent", subagent_type="builder", description="[PROJ-77] build", prompt="p")
    main_file(env, [P(0, "human"), A("m1", 5, [spawn], stop="tool_use")])
    add_sub(env.root, "S1", "a1", "builder", [A("s1", 10, agent="a1")], "sp")
    st = Store()
    st.ingest()
    return TestClient(server.create_app(store=st, pricing=Pricing({}), port=8790), base_url="http://127.0.0.1:8790")


def lines(env, name):
    p = env.home / name
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def test_a_missing_file_is_created_with_mode_0600_and_holds_one_line(api, env):
    assert not (env.home / "verdicts.jsonl").exists()
    r = api.post("/api/verdict", json={"ticket": "PROJ-77", "verdict": "accepted", "note": "good", "roles": ["builder"]})
    assert r.status_code == 200 and r.json()["verdict"]["verdict"] == "accepted"
    assert oct((env.home / "verdicts.jsonl").stat().st_mode & 0o777) == "0o600" and lines(env, "verdicts.jsonl")[0]["roles"] == ["builder"]


def test_the_latest_verdict_of_a_ticket_wins_and_the_history_is_kept(api, env):
    for v in ("rejected", "accepted_after_rework", "accepted"):
        assert api.post("/api/verdict", json={"ticket": "PROJ-77", "verdict": v}).status_code == 200
    assert gold.latest_verdicts()["PROJ-77"]["verdict"] == "accepted" and len(lines(env, "verdicts.jsonl")) == 3


@pytest.mark.parametrize("body", [
    {"ticket": "PROJ-77", "verdict": "maybe"},                                              # not an allowed value
    {"ticket": "PROJ-77", "verdict": "accepted", "note": "x" * 201},                        # note over 200 characters
    {"ticket": "bt 77", "verdict": "accepted"}, {"ticket": "PROJ-77", "verdict": "accepted", "roles": ["Bad Role!"]},
    {"ticket": "PROJ-77", "verdict": "accepted", "extra": 1}, {"verdict": "accepted"}])
def test_invalid_verdicts_are_refused_and_nothing_is_written(api, env, body):
    assert api.post("/api/verdict", json=body).status_code == 422 and not (env.home / "verdicts.jsonl").exists()


def test_a_note_of_exactly_200_characters_is_accepted_and_a_verdict_for_an_unknown_ticket_is_not(api, env):
    assert api.post("/api/verdict", json={"ticket": "PROJ-77", "verdict": "rejected", "note": "x" * 200}).status_code == 200
    assert api.post("/api/verdict", json={"ticket": "PROJ-60096", "verdict": "rejected"}).status_code == 404
    assert len(lines(env, "verdicts.jsonl")) == 1


def test_writes_need_json_and_the_same_origin(api, env):
    ok = {"ticket": "PROJ-77", "verdict": "accepted"}
    assert api.post("/api/verdict", content=b"x=1", headers={"content-type": "text/plain"}).status_code == 415
    assert api.post("/api/verdict", json=ok, headers={"origin": "https://evil.example.com"}).status_code == 403
    assert api.post("/api/verdict", json=ok, headers={"origin": "http://127.0.0.1:8790"}).status_code == 200
    assert api.post("/api/defect", json={"ticket": "PROJ-77", "date": "2026-11-01", "roles": ["reviewer"]}, headers={"origin": "https://evil.example.com"}).status_code == 403
    assert len(lines(env, "verdicts.jsonl")) == 1 and not (env.home / "defects.jsonl").exists()


def test_a_defect_report_is_validated_and_appended(api, env):
    good = {"ticket": "PROJ-77", "date": "2026-11-01", "roles": ["reviewer", "reviewer", "builder"], "note": "found in beta"}
    r = api.post("/api/defect", json=good)
    assert r.status_code == 200 and lines(env, "defects.jsonl")[0]["roles"] == ["reviewer", "builder"]       # a role is listed once
    assert gold.defects("PROJ-77")[0]["date"] == "2026-11-01" and gold.defects("PROJ-1") == []
    for bad in ({**good, "date": "01/11/2026"}, {**good, "date": "2026-13-45"}, {**good, "roles": []}, {**good, "note": "n" * 201}, {**good, "roles": ["NOT OK"]}, {**good, "ticket": "nope"}):
        assert api.post("/api/defect", json=bad).status_code == 422, bad
    assert len(lines(env, "defects.jsonl")) == 1


def test_confirming_or_dismissing_a_deception_flag(api, env):
    # a deception flag exists only on a score line; write one for the run
    (env.home).mkdir(parents=True, exist_ok=True)
    (env.home / "scores.jsonl").write_text(json.dumps({"task_id": "S1:a1", "rev": 1, "flags": ["deception"], "flag_evidence": {"deception": {"suspected": True}}, "S": 0.5, "role": "builder"}) + "\n")
    assert api.post("/api/flags/decide", json={"run_id": "S1:a1", "flag": "deception", "decision": "maybe"}).status_code == 422
    assert api.post("/api/flags/decide", json={"run_id": "S1:a1", "flag": "overthinking", "decision": "confirm"}).status_code == 422
    assert api.post("/api/flags/decide", json={"run_id": "nope", "flag": "deception", "decision": "confirm"}).status_code == 404
    assert api.post("/api/flags/decide", json={"run_id": "S1:a1", "flag": "deception", "decision": "confirm"}).status_code == 200
    assert api.post("/api/flags/decide", json={"run_id": "S1:a1", "flag": "deception", "decision": "dismiss"}).status_code == 200
    assert gold.decisions() == {"S1:a1": "dismiss"} and len(lines(env, "flag_decisions.jsonl")) == 2
