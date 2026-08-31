"""Tests for the narrow AWS Phase 8 account prerequisite helper."""

from __future__ import annotations

from scripts import manage_phase8_aws_outbound_identity as helper


class FakeIam:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.enable_calls = 0
        self.disable_calls = 0

    def get_outbound_web_identity_federation_info(self):
        if not self.enabled:
            error = helper.ClientError(
                {
                    "Error": {
                        "Code": "FeatureDisabled",
                        "Message": "disabled for sensitive-account-id",
                    }
                },
                "GetOutboundWebIdentityFederationInfo",
            )
            raise error
        return {
            "JwtVendingEnabled": True,
            "IssuerIdentifier": "must-not-enter-record",
        }

    def enable_outbound_web_identity_federation(self):
        self.enable_calls += 1
        self.enabled = True
        return {}

    def disable_outbound_web_identity_federation(self):
        self.disable_calls += 1
        self.enabled = False
        return {}


def test_enable_is_idempotent_and_redacted() -> None:
    client = FakeIam(enabled=False)
    record = helper.manage(client, "enable")
    assert client.enable_calls == 1
    assert record["status_before"] == "disabled"
    assert record["status_after"] == "enabled"
    assert record["mutation_performed"] is True
    assert "must-not-enter-record" not in helper._canonical_json(record)

    second = helper.manage(client, "enable")
    assert client.enable_calls == 1
    assert second["mutation_performed"] is False


def test_disable_is_explicit_final_cleanup() -> None:
    client = FakeIam(enabled=True)
    record = helper.manage(client, "disable")
    assert client.disable_calls == 1
    assert record["status_after"] == "disabled"
    assert record["cleanup_requirement"] == "complete"


def test_safe_error_code_excludes_provider_message() -> None:
    error = helper.ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "sensitive-account-id"}},
        "EnableOutboundWebIdentityFederation",
    )
    assert helper._safe_error_code(error) == "ACCESSDENIED"


def test_unknown_response_schema_fails_closed() -> None:
    client = FakeIam(enabled=True)
    client.get_outbound_web_identity_federation_info = lambda: {"Status": "ENABLED"}
    assert helper._status(client) == "unknown"
