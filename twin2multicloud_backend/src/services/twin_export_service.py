"""Twin configuration export use cases."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from src.models.twin import DigitalTwin, TwinState
from src.services import deployment_service
from src.services.service_errors import EntityNotFoundError


REDACTED = "__REDACTED__"


@dataclass(frozen=True)
class TwinExportArchive:
    """Prepared redacted twin export archive for an HTTP adapter."""

    content: io.BytesIO
    filename: str
    media_type: str = "application/zip"


class TwinExportService:
    """Build redacted debug/backup exports for user-owned twins."""

    def __init__(self, db: Session):
        self.db = db

    def export_twin(self, twin_id: str, user_id: str) -> TwinExportArchive:
        """Build a redacted configuration archive without plaintext credentials."""
        twin = self._load_twin(twin_id, user_id)
        zip_buffer = io.BytesIO()
        deployer_config = twin.deployer_config

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            providers = deployment_service._build_providers_config(twin)
            self._add_redacted_config_files(archive, twin, providers)
            deployment_service._add_hierarchy_files(archive, deployer_config)
            deployment_service._add_state_machine_file(archive, deployer_config, twin.optimizer_config)
            deployment_service._add_user_functions(archive, deployer_config, providers)
            deployment_service._add_scene_files(archive, deployer_config, providers, twin.id)

            if deployer_config and deployer_config.payloads_json:
                archive.writestr("iot_device_simulator/payloads.json", deployer_config.payloads_json)

        zip_buffer.seek(0)
        return TwinExportArchive(
            content=zip_buffer,
            filename=f"{twin.name.lower().replace(' ', '-')}_config.zip",
        )

    def _load_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = (
            self.db.query(DigitalTwin)
            .options(
                joinedload(DigitalTwin.deployer_config),
                joinedload(DigitalTwin.optimizer_config),
                joinedload(DigitalTwin.configuration),
            )
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .first()
        )
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _add_redacted_config_files(self, archive: zipfile.ZipFile, twin: DigitalTwin, providers: dict) -> None:
        deployer_config = twin.deployer_config
        optimizer_config = twin.optimizer_config

        archive.writestr("config.json", json.dumps(deployment_service._build_main_config(twin), indent=2))
        archive.writestr("config_providers.json", json.dumps(providers, indent=2))
        archive.writestr("config_credentials.json", json.dumps(self._redacted_credentials_config(twin), indent=2))

        if deployer_config:
            deployment_service._write_if_present(archive, "config_iot_devices.json", deployer_config.config_iot_devices_json)
            deployment_service._write_if_present(archive, "config_events.json", deployer_config.config_events_json)
            deployment_service._write_if_present(archive, "config_user.json", deployer_config.user_config_content)

        if optimizer_config:
            archive.writestr(
                "config_optimization.json",
                json.dumps(deployment_service._build_optimization_config(optimizer_config), indent=2),
            )

    @staticmethod
    def _redacted_credentials_config(twin: DigitalTwin) -> dict:
        config = twin.configuration
        if not config:
            return {}

        result = {}
        if config.aws_access_key_id:
            result["aws"] = {
                "aws_access_key_id": REDACTED,
                "aws_secret_access_key": REDACTED,
                "aws_region": config.aws_region or "eu-central-1",
                "aws_sso_region": config.aws_sso_region or "",
            }
            if config.aws_session_token:
                result["aws"]["aws_session_token"] = REDACTED

        if config.azure_subscription_id:
            azure_region = config.azure_region or "westeurope"
            result["azure"] = {
                "azure_subscription_id": REDACTED,
                "azure_tenant_id": REDACTED,
                "azure_client_id": REDACTED,
                "azure_client_secret": REDACTED,
                "azure_region": azure_region,
                "azure_region_iothub": config.azure_region_iothub or azure_region,
                "azure_region_digital_twin": config.azure_region_digital_twin or azure_region,
            }

        if config.gcp_project_id:
            result["gcp"] = {
                "gcp_project_id": config.gcp_project_id,
                "gcp_region": config.gcp_region or "europe-west1",
            }
            if config.gcp_billing_account:
                result["gcp"]["gcp_billing_account"] = REDACTED
            if config.gcp_service_account_json:
                result["gcp"]["gcp_credentials_file"] = None
                result["gcp"]["gcp_service_account_json"] = REDACTED

        return result
