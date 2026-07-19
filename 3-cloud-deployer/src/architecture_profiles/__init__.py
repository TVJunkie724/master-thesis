"""Dark-read architecture-profile contracts for the Deployer."""

from .catalog import DeploymentComponentCatalog
from .registry import ArchitectureProfileRegistry

__all__ = ["ArchitectureProfileRegistry", "DeploymentComponentCatalog"]
