"""
Terraform Provider Module.

This module provides a Terraform-based deployment strategy for the hybrid
approach where Terraform handles infrastructure and Python handles dynamic operations.
"""

from src.providers.terraform.deployer_strategy import TerraformDeployerStrategy

__all__ = ["TerraformDeployerStrategy"]
