from datetime import datetime, timezone
import json

from src.models.pricing_refresh_run import PricingRefreshRun
from src.models.pricing_review import PricingCandidateReport, PricingReviewDecision
from src.models.user import User


def _current_user_id(db_session) -> str:
    user = db_session.query(User).first()
    assert user is not None
    return user.id


def _insert_refresh_run(
    db_session,
    *,
    user_id: str,
    provider: str = "aws",
    result_summary: dict | None = None,
) -> PricingRefreshRun:
    run = PricingRefreshRun(
        id=f"run-{provider}-{len(db_session.query(PricingRefreshRun).all()) + 1}",
        user_id=user_id,
        provider=provider,
        status="succeeded",
        pricing_connection_id=None,
        force=True,
        credential_summary_json=json.dumps(
            {
                "connection_id": None,
                "identity_label": "Test Pricing Access",
                "scope": "public",
                "provider_account_id": None,
                "provider_project_id": None,
                "provider_subscription_id": None,
            }
        ),
        result_summary_json=json.dumps(result_summary or _result_summary()),
        created_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def _result_summary() -> dict:
    return {
        "__schema__": {
            "provider": "aws",
            "schema_version": "pricing-schema.v1",
            "private_key": "SHOULD_NOT_LEAK_FROM_SCHEMA",
        },
        "__quality__": {
            "field_sources": {
                "iotCore.pricePerDeviceAndMonth": "fetched",
                "iotCore.priceRulesTriggered": "fallback_static",
                "lambda.requestPrice": "derived",
            }
        },
        "iotCore": {
            "pricePerDeviceAndMonth": 0.1,
            "priceRulesTriggered": 0.2,
            "secret_access_key": "SHOULD_NOT_LEAK_FROM_VALUE",
        },
        "lambda": {"requestPrice": 0.0000002},
    }


def test_candidate_reports_generated_from_quality_metadata(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    run = _insert_refresh_run(db_session, user_id=_current_user_id(db_session))

    response = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "pricing-candidate-report-list.v1"
    assert body["provider"] == "aws"
    assert body["refresh_run_id"] == run.id
    assert len(body["reports"]) == 3

    by_intent = {report["intent_id"]: report for report in body["reports"]}
    fetched = by_intent["iotCore.pricePerDeviceAndMonth"]
    assert fetched["schema_version"] == "pricing-candidate-report.v1"
    assert fetched["review_state"] == "ready"
    assert fetched["source_status"] == "quality_metadata"
    assert fetched["deterministic_selection"]["selectable"] is True
    assert fetched["candidates"][0]["value"] == 0.1

    fallback = by_intent["iotCore.priceRulesTriggered"]
    assert fallback["review_state"] == "needs_review"
    assert fallback["deterministic_selection"]["selectable"] is False
    assert fallback["candidates"] == []
    assert "fallback_static" in fallback["source_warning"]

    assert db_session.query(PricingCandidateReport).count() == 3


def test_candidate_report_detail_and_trace_are_secret_free(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    run = _insert_refresh_run(db_session, user_id=_current_user_id(db_session))
    reports = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    ).json()["reports"]
    report_id = next(
        report["report_id"]
        for report in reports
        if report["intent_id"] == "iotCore.pricePerDeviceAndMonth"
    )

    detail = client.get(
        f"/optimizer/pricing-review/candidate-reports/{report_id}",
        headers=headers,
    )
    trace = client.get(
        f"/optimizer/pricing-review/candidate-reports/{report_id}/trace",
        headers=headers,
    )

    assert detail.status_code == 200
    assert trace.status_code == 200
    trace_body = trace.json()
    assert trace_body["schema_version"] == "pricing-trace.v1"
    assert trace_body["sanitization"] == {
        "bounded": True,
        "secret_free": True,
        "omitted_raw_rows": 0,
    }
    assert any(
        check["check"] == "raw_provider_candidates"
        and check["status"] == "not_available"
        for check in trace_body["hard_checks"]
    )
    serialized = json.dumps({"detail": detail.json(), "trace": trace_body})
    assert "SHOULD_NOT_LEAK" not in serialized
    assert "private_key" not in serialized
    assert "secret_access_key" not in serialized


def test_review_decision_approval_requires_report_candidate(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    run = _insert_refresh_run(db_session, user_id=_current_user_id(db_session))
    report = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    ).json()["reports"][0]

    invalid = client.post(
        "/optimizer/pricing-review/decisions",
        json={
            "report_id": report["report_id"],
            "decision": "approve",
            "selected_candidate_id": "not-from-report",
        },
        headers=headers,
    )
    assert invalid.status_code == 400

    valid_candidate_id = report["candidates"][0]["candidate_id"]
    response = client.post(
        "/optimizer/pricing-review/decisions",
        json={
            "report_id": report["report_id"],
            "decision": "approve",
            "selected_candidate_id": valid_candidate_id,
            "rationale": "Reviewed against pricing evidence.",
        },
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "pricing-review-decision.v1"
    assert body["selected_candidate_id"] == valid_candidate_id
    assert db_session.query(PricingReviewDecision).count() == 1

    listed = client.get("/optimizer/pricing-review/decisions?provider=aws", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["schema_version"] == "pricing-review-decision-list.v1"
    assert listed.json()["decisions"][0]["decision_id"] == body["decision_id"]


def test_defer_decision_rejects_selected_candidate(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    run = _insert_refresh_run(db_session, user_id=_current_user_id(db_session))
    report = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    ).json()["reports"][0]

    invalid = client.post(
        "/optimizer/pricing-review/decisions",
        json={
            "report_id": report["report_id"],
            "decision": "defer",
            "selected_candidate_id": report["candidates"][0]["candidate_id"],
        },
        headers=headers,
    )
    assert invalid.status_code == 400

    valid = client.post(
        "/optimizer/pricing-review/decisions",
        json={"report_id": report["report_id"], "decision": "defer"},
        headers=headers,
    )
    assert valid.status_code == 200
    assert valid.json()["decision"] == "defer"


def test_candidate_reports_are_user_scoped(authenticated_client, db_session):
    client, headers = authenticated_client
    run = _insert_refresh_run(db_session, user_id="other-user")

    response = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    )

    assert response.status_code == 404


def test_provider_mismatch_returns_bad_request(authenticated_client, db_session):
    client, headers = authenticated_client
    run = _insert_refresh_run(
        db_session,
        user_id=_current_user_id(db_session),
        provider="azure",
    )

    response = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    )

    assert response.status_code == 400
    assert "provider does not match" in response.json()["detail"]


def test_missing_quality_metadata_returns_evidence_unavailable_report(
    authenticated_client,
    db_session,
):
    client, headers = authenticated_client
    run = _insert_refresh_run(
        db_session,
        user_id=_current_user_id(db_session),
        result_summary={"__schema__": {"provider": "aws"}},
    )

    response = client.get(
        f"/optimizer/pricing-review/aws/candidate-reports?refresh_run_id={run.id}",
        headers=headers,
    )

    assert response.status_code == 200
    reports = response.json()["reports"]
    assert len(reports) == 1
    assert reports[0]["review_state"] == "evidence_unavailable"
    assert reports[0]["source_status"] == "evidence_unavailable"
    assert reports[0]["candidates"] == []
