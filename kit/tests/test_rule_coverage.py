import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import rule_coverage  # noqa: E402


def rule(rule_id: str, status: str, scope: str = "") -> str:
    return f"### {rule_id}\n- status: {status}\n- statement: x\n- source: y\n- scope: {scope}\n- tests: none\n\n"


def make_repo(tmp_path: Path, area_md: str, tests: dict[str, str] | None = None) -> Path:
    (tmp_path / "docs" / "requirements").mkdir(parents=True)
    (tmp_path / "docs" / "requirements" / "audit.md").write_text("# Requirements: audit\n\n" + area_md)
    for name, body in (tests or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return tmp_path


def run(repo: Path, *args: str) -> int:
    return rule_coverage.main([str(repo), *args])


def test_confirmed_rule_without_test_fails(tmp_path, capsys):
    repo = make_repo(tmp_path, rule("AUDIT-001", "confirmed"))
    assert run(repo) == 1
    assert "AUDIT-001" in capsys.readouterr().out


def test_new_rule_without_test_fails(tmp_path):
    repo = make_repo(tmp_path, rule("AUDIT-001", "new"))
    assert run(repo) == 1


def test_rules_with_tests_pass(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new") + rule("AUDIT-002", "confirmed"),
        {"pkg/tests/test_a.py": "# rule: AUDIT-001, AUDIT-002\ndef test_a():\n    pass\n"},
    )
    assert run(repo) == 0


def test_observed_rules_are_ignored(tmp_path):
    repo = make_repo(tmp_path, rule("AUDIT-001", "observed"))
    assert run(repo) == 0


def test_test_with_unknown_id_fails_only_in_strict(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new"),
        {"tests/test_a.py": "# rule: AUDIT-001\n# rule: AUDIT-999\n"},
    )
    assert run(repo) == 0
    assert run(repo, "--strict") == 1


def test_unknown_id_is_named_in_output(tmp_path, capsys):
    repo = make_repo(tmp_path, "", {"tests/test_a.py": "# rule: AUDIT-999\n"})
    run(repo)
    out = capsys.readouterr().out
    assert "UNKNOWN" in out
    assert "AUDIT-999" in out
    assert "tests/test_a.py:1" in out


def test_retired_rule_is_reported_and_test_on_it_is_flagged(tmp_path, capsys):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "retired"),
        {"tests/test_a.py": "# rule: AUDIT-001\n"},
    )
    assert run(repo) == 0
    out = capsys.readouterr().out
    assert "Retired rules: AUDIT-001" in out
    assert "RETIRED" in out
    assert run(repo, "--strict") == 1


def test_scope_filter_limits_what_must_have_tests(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new", "6.3") + rule("AUDIT-002", "new", "6.2"),
        {"tests/test_a.py": "# rule: AUDIT-001\n"},
    )
    assert run(repo) == 1
    assert run(repo, "--scope", "6.3") == 0
    assert run(repo, "--scope", "6.2") == 1


def test_per_area_counts(tmp_path, capsys):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "observed") + rule("AUDIT-002", "observed") + rule("AUDIT-003", "new"),
        {"tests/test_a.py": "# rule: AUDIT-003\n"},
    )
    run(repo)
    assert "audit: observed=2, new=1" in capsys.readouterr().out


def test_questions_file_is_not_an_area(tmp_path, capsys):
    repo = make_repo(tmp_path, rule("AUDIT-001", "observed"))
    (repo / "docs" / "requirements" / "QUESTIONS.md").write_text("### AUDIT-009\n- status: new\n")
    run(repo)
    assert "Rules: 1" in capsys.readouterr().out


def test_comments_outside_tests_are_ignored(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new"),
        {"src/app.py": "# rule: AUDIT-001\n"},
    )
    assert run(repo) == 1


def test_missing_requirements_dir_is_an_error(tmp_path):
    assert run(tmp_path) == 2


def test_invalid_status_is_flagged_in_strict(tmp_path):
    repo = make_repo(tmp_path, rule("AUDIT-001", "maybe"))
    assert run(repo) == 0
    assert run(repo, "--strict") == 1


@pytest.mark.parametrize("line", ["    # rule: AUDIT-001", "# rule:AUDIT-001", "x = 1  # rule: AUDIT-001"])
def test_comment_forms(tmp_path, line):
    repo = make_repo(tmp_path, rule("AUDIT-001", "new"), {"tests/test_a.py": line + "\n"})
    assert run(repo) == 0


