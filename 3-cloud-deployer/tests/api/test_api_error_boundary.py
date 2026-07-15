"""Tests for the canonical REST error redaction boundary."""

import asyncio
import json
from unittest.mock import patch

from starlette.requests import Request

import rest_api
from src.api.error_handling import internal_server_error, safe_error_detail


def test_expected_error_detail_is_redacted():
    detail = safe_error_detail(
        RuntimeError(
            "project /app/upload/factory client_secret=super-secret-value"
        )
    )

    assert detail == "project <project-path> client_secret=<redacted>"


def test_internal_error_logs_redacted_context_and_returns_generic_detail():
    with patch("src.api.error_handling.logger.error") as log_error:
        error = internal_server_error(
            "Project import",
            RuntimeError("access_token=super-secret-value"),
        )

    assert error.status_code == 500
    assert error.detail == "Internal server error. Check logs."
    assert log_error.call_args.args == (
        "%s failed: %s",
        "Project import",
        "access_token=<redacted>",
    )
    assert log_error.call_args.kwargs["extra"] == {"error_type": "RuntimeError"}
    assert log_error.call_args.kwargs["exc_info"] is False


def test_global_exception_handler_returns_generic_fastapi_envelope():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/internal",
            "headers": [],
            "query_string": b"",
        }
    )

    with patch("src.api.error_handling.logger.error") as log_error:
        response = asyncio.run(
            rest_api.unhandled_exception_handler(
                request,
                RuntimeError("api_key=must-not-leak /app/upload/factory"),
            )
        )

    assert response.status_code == 500
    assert json.loads(response.body) == {
        "detail": "Internal server error. Check logs.",
    }
    assert log_error.call_args.args[2] == "api_key=<redacted> <project-path>"


def test_openapi_error_schema_matches_fastapi_detail_envelope():
    schema = rest_api.app.openapi()
    error_schema = schema["paths"]["/projects"]["get"]["responses"]["500"][
        "content"
    ]["application/json"]["schema"]

    assert error_schema == {
        "$ref": "#/components/schemas/HttpErrorEnvelope",
    }
