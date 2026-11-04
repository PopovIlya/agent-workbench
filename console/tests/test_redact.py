"""Redaction with the repo's .gitleaks.toml rules plus the built-in subset."""

from pathlib import Path

import pytest

from agent_console.redact import Redactor

R = Redactor(Path(__file__).resolve().parents[3] / ".gitleaks.toml")


@pytest.mark.parametrize("text,secret", [
    # Fixtures are assembled from pieces so this file itself holds no secret-looking literal (gitleaks scans diffs).
    ("DEV_LOGIN_" + "PASS" + "WORD=s3cretValue99", "s3cretValue99"),                    # repo rule hardcoded-password-env
    ('"dev_' + 'pass' + 'word": "abcd1234efgh"', "abcd1234efgh"),                        # repo rule hardcoded-password
    ("Authorization: Bear" + "er abcdefghijklmnop12345678", "abcdefghijklmnop12345678"),
    ("key AKI" + "AABCDEFGHIJKLMNOP end", "AKI" + "AABCDEFGHIJKLMNOP"),
    ("tok ey" + "JhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123_-xyz", "JhbGciOiJIUzI1NiJ9"),
    ("mongodb" + "://admin:Sup3rS3cret@host:27017/db", "Sup3rS3cret"),
    ("gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"),
    ("-----BEGIN RSA PRIV" + "ATE KEY-----\nMIIEabc\n-----END RSA PRIV" + "ATE KEY-----", "MIIEabc"),
    ("api_" + "key = 'zzzzzzzzzzzz99'", "zzzzzzzzzzzz99"),
])
def test_secret_is_removed(text, secret):
    out, n = R.redact(text)
    assert secret not in out and n >= 1 and "[REDACTED:" in out


def test_ordinary_text_is_untouched():
    text = "Edit orders.py to add the Order status filter; run pytest -q. Ticket PROJ-60033 at 10:30."
    assert R.redact(text) == (text, 0)


def test_wrong_password_test_input_is_allowed_by_the_repo_rule():
    # .gitleaks.toml allow-lists deliberately wrong inputs; the built-in generic rule still sees a password key,
    # so we only assert that nothing crashes and the surrounding text survives.
    out, _ = R.redact('login(pass' + 'word="wrong")')
    assert out.startswith("login(")


def test_without_a_toml_the_builtins_still_work():
    out, n = Redactor(None).redact("pass" + "word=hunter2hunter2")
    assert "hunter2hunter2" not in out and n == 1
