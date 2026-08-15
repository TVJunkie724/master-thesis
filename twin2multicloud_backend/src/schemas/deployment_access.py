"""Closed Management API models for Layer Access and one-time rotation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Layer = Literal["l4", "l5"]
Provider = Literal["aws", "azure", "gcp"]
AuthMode = Literal[
    "aws_identity_center",
    "azure_entra",
    "gcp_iap",
    "generated_viewer",
]
CredentialAction = Literal["none", "rotate"]

SURFACE_MATRIX = {
    ("l4", "aws"): ("aws_iot_twinmaker", "aws_identity_center", "none"),
    ("l4", "azure"): ("azure_digital_twins", "azure_entra", "none"),
    ("l4", "gcp"): ("gcp_twin_explorer", "gcp_iap", "none"),
    ("l5", "aws"): ("aws_managed_grafana", "aws_identity_center", "none"),
    ("l5", "azure"): ("azure_managed_grafana", "azure_entra", "none"),
    ("l5", "gcp"): ("gcp_grafana_oss", "generated_viewer", "rotate"),
}
SUPPORTED_DEPLOYMENT_ACCESS_PROFILES = frozenset(
    {
        ("five-layer-baseline", "2"),
        ("six-layer-eventing", "1"),
    }
)


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LayerAccessAuth(_ClosedModel):
    mode: AuthMode
    principal_label: str = Field(min_length=1)
    credential_action: CredentialAction

    @field_validator("principal_label")
    @classmethod
    def label_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("principal_label must not be blank")
        return value


class LayerAccessReadiness(_ClosedModel):
    resource: Literal["ready", "failed", "pending"]
    access_binding: Literal["ready", "blocked", "pending"]
    content: Literal["ready", "failed", "pending"]
    data_probe: Literal["ready", "failed", "pending"]
    browser_sign_in: Literal["unverified", "verified", "failed"]


class DeploymentAccessSurface(_ClosedModel):
    layer: Layer
    provider: Provider
    service_id: Literal[
        "aws_iot_twinmaker",
        "azure_digital_twins",
        "gcp_twin_explorer",
        "aws_managed_grafana",
        "azure_managed_grafana",
        "gcp_grafana_oss",
    ]
    display_name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    auth: LayerAccessAuth
    readiness: LayerAccessReadiness
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("display_name must not be blank")
        return value

    @field_validator("url")
    @classmethod
    def url_must_be_secret_free_https(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("url must be absolute secret-free HTTPS")
        return value

    @field_validator("capabilities", "limitations")
    @classmethod
    def string_items_must_be_unique_and_non_blank(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("list values must not be blank")
        if len(value) != len(set(value)):
            raise ValueError("list values must be unique")
        return value

    @model_validator(mode="after")
    def provider_service_auth_must_match(self) -> "DeploymentAccessSurface":
        expected = SURFACE_MATRIX.get((self.layer, self.provider))
        actual = (
            self.service_id,
            self.auth.mode,
            self.auth.credential_action,
        )
        if expected != actual:
            raise ValueError("provider/service/auth combination is not supported")
        if not self.capabilities:
            raise ValueError("capabilities must not be empty")
        return self


class DeploymentAccessEvidence(_ClosedModel):
    schema_version: Literal["deployment-access-evidence.v1"]
    profile_id: Literal["five-layer-baseline", "six-layer-eventing"]
    profile_version: Literal["1", "2"]
    generated_at: datetime
    surfaces: tuple[DeploymentAccessSurface, DeploymentAccessSurface]

    @model_validator(mode="after")
    def contains_exact_l4_l5(self) -> "DeploymentAccessEvidence":
        if (
            self.profile_id,
            self.profile_version,
        ) not in SUPPORTED_DEPLOYMENT_ACCESS_PROFILES:
            raise ValueError("evidence profile/version is not supported")
        if [surface.layer for surface in self.surfaces] != ["l4", "l5"]:
            raise ValueError("evidence must contain ordered L4 and L5 surfaces")
        return self


class DeploymentAccessSnapshot(_ClosedModel):
    schema_version: Literal["deployment-access.v1"] = "deployment-access.v1"
    twin_id: str = Field(min_length=1)
    deployment_id: str = Field(min_length=1)
    generated_at: datetime
    availability: Literal["available", "unsupported"]
    reason_code: Literal["unsupported_historical_profile"] | None
    surfaces: tuple[DeploymentAccessSurface, ...]

    @model_validator(mode="after")
    def availability_shape_must_match(self) -> "DeploymentAccessSnapshot":
        layers = [surface.layer for surface in self.surfaces]
        if self.availability == "available":
            if self.reason_code is not None or layers != ["l4", "l5"]:
                raise ValueError("available snapshot must contain exact L4/L5 surfaces")
        elif self.reason_code is None or self.surfaces:
            raise ValueError("unsupported snapshot must contain a reason and no surfaces")
        return self


class DeploymentAccessCredential(_ClosedModel):
    schema_version: Literal["deployment-access-credential.v1"] = (
        "deployment-access-credential.v1"
    )
    layer: Literal["l5"] = "l5"
    provider: Literal["gcp"] = "gcp"
    username: str = Field(min_length=1)
    password: str = Field(min_length=1, repr=False)
    issued_at: datetime

    @field_validator("username", "password")
    @classmethod
    def credential_values_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("credential values must not be blank")
        return value
