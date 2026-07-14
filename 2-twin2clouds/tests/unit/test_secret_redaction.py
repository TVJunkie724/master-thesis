import logging

import pytest

from backend.logger import RedactingColoredFormatter
from backend.secret_redaction import REDACTED, redact_secret_like_text


@pytest.mark.parametrize(
    "message, secret",
    [
        ("aws_secret_access_key=super-secret-value", "super-secret-value"),
        ("Authorization: Bearer token-value-12345", "token-value-12345"),
        (
            'payload={"private_key_id": "private-key-identifier"}',
            "private-key-identifier",
        ),
        (
            "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----",
            "private-material",
        ),
    ],
)
def test_secret_redaction_covers_supported_secret_shapes(message, secret):
    redacted = redact_secret_like_text(message)

    assert secret not in redacted
    assert REDACTED in redacted


def test_console_formatter_redacts_interpolated_log_arguments():
    record = logging.LogRecord(
        name="optimizer",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Provider failed with client_secret=%s",
        args=("sensitive-client-secret",),
        exc_info=None,
    )
    formatter = RedactingColoredFormatter("%(levelname)s %(message)s")

    rendered = formatter.format(record)

    assert "sensitive-client-secret" not in rendered
    assert REDACTED in rendered
