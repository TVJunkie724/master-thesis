from src.api.routes.sse import LogSession, SessionState


def test_log_session_complete_event_carries_operation_metadata():
    session = LogSession("twin-1", "session-1", operation_type="deploy")

    session.on_complete(
        success=False,
        message="Deployment failed",
        operation_id="op-123",
        error_code="DEPLOYMENT_ERROR",
    )

    event = session.queue.get_nowait()
    assert session.state == SessionState.COMPLETED
    assert event["type"] == "error"
    assert event["operation_id"] == "op-123"
    assert event["error_code"] == "DEPLOYMENT_ERROR"
    assert session.logs[-1] == event
