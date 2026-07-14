from datetime import datetime, timezone
import os
from types import SimpleNamespace

import boto3
from google.cloud import logging as cloud_logging

from src.log_tracing import fetchers


def test_aws_fetch_uses_session_token_and_redacts_log_message(monkeypatch):
    captured = {}

    class Client:
        def filter_log_events(self, **kwargs):
            return {
                "events": [
                    {
                        "timestamp": 1_700_000_000_000,
                        "message": "api_key=must-not-leak",
                    }
                ]
            }

    def client(service, **kwargs):
        captured.update(service=service, kwargs=kwargs)
        return Client()

    monkeypatch.setattr(boto3, "client", client)

    result = fetchers.fetch_aws_logs(
        {"L1": "/aws/lambda/factory-l1-dispatcher"},
        "TRACE-1234ABCD",
        1,
        {
            "aws_access_key_id": "key",
            "aws_secret_access_key": "secret",
            "aws_session_token": "session",
            "aws_region": "eu-central-1",
        },
    )

    assert captured["service"] == "logs"
    assert captured["kwargs"]["aws_session_token"] == "session"
    assert len(result.entries) == 1
    assert "must-not-leak" not in result.entries[0].message


def test_gcp_fetch_uses_explicit_credentials_without_mutating_environment(
    monkeypatch,
    tmp_path,
):
    captured = {}
    parsed_credentials = object()

    def parse(value):
        captured["credentials_input"] = value
        return {}, {}, parsed_credentials

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def list_entries(self, **kwargs):
            captured["query"] = kwargs
            return [
                SimpleNamespace(
                    payload="trace observed",
                    timestamp=datetime.now(timezone.utc),
                    resource=SimpleNamespace(
                        labels={"service_name": "factory-l2-persister"}
                    ),
                )
            ]

    monkeypatch.setattr(fetchers, "parse_gcp_service_account", parse)
    monkeypatch.setattr(cloud_logging, "Client", Client)
    previous = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    result = fetchers.fetch_gcp_logs(
        "factory-project",
        "TRACE-1234ABCD",
        {"gcp_credentials_file": "credentials.json"},
        tmp_path,
        datetime.now(timezone.utc),
    )

    assert captured["credentials_input"] == str(tmp_path / "credentials.json")
    assert captured["client"]["credentials"] is parsed_credentials
    assert 'AND (textPayload:"TRACE-1234ABCD"' in captured["query"]["filter_"]
    assert captured["query"]["timeout"] == 15
    assert os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") == previous
    assert result.entries[0].layer == "L2"


def test_fetcher_error_diagnostics_are_redacted(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("azure_client_secret=sensitive-value")

    monkeypatch.setattr(boto3, "client", fail)

    result = fetchers.fetch_aws_logs({}, "TRACE-1234ABCD", 1, {})

    assert result.error is not None
    assert "sensitive-value" not in result.error


def test_azure_partial_results_are_retained(monkeypatch):
    from azure.monitor import query as monitor_query

    captured = {}

    class Credential:
        def __init__(self, **kwargs):
            pass

    class Client:
        def __init__(self, credential):
            pass

        def query_workspace(self, workspace_id, query, **kwargs):
            captured.update(workspace_id=workspace_id, query=query, kwargs=kwargs)
            return SimpleNamespace(
                partial_data=[
                    SimpleNamespace(
                        rows=[
                            [
                                datetime.now(timezone.utc),
                                "trace observed",
                                "factory-l2-persister",
                            ]
                        ]
                    )
                ],
                partial_error="query partially completed",
            )

    monkeypatch.setattr("azure.identity.ClientSecretCredential", Credential)
    monkeypatch.setattr(monitor_query, "LogsQueryClient", Client)
    started_at = datetime.now(timezone.utc)

    result = fetchers.fetch_azure_logs(
        "workspace",
        "TRACE-1234ABCD",
        {
            "azure_tenant_id": "tenant",
            "azure_client_id": "client",
            "azure_client_secret": "secret",
        },
        started_at,
    )

    assert len(result.entries) == 1
    assert result.entries[0].layer == "L2"
    assert result.error == "query partially completed"
    assert "isfuzzy=true" in captured["query"]
    assert captured["kwargs"]["timespan"][0] == started_at
