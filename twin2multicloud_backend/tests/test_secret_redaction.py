import pytest

from src.services.secret_redaction import redact_secret_like_text


@pytest.mark.parametrize(
    "path",
    [
        "/Users/caroline/private_key.json",
        "/home/developer/.config/cloud/credentials.json",
        r"C:\Users\developer\.azure\accessTokens.json",
    ],
)
def test_redact_secret_like_text_removes_local_home_paths(path):
    redacted = redact_secret_like_text(f"Credential source: {path}")

    assert path not in redacted
    assert "[REDACTED_PATH]" in redacted
