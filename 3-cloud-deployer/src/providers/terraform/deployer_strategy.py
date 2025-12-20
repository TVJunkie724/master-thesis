"""
Terraform Deployer Strategy.

This module provides a deployment strategy that uses Terraform for infrastructure
provisioning and Python for dynamic operations (function code, DTDL, Grafana).

Architecture:
    TerraformDeployerStrategy
        ├── terraform apply (all infrastructure)
        └── Post-terraform steps:
            ├── Azure: Function code deployment (Kudu ZIP)
            ├── AWS: Lambda code deployment (boto3)
            ├── DTDL/TwinMaker model upload (SDK)
            ├── IoT device registration (SDK)
            └── Grafana datasource config (API)

Usage:
    strategy = TerraformDeployerStrategy(
        terraform_dir="/app/src/terraform",
        project_path="/app/upload/my_project"
    )
    strategy.deploy_all()
    strategy.destroy_all()
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from src.terraform_runner import TerraformRunner, TerraformError
from src.tfvars_generator import generate_tfvars, ConfigurationError

# Provider-specific deployers
from src.providers.terraform.azure_deployer import (
    deploy_azure_function_code,
    upload_dtdl_models,
    register_azure_iot_devices,
    configure_azure_grafana,
)
from src.providers.terraform.aws_deployer import (
    create_twinmaker_entities,
    register_aws_iot_devices,
    configure_aws_grafana,
)

if TYPE_CHECKING:
    from src.core.context import DeploymentContext

logger = logging.getLogger(__name__)


class TerraformDeployerStrategy:
    """
    Deploys infrastructure via Terraform with Python post-deployment steps.
    
    This strategy:
    1. Generates tfvars.json from project configs
    2. Runs terraform init + apply
    3. Deploys function code via Kudu (Azure) / boto3 (AWS)
    4. Runs SDK operations (DTDL, Grafana, IoT devices)
    
    Attributes:
        terraform_dir: Path to src/terraform/
        project_path: Path to project directory (upload/<project>/)
    """
    
    def __init__(self, terraform_dir: str, project_path: str):
        """
        Initialize the Terraform deployer strategy.
        
        Args:
            terraform_dir: Absolute path to Terraform configuration directory
            project_path: Absolute path to project directory
        
        Raises:
            ValueError: If required paths are missing
        """
        if not terraform_dir:
            raise ValueError("terraform_dir is required")
        if not project_path:
            raise ValueError("project_path is required")
        
        self.terraform_dir = Path(terraform_dir)
        self.project_path = Path(project_path)
        self.tfvars_path = self.project_path / "terraform" / "generated.tfvars.json"
        self.state_path = self.project_path / "terraform" / "terraform.tfstate"
        
        self._runner: Optional[TerraformRunner] = None
        self._providers_config: Optional[dict] = None
        self._terraform_outputs: Optional[dict] = None
    
    @property
    def runner(self) -> TerraformRunner:
        """Lazy-load Terraform runner."""
        if self._runner is None:
            self._runner = TerraformRunner(
                terraform_dir=str(self.terraform_dir),
                state_path=str(self.state_path)
            )
        return self._runner
    
    def _load_providers_config(self) -> dict:
        """Load config_providers.json."""
        if self._providers_config is None:
            providers_file = self.project_path / "config_providers.json"
            if providers_file.exists():
                with open(providers_file) as f:
                    self._providers_config = json.load(f)
            else:
                self._providers_config = {}
        return self._providers_config
    
    def _load_credentials(self) -> dict:
        """Load config_credentials.json."""
        creds_file = self.project_path / "config_credentials.json"
        if not creds_file.exists():
            raise ConfigurationError(f"config_credentials.json not found: {creds_file}")
        with open(creds_file) as f:
            return json.load(f)
    
    # =========================================================================
    # Main Deployment Methods
    # =========================================================================
    
    def deploy_all(self, context: Optional['DeploymentContext'] = None) -> dict:
        """
        Deploy all infrastructure and code.
        
        Steps:
        1. Build function packages (Lambda ZIPs, Function ZIPs)
        2. Generate tfvars.json
        3. terraform init
        4. terraform apply (AWS uses pre-built ZIPs)
        5. Deploy Azure function code (Kudu)
        6. Post-deployment SDK operations
        
        Args:
            context: Optional deployment context for SDK operations
        
        Returns:
            Dictionary of Terraform outputs
        
        Raises:
            TerraformError: If Terraform fails
            ConfigurationError: If config is invalid
        """
        logger.info("=" * 60)
        logger.info("  TERRAFORM DEPLOYMENT - STARTING")
        logger.info("=" * 60)
        
        # Step 1: Build function packages
        logger.info("\n[STEP 1/6] Building function packages...")
        self._build_packages()
        
        # Step 2: Generate tfvars
        logger.info("\n[STEP 2/6] Generating tfvars.json...")
        self._generate_tfvars()
        
        # Step 3: Terraform init
        logger.info("\n[STEP 3/6] Terraform init...")
        self.runner.init()
        
        # Step 4: Terraform apply (AWS Lambda uses pre-built ZIPs)
        logger.info("\n[STEP 4/6] Terraform apply...")
        self.runner.apply(var_file=str(self.tfvars_path))
        
        # Get outputs
        self._terraform_outputs = self.runner.output()
        logger.info(f"✓ Terraform outputs: {list(self._terraform_outputs.keys())}")
        
        # Step 5: Deploy Azure function code (Kudu)
        logger.info("\n[STEP 5/6] Deploying Azure function code...")
        self._deploy_azure_function_code()
        
        # Step 6: Post-deployment SDK operations
        logger.info("\n[STEP 6/6] Running post-deployment operations...")
        if context:
            self._run_post_deployment(context)
        else:
            logger.info("  Skipping SDK operations (no context provided)")
        
        logger.info("\n" + "=" * 60)
        logger.info("  TERRAFORM DEPLOYMENT - COMPLETE")
        logger.info("=" * 60)
        
        return self._terraform_outputs
    
    def destroy_all(self, context: Optional['DeploymentContext'] = None) -> None:
        """
        Destroy all Terraform-managed resources.
        
        Raises:
            TerraformError: If destroy fails
        """
        logger.info("=" * 60)
        logger.info("  TERRAFORM DESTROY - STARTING")
        logger.info("=" * 60)
        
        if not self.tfvars_path.exists():
            logger.warning("tfvars.json not found, generating...")
            self._generate_tfvars()
        
        self.runner.init()
        self.runner.destroy(var_file=str(self.tfvars_path))
        
        logger.info("✓ All resources destroyed")
    
    def get_outputs(self) -> dict:
        """Get Terraform outputs (run after deploy)."""
        if self._terraform_outputs is None:
            self._terraform_outputs = self.runner.output()
        return self._terraform_outputs
    
    # =========================================================================
    # Internal Methods
    # =========================================================================
    
    def _generate_tfvars(self) -> None:
        """Generate tfvars.json from project config."""
        self.tfvars_path.parent.mkdir(parents=True, exist_ok=True)
        generate_tfvars(str(self.project_path), str(self.tfvars_path))
        logger.info(f"✓ Generated: {self.tfvars_path}")
    
    def _build_packages(self) -> None:
        """Build all Lambda/Function packages before Terraform."""
        from src.providers.terraform.package_builder import build_all_packages
        
        providers = self._load_providers_config()
        build_all_packages(self.terraform_dir, self.project_path, providers)
    
    def _deploy_azure_function_code(self) -> None:
        """Deploy Azure Function code via Kudu (using pre-built ZIPs)."""
        providers = self._load_providers_config()
        
        # Check if any layer uses Azure
        azure_layers = ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider",
                        "layer_4_provider", "layer_5_provider"]
        has_azure = any(providers.get(layer) == "azure" for layer in azure_layers)
        
        if not has_azure:
            logger.info("  No Azure layers configured, skipping Kudu deployment")
            return
        
        # Deploy Azure functions via Kudu
        deploy_azure_function_code(
            self.project_path, providers, self._terraform_outputs, self._load_credentials
        )
    
    def _run_post_deployment(self, context: 'DeploymentContext') -> None:
        """Run post-Terraform SDK operations."""
        providers = self._load_providers_config()
        
        # Validate required provider keys
        for key in ["layer_1_provider", "layer_4_provider", "layer_5_provider"]:
            if key not in providers:
                raise ValueError(f"Missing required provider config: {key}")
        
        # ===== Azure Post-Deployment =====
        if providers["layer_4_provider"] == "azure":
            upload_dtdl_models(context, self.project_path)
        
        if providers["layer_1_provider"] == "azure":
            register_azure_iot_devices(context, self.project_path)
        
        if providers["layer_5_provider"] == "azure":
            configure_azure_grafana(context, self._terraform_outputs)
        
        # ===== AWS Post-Deployment =====
        if providers["layer_4_provider"] == "aws":
            create_twinmaker_entities(
                self.project_path, self._terraform_outputs, self._load_credentials
            )
        
        if providers["layer_1_provider"] == "aws":
            register_aws_iot_devices(self.project_path, self._load_credentials)
        
        if providers["layer_5_provider"] == "aws":
            configure_aws_grafana(self._terraform_outputs, self._load_credentials)