def test_strict_fails_on_confirmed_or_new_rule_without_scope(tmp_path, capsys):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new") + rule("AUDIT-002", "confirmed", "6.3"),
        {"tests/test_a.py": "# rule: AUDIT-001, AUDIT-002\n"},
    )
    assert run(repo) == 0
    assert run(repo, "--strict") == 1
    assert "WITHOUT a scope" in capsys.readouterr().out


def test_strict_passes_when_every_confirmed_or_new_rule_has_scope(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new", "6.3") + rule("AUDIT-002", "observed"),
        {"tests/test_a.py": "# rule: AUDIT-001\n"},
    )
    assert run(repo, "--strict", "--scope", "6.3") == 0


def test_strict_scope_check_covers_rules_outside_the_scope_filter(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new", "6.3") + rule("AUDIT-002", "new"),
        {"tests/test_a.py": "# rule: AUDIT-001\n"},
    )
    assert run(repo, "--strict", "--scope", "6.3") == 1


def read_map(repo: Path) -> str:
    return (repo / "docs" / "requirements" / "audit.md").read_text()


def test_write_tests_fills_the_field_from_the_markers(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new", "6.3") + rule("AUDIT-002", "new", "6.3") + rule("AUDIT-003", "observed"),
        {
            "pkg/tests/test_b.py": "# rule: AUDIT-001\n",
            "pkg/tests/test_a.py": "# rule: AUDIT-001, AUDIT-002\n# rule: AUDIT-001\n",
        },
    )
    assert run(repo, "--write-tests") == 0
    text = read_map(repo)
    assert "- tests: pkg/tests/test_a.py, pkg/tests/test_b.py" in text
    assert "- tests: pkg/tests/test_a.py\n" in text
    assert "- tests: none" in text


def test_write_tests_is_idempotent_and_keeps_the_rest_of_the_file(tmp_path, capsys):
    repo = make_repo(tmp_path, rule("AUDIT-001", "new", "6.3"), {"tests/test_a.py": "# rule: AUDIT-001\n"})
    run(repo, "--write-tests")
    first = read_map(repo)
    capsys.readouterr()
    run(repo, "--write-tests")
    assert read_map(repo) == first
    assert "written for 0 rule(s)" in capsys.readouterr().out
    assert first.startswith("# Requirements: audit\n")
    assert "- statement: x\n- source: y\n- scope: 6.3\n" in first


def test_write_tests_sets_none_when_the_marker_is_gone(tmp_path):
    repo = make_repo(tmp_path, rule("AUDIT-001", "new", "6.3"), {"tests/test_a.py": "# rule: AUDIT-001\n"})
    run(repo, "--write-tests")
    (repo / "tests" / "test_a.py").write_text("def test_a():\n    pass\n")
    run(repo, "--write-tests")
    assert "- tests: none" in read_map(repo)


def test_write_tests_adds_a_missing_field(tmp_path):
    repo = make_repo(tmp_path, "### AUDIT-001\n- status: new\n- statement: x\n- scope: 6.3\n- notes: n\n\n",
                     {"tests/test_a.py": "# rule: AUDIT-001\n"})
    run(repo, "--write-tests")
    assert "- scope: 6.3\n- notes: n\n- tests: tests/test_a.py\n" in read_map(repo)


def test_write_tests_with_scope_leaves_other_scopes_alone(tmp_path):
    repo = make_repo(
        tmp_path,
        rule("AUDIT-001", "new", "6.3") + rule("AUDIT-002", "new", "6.2"),
        {"tests/test_a.py": "# rule: AUDIT-001, AUDIT-002\n"},
    )
    run(repo, "--write-tests", "--scope", "6.3")
    text = read_map(repo)
    assert text.count("- tests: tests/test_a.py") == 1
    assert "- tests: none" in text


def test_unproven_tests_path_is_reported_and_fails_only_in_strict(tmp_path, capsys):
    repo = make_repo(
        tmp_path,
        "### AUDIT-001\n- status: new\n- statement: x\n- source: y\n- scope: 6.3\n- tests: tests/test_gone.py\n\n",
        {"tests/test_a.py": "# rule: AUDIT-001\n"},
    )
    assert run(repo) == 0
    assert "no `# rule:` marker" in capsys.readouterr().out
    assert run(repo, "--strict") == 1
    assert run(repo, "--strict", "--write-tests") == 0


def test_outdated_field_is_reported_but_does_not_fail(tmp_path, capsys):
    repo = make_repo(tmp_path, rule("AUDIT-001", "new", "6.3"), {"tests/test_a.py": "# rule: AUDIT-001\n"})
    assert run(repo, "--strict") == 0
    assert "run --write-tests" in capsys.readouterr().out
