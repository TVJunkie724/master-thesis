"""Strict Management API contract for Deployer project ZIP extraction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProjectFileExtraction(BaseModel):
    """One allowlisted extracted text or binary file."""

    model_config = ConfigDict(extra="forbid")

    exists: bool
    content: str | None = None
    is_binary: bool = False
    validation_error: str | None = None


class ProjectAssetFileExtraction(ProjectFileExtraction):
    """Extracted asset plus Management API persistence outcome."""

    saved: bool | None = None


class ProjectFunctionExtraction(BaseModel):
    """Extracted user functions grouped by supported role."""

    model_config = ConfigDict(extra="forbid")

    processors: dict[str, ProjectFileExtraction] = Field(default_factory=dict)
    event_actions: dict[str, ProjectFileExtraction] = Field(default_factory=dict)
    event_feedback: ProjectFileExtraction | None = None


class ProjectAssetExtraction(BaseModel):
    """Extracted binary assets allowed to cross the Deployer boundary."""

    model_config = ConfigDict(extra="forbid")

    scene_glb: ProjectAssetFileExtraction | None = None


class ProjectZipExtractionContract(BaseModel):
    """Credential-free response accepted from the internal Deployer API."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    files: dict[str, ProjectFileExtraction] = Field(default_factory=dict)
    functions: ProjectFunctionExtraction = Field(
        default_factory=ProjectFunctionExtraction
    )
    assets: ProjectAssetExtraction = Field(default_factory=ProjectAssetExtraction)
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
