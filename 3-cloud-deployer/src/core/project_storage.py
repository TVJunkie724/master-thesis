"""Twin-scoped path boundary for durable deployment workspaces."""

from dataclasses import dataclass
from pathlib import Path

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
    """Base error for Twin workspace path violations."""


@dataclass(frozen=True)
class ProjectStorageContext:
    """Resolved Twin deployment-workspace context."""

    project_name: str
    project_path: Path
    is_template: bool


class ProjectStorage:
    """Own safe Twin-name resolution without exposing a generic file API."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or get_project_root()

    def context(self, project_name: str) -> ProjectStorageContext:
        """Resolve a Twin name into its canonical storage context."""
        safe_name = self._validate_project_name(project_name)
        return ProjectStorageContext(
            project_name=safe_name,
            project_path=resolve_project_context_path(safe_name, self.project_root),
            is_template=safe_name == CONSTANTS.DEFAULT_PROJECT_NAME,
        )

    def deployment_project_path(self, project_name: str) -> Path:
        """Resolve a runtime upload path, never the canonical template path."""
        safe_name = self._validate_project_name(project_name)
        return resolve_deployment_paths(safe_name, self.project_root).project_path

    def exists(self, project_name: str) -> bool:
        """Return True when the Twin workspace exists."""
        return self.context(project_name).project_path.exists()

    @staticmethod
    def _validate_project_name(project_name: str) -> str:
        try:
            return validate_path_component(project_name, "project name")
        except ValueError as exc:
            raise ProjectStorageError("Invalid project name.") from exc


def is_sensitive_project_file(relative_path: str) -> bool:
    """Return True when a deployment file may contain live cloud credentials."""
    filename = Path(relative_path).name
    if filename.endswith(".example"):
        return False
    if filename in SENSITIVE_PROJECT_FILENAMES:
        return True
    return "credentials" in filename.lower()


def get_project_storage(project_root: Path | None = None) -> ProjectStorage:
    """Factory for the default Twin workspace path boundary."""
    return ProjectStorage(project_root=project_root)
