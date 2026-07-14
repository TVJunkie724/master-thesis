"""Project-scoped storage boundary for Deployer project data."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import constants as CONSTANTS
from src.core.paths import (
    get_project_root,
    resolve_deployment_paths,
    resolve_project_context_path,
    validate_path_component,
)


SENSITIVE_PROJECT_FILENAMES = {
    "config_credentials.json",
    "config_credentials_aws.json",
    "config_credentials_azure.json",
    "config_credentials_google.json",
    "config_credentials_gcp.json",
    "gcp_credentials.json",
    "google-credentials.json",
    "google_credentials.json",
    "service_account.json",
}


class ProjectStorageError(ValueError):
    """Base error for project storage boundary violations."""


class ProjectFileAccessDenied(PermissionError):
    """Raised when a project file is intentionally not readable via generic APIs."""


@dataclass(frozen=True)
class ProjectStorageContext:
    """Resolved project storage context."""

    project_name: str
    project_path: Path
    is_template: bool


class ProjectStorage:
    """Owns safe project path resolution and project file I/O."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or get_project_root()

    def context(self, project_name: str) -> ProjectStorageContext:
        """Resolve a project name into its canonical storage context."""
        safe_name = self._validate_project_name(project_name)
        return ProjectStorageContext(
            project_name=safe_name,
            project_path=resolve_project_context_path(safe_name, self.project_root),
            is_template=safe_name == CONSTANTS.DEFAULT_PROJECT_NAME,
        )

    def deployment_project_path(self, project_name: str) -> Path:
        """Resolve a runtime upload project path, never the canonical template path."""
        safe_name = self._validate_project_name(project_name)
        return resolve_deployment_paths(safe_name, self.project_root).project_path

    def exists(self, project_name: str) -> bool:
        """Return True when the project context exists."""
        return self.context(project_name).project_path.exists()

    def list_projects(self, include_templates: bool = False) -> list[str]:
        """List runtime projects under upload/ with optional legacy template inclusion."""
        upload_root = resolve_deployment_paths("placeholder", self.project_root).upload_root
        if not upload_root.exists():
            return []

        projects = []
        for item in upload_root.iterdir():
            if item.name.startswith("."):
                continue
            if not include_templates and item.name == CONSTANTS.DEFAULT_PROJECT_NAME:
                continue
            if item.is_dir():
                projects.append(item.name)
        return sorted(projects)

    def read_json(self, project_name: str, relative_path: str) -> Any:
        """Read a JSON file from a project context."""
        file_path = self.resolve_file(project_name, relative_path, must_be_readable=True)
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def read_json_optional(self, project_name: str, relative_path: str) -> Any | None:
        """Read a JSON file if it exists; return None for missing files."""
        try:
            return self.read_json(project_name, relative_path)
        except FileNotFoundError:
            return None

    def read_text(self, project_name: str, relative_path: str) -> str:
        """Read a text file from a project context."""
        file_path = self.resolve_file(project_name, relative_path, must_be_readable=True)
        return file_path.read_text(encoding="utf-8")

    def write_text(self, project_name: str, relative_path: str, content: str) -> Path:
        """Write a text file inside a runtime project context."""
        self._reject_template_write(project_name)
        file_path = self.resolve_file(project_name, relative_path, for_write=True)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def write_json(self, project_name: str, relative_path: str, content: Any) -> Path:
        """Write JSON inside a runtime project context."""
        self._reject_template_write(project_name)
        file_path = self.resolve_file(project_name, relative_path, for_write=True)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
        return file_path

    def resolve_file(
        self,
        project_name: str,
        relative_path: str,
        *,
        must_be_readable: bool = False,
        for_write: bool = False,
    ) -> Path:
        """Resolve a project-relative path and reject traversal attempts."""
        context = self.context(project_name)
        if for_write and context.is_template:
            raise ProjectStorageError("Cannot modify the protected template project.")

        normalized = self._normalize_relative_path(relative_path)
        if must_be_readable and is_sensitive_project_file(normalized):
            raise ProjectFileAccessDenied(
                f"Access denied for protected sensitive project file '{normalized}'."
            )

        target = (context.project_path / normalized).resolve()
        base = context.project_path.resolve()
        if base not in target.parents and target != base:
            raise ProjectStorageError("Invalid file path: Traversal attempt detected.")

        if must_be_readable:
            if not target.exists():
                raise FileNotFoundError(f"File '{normalized}' not found.")
            if target.is_dir():
                raise ProjectStorageError(f"'{normalized}' is a directory, not a file.")

        return target

    def file_tree(self, project_name: str) -> list[dict[str, Any]]:
        """Return a recursive, secret-safe file tree for a project context."""
        context = self.context(project_name)
        if not context.project_path.exists():
            raise FileNotFoundError(f"Project '{project_name}' does not exist.")
        return self._build_tree(context.project_path, "")

    def file_content(self, project_name: str, relative_path: str) -> dict[str, Any]:
        """Return text content and parsed JSON when applicable."""
        normalized = self._normalize_relative_path(relative_path)
        try:
            raw = self.read_text(project_name, normalized)
        except UnicodeDecodeError as exc:
            raise ProjectStorageError("Cannot read binary file as text.") from exc

        result: dict[str, Any] = {"path": normalized, "raw": raw}
        if normalized.endswith(".json") or normalized.endswith(".json.example"):
            try:
                result["content"] = json.loads(raw)
            except json.JSONDecodeError:
                pass
        return result

    def version_count(self, project_name: str) -> int:
        """Return the number of archived ZIP versions for a runtime project."""
        versions_dir = self.deployment_project_path(project_name) / CONSTANTS.PROJECT_VERSIONS_DIR_NAME
        if not versions_dir.exists():
            return 0
        return len([path for path in versions_dir.iterdir() if path.suffix == ".zip"])

    def _build_tree(self, current_path: Path, rel_base: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            entries = sorted(current_path.iterdir(), key=lambda path: path.name)
        except OSError:
            return []

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.name in {CONSTANTS.PROJECT_VERSIONS_DIR_NAME, "__pycache__"}:
                continue
            if entry.name == CONSTANTS.PROJECT_INFO_FILE:
                continue

            rel_path = "/".join(part for part in [rel_base, entry.name] if part)
            if entry.is_file() and is_sensitive_project_file(rel_path):
                continue

            item: dict[str, Any] = {"name": entry.name, "path": rel_path}
            if entry.is_dir():
                item["type"] = "directory"
                item["children"] = self._build_tree(entry, rel_path)
            else:
                item["type"] = "file"
                item["size"] = entry.stat().st_size
            items.append(item)
        return items

    def _validate_project_name(self, project_name: str) -> str:
        try:
            return validate_path_component(project_name, "project name")
        except ValueError as exc:
            raise ProjectStorageError("Invalid project name.") from exc

    def _normalize_relative_path(self, relative_path: str) -> str:
        path = Path(relative_path)
        if path.is_absolute():
            raise ProjectStorageError("Invalid file path: Absolute paths are not allowed.")
        normalized = path.as_posix()
        if not normalized or normalized == ".":
            raise ProjectStorageError("Invalid file path.")
        return normalized

    def _reject_template_write(self, project_name: str) -> None:
        if project_name == CONSTANTS.DEFAULT_PROJECT_NAME:
            raise ProjectStorageError("Cannot modify the protected template project.")


def is_sensitive_project_file(relative_path: str) -> bool:
    """Return True when a project file may contain live cloud credentials."""
    filename = Path(relative_path).name
    if filename.endswith(".example"):
        return False
    if filename in SENSITIVE_PROJECT_FILENAMES:
        return True
    return "credentials" in filename.lower()


def get_project_storage(project_root: Path | None = None) -> ProjectStorage:
    """Factory for the default project storage service."""
    return ProjectStorage(project_root=project_root)
