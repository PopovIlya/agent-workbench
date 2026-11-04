"""`python -m agent_scoring agent-score` is registered and its options are the ones the task names."""

import pytest

from agent_scoring import __main__ as cli


def test_agent_score_is_a_registered_command_with_the_named_options(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["agent-score", "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for opt in ("--since", "--ticket", "--rescore", "--roles-ref", "--scores"):
        assert opt in out


def test_agent_score_writes_to_a_given_scores_path_and_prints_a_summary(tmp_path, monkeypatch, capsys):
    from agent_scoring import agent_score
    called = {}

    def fake_run(repo, **kw):
        called.update(kw)
        return {"written": 0, "stats": {"unchanged": 0}, "lines": []}
    monkeypatch.setattr(agent_score, "run_scoring", fake_run)
    p = tmp_path / "s.jsonl"
    assert cli.main(["agent-score", "--since", "2026-10-01", "--ticket", "PROJ-200", "--rescore", "--scores", str(p)]) == 0
    assert called["since"] == "2026-10-01" and called["ticket"] == "PROJ-200" and called["rescore"] is True and called["scores_path"] == p
    assert "agent-score: 0 line(s) written" in capsys.readouterr().out
