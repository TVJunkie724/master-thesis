"""Closed-contract tests for telemetry terminal evidence."""

import pytest
from pydantic import ValidationError

from src.schemas.telemetry_verification import TelemetryVerificationEvidence


def _valid_evidence():
    return {
        "schema_version": "telemetry-verification.v1",
        "trace_id": "VERIFY-1234ABCD",
        "status": "pass",
        "pass_count": 3,
        "fail_count": 0,
        "skip_count": 0,
        "total_time": 1.5,
        "failed_phase": None,
        "evidence": [
            {"phase": 1, "kind": "message_accepted", "provider": "aws"},
            {
                "phase": 2,
                "kind": "trace_correlated_hot_record",
                "provider": "azure",
                "record_count": 1,
            },
            {
                "phase": 3,
                "kind": "gcp_twin_projection",
                "provider": "gcp",
                "correlation": "source_sequence",
            },
        ],
    }


def test_terminal_contract_accepts_exact_three_phase_roundtrip():
    evidence = TelemetryVerificationEvidence.model_validate(_valid_evidence())

    assert evidence.trace_id == "VERIFY-1234ABCD"
    assert [item.phase for item in evidence.evidence] == [1, 2, 3]


@pytest.mark.parametrize(
    "mutation",
    [
        {"client_secret": "forbidden"},
        {"trace_id": "invalid"},
        {"pass_count": 2},
        {"status": "fail"},
    ],
)
def test_terminal_contract_rejects_open_or_inconsistent_evidence(mutation):
    value = {**_valid_evidence(), **mutation}

    with pytest.raises(ValidationError):
        TelemetryVerificationEvidence.model_validate(value)
