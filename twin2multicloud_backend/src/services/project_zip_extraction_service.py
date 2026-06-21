"""Project ZIP extraction use case for Step-3 wizard auto-population."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.repositories.twin_repository import TwinRepository
from src.services.scene_glb_service import SceneGlbService
from src.services.service_errors import EntityNotFoundError, ValidationError


logger = logging.getLogger(__name__)

MAX_PROJECT_ZIP_SIZE_BYTES = 100 * 1024 * 1024


def empty_zip_extraction_response(validation_error: str) -> dict[str, Any]:
    """Return the stable empty upload-zip response shape."""
    return {
        "success": False,
        "validation_errors": [validation_error],
        "files": {},
        "functions": {"processors": {}, "event_actions": {}, "event_feedback": None},
        "assets": {"scene_glb": None},
        "warnings": [],
    }


class ProjectZipExtractionService:
    """Owns project.zip validation/extraction proxying and extracted GLB storage."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        scene_glb_service: SceneGlbService,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.scene_glb_service = scene_glb_service

    async def upload_project_zip(self, twin_id: str, user_id: str, zip_content: bytes) -> dict[str, Any]:
        """Proxy project.zip to Deployer and normalize the extraction response."""
        twin = self.twin_repository.get_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        if len(zip_content) > MAX_PROJECT_ZIP_SIZE_BYTES:
            raise ValidationError(
                "File too large. Maximum allowed size is 100MB, "
                f"got {len(zip_content) / (1024 * 1024):.1f}MB"
            )

        validation_context = self._build_validation_context(twin)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.DEPLOYER_URL}/validate/zip/extract",
                    files={"file": ("project.zip", zip_content, "application/zip")},
                    params={
                        "validation_context": json.dumps(validation_context),
                        "include_credentials": False,
                    },
                )
        except httpx.ConnectError:
            return empty_zip_extraction_response("Cannot connect to Deployer API. Is it running?")
        except httpx.RequestError as exc:
            return empty_zip_extraction_response(f"Request error: {str(exc)}")

        if response.status_code != 200:
            return empty_zip_extraction_response(f"Deployer error: {response.text}")

        result = response.json()
        self._save_scene_glb_if_present(twin_id, user_id, result)
        return result

    def _build_validation_context(self, twin) -> dict[str, Any]:
        validation_context: dict[str, Any] = {
            "skip_credentials": True,
            "skip_config_files": [],
        }

        if not twin.optimizer_config:
            return validation_context

        opt_config = twin.optimizer_config
        calc_result = self._parse_calculation_result(opt_config.result_json)

        l2 = self._resolve_layer(opt_config.cheapest_l2, calc_result, "L2")
        l4 = self._resolve_layer(opt_config.cheapest_l4, calc_result, "L4")
        if l2:
            validation_context["l2_provider"] = l2
        if l4:
            validation_context["l4_provider"] = l4
        logger.info(
            "upload-zip: resolved providers for twin %s - l2=%s, l4=%s (columns: l2=%s l4=%s)",
            twin.id,
            l2,
            l4,
            opt_config.cheapest_l2,
            opt_config.cheapest_l4,
        )
        return validation_context

    @staticmethod
    def _parse_calculation_result(result_json: str | None) -> dict[str, Any]:
        if not result_json:
            return {}
        try:
            return (json.loads(result_json) or {}).get("calculationResult", {}) or {}
        except (ValueError, TypeError):
            return {}

    @staticmethod
    def _resolve_layer(column_value: str | None, calc_result: dict[str, Any], calc_key: str) -> str | None:
        if column_value:
            return column_value.lower()
        raw = calc_result.get(calc_key)
        return raw.lower() if isinstance(raw, str) and raw else None

    def _save_scene_glb_if_present(self, twin_id: str, user_id: str, result: dict[str, Any]) -> None:
        assets = result.get("assets") or {}
        scene_glb = assets.get("scene_glb") or {}
        if not scene_glb.get("exists"):
            return
        if not (scene_glb.get("content") and scene_glb.get("is_binary")):
            return

        try:
            glb_bytes = base64.b64decode(scene_glb["content"])
            self.scene_glb_service.upload_scene_glb(twin_id=twin_id, user_id=user_id, content=glb_bytes)
            result.setdefault("assets", {})["scene_glb"] = {
                "exists": True,
                "saved": True,
                "is_binary": True,
                "content": None,
            }
        except Exception as exc:
            result["warnings"] = result.get("warnings", []) + [f"Failed to save GLB: {str(exc)}"]
