"""Test-only deployment support use cases.

This service is used only by endpoints behind ``ENABLE_TEST_ENDPOINTS``. It
keeps test orchestration out of FastAPI route handlers while preserving the
existing mock stream contracts for UI development.
"""

from __future__ import annotations

import asyncio
import io
import json
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models.optimizer_config import OptimizerConfiguration
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_stream_service import create_session
from src.services.provider_contract import provider_id_for_deployer_api
from src.services.service_errors import EntityNotFoundError


SessionCreator = Callable[[str, str, str], Awaitable[Any]]
TaskScheduler = Callable[[Awaitable[Any]], Any]
TestLogTraceRunner = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class MockSimulatorArchive:
    """In-memory mock simulator archive prepared for an HTTP adapter."""

    content: io.BytesIO
    filename: str
    media_type: str = "application/zip"


class TestDeploymentService:
    """Use cases for gated test-only deployment endpoints."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        session_creator: SessionCreator = create_session,
        task_scheduler: TaskScheduler = asyncio.create_task,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.session_creator = session_creator
        self.task_scheduler = task_scheduler

    async def start_log_trace(
        self,
        twin_id: str,
        user_id: str,
        *,
        duration: int,
        should_fail: bool,
        test_log_trace_runner: TestLogTraceRunner,
    ) -> dict[str, Any]:
        """Start a mock multi-cloud log trace and return the SSE contract."""
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")

        trace_id = f"TRACE-{uuid.uuid4().hex[:8].upper()}"
        providers = self._configured_providers(twin)

        session_id = str(uuid.uuid4())
        await self.session_creator(twin_id, session_id, "log_trace")
        self.task_scheduler(
            test_log_trace_runner(
                session_id=session_id,
                twin_id=twin_id,
                trace_id=trace_id,
                providers=providers,
                duration=duration,
                should_fail=should_fail,
            )
        )

        primary_provider = providers[0] if providers else "aws"
        return {
            "trace_id": trace_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "l1_provider": primary_provider,
            "providers": providers,
            "message": f"Test message sent to {primary_provider} IoT endpoint",
            "session_id": session_id,
            "sse_url": f"/sse/deploy/{session_id}",
        }

    def build_mock_simulator_archive(self, twin_id: str, user_id: str) -> MockSimulatorArchive:
        """Build the mock simulator archive used by UI development smoke flows."""
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")

        l1_provider = self._optimizer_l1_provider(twin_id)
        resource_name = self._resource_name(twin)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            config = {
                "project_id": "mock-project-id",
                "topic_name": f"projects/mock-project/topics/{resource_name}-telemetry",
                "device_id": "mock-device-1",
                "digital_twin_name": resource_name,
                "payload_path": "payloads.json",
                "service_account_key_path": "service_account.json",
            }
            archive.writestr("config.json", json.dumps(config, indent=2))

            payloads = [{"temperature": 25.5, "humidity": 60, "device_id": "mock-device-1"}]
            archive.writestr("payloads.json", json.dumps(payloads, indent=2))

            readme = f"""# IoT Device Simulator - {resource_name} ({l1_provider.upper()})

## [MOCK PACKAGE - FOR UI TESTING ONLY]

This is a mock simulator package generated for UI testing purposes.
In production, this package would contain the actual simulator code.

## Usage
```bash
pip install -r requirements.txt
python src/main.py --project {resource_name}
```
"""
            archive.writestr("README.md", readme)
            archive.writestr("requirements.txt", "google-cloud-pubsub>=2.0.0\n")
            archive.writestr("src/main.py", "# Mock simulator main.py\nprint('Mock simulator')\n")

        zip_buffer.seek(0)
        return MockSimulatorArchive(
            content=zip_buffer,
            filename=f"simulator_{resource_name}_{l1_provider}.zip",
        )

    @staticmethod
    def _configured_providers(twin) -> list[str]:
        providers = ["aws"]
        if not twin.deployer_config or not hasattr(twin.deployer_config, "layer_providers"):
            return providers

        layer_providers = twin.deployer_config.layer_providers or {}
        unique_providers = []
        for layer in ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider"]:
            provider = layer_providers.get(layer)
            if provider and provider not in unique_providers:
                unique_providers.append(provider)
        return unique_providers if unique_providers else providers

    def _optimizer_l1_provider(self, twin_id: str) -> str:
        optimizer_config = self.db.query(OptimizerConfiguration).filter_by(twin_id=twin_id).first()
        if optimizer_config and optimizer_config.cheapest_l1:
            return provider_id_for_deployer_api(optimizer_config.cheapest_l1)
        return "gcp"

    @staticmethod
    def _resource_name(twin) -> str:
        if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
            return twin.deployer_config.deployer_digital_twin_name
        return twin.name.lower().replace(" ", "-")
