"""
Pydantic models for ZIP extraction API response.

These models define the structure of the /validate/zip/extract endpoint response
for the Flutter wizard to parse and populate fields.
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FileExtractionResult(BaseModel):
    """Result of extracting a single file from the ZIP."""
    exists: bool
    content: str | None = None  # UTF-8 for text, base64 for binary
    is_binary: bool = False
    validation_error: str | None = None


class FunctionExtractionResult(BaseModel):
    """Extracted function code from processor/action/feedback directories."""
    processors: dict[str, FileExtractionResult] = Field(default_factory=dict)
    event_actions: dict[str, FileExtractionResult] = Field(default_factory=dict)
    event_feedback: FileExtractionResult | None = None


class AssetExtractionResult(BaseModel):
    """Extracted binary assets (GLB files for 3D visualization)."""
    scene_glb: FileExtractionResult | None = None


class ValidationContextInput(BaseModel):
    """Input context for Mode A (Wizard Step 3) validation."""

    model_config = ConfigDict(extra="forbid")

    l2_provider: Literal["aws", "azure", "gcp", "google"] | None = None
    l4_provider: Literal["aws", "azure"] | None = None
    optimization_flags: dict[str, Any] | None = None
    skip_credentials: Literal[True] = True
    skip_config_files: list[str] = Field(default_factory=list)


class ZipExtractionResponse(BaseModel):
    """Full response from /validate/zip/extract endpoint."""
    success: bool
    files: dict[str, FileExtractionResult] = Field(default_factory=dict)
    functions: FunctionExtractionResult = Field(default_factory=FunctionExtractionResult)
    assets: AssetExtractionResult = Field(default_factory=AssetExtractionResult)
    validation_errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
