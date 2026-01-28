"""
Pydantic models for ZIP extraction API response.

These models define the structure of the /validate/zip/extract endpoint response
for the Flutter wizard to parse and populate fields.
"""
from pydantic import BaseModel
from typing import Optional


class FileExtractionResult(BaseModel):
    """Result of extracting a single file from the ZIP."""
    exists: bool
    content: Optional[str] = None  # UTF-8 for text, base64 for binary
    is_binary: bool = False
    validation_error: Optional[str] = None


class FunctionExtractionResult(BaseModel):
    """Extracted function code from processor/action/feedback directories."""
    processors: dict[str, FileExtractionResult] = {}  # keyed by device ID
    event_actions: dict[str, FileExtractionResult] = {}  # keyed by action name
    event_feedback: Optional[FileExtractionResult] = None


class AssetExtractionResult(BaseModel):
    """Extracted binary assets (GLB files for 3D visualization)."""
    scene_glb: Optional[FileExtractionResult] = None


class ValidationContextInput(BaseModel):
    """Input context for Mode A (Wizard Step 3) validation."""
    l2_provider: Optional[str] = None  # aws, azure, google
    l4_provider: Optional[str] = None  # aws, azure
    optimization_flags: Optional[dict] = None
    skip_credentials: bool = True
    skip_config_files: list[str] = []


class ZipExtractionResponse(BaseModel):
    """Full response from /validate/zip/extract endpoint."""
    success: bool
    files: dict[str, FileExtractionResult] = {}  # config files by name
    functions: FunctionExtractionResult = FunctionExtractionResult()
    assets: AssetExtractionResult = AssetExtractionResult()
    validation_errors: list[str] = []
    warnings: list[str] = []
