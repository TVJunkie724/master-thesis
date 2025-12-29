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
    
    def deploy_all(self, context: Optional['DeploymentContext'] = None, skip_credential_check: bool = False) -> dict:
        """
        Deploy all infrastructure and code.
        
        Steps:
        0. Validate cloud credentials (optional, default: enabled)
        0.5. Initialize cloud providers for SDK operations
        1. Validate project structure
        2. Build function packages (Lambda ZIPs, Function ZIPs)
        3. Generate tfvars.json
        4. terraform init
        5. terraform apply (AWS uses pre-built ZIPs)
        6. Deploy Azure function code (Kudu)
        7. Post-deployment SDK operations (IoT, DTDL, Grafana)
        
        Args:
            context: DeploymentContext for SDK operations (REQUIRED)
            skip_credential_check: If True, skip pre-deployment credential validation.
                                   Default is False (validation enabled).
        
        Returns:
            Dictionary of Terraform outputs
        
        Raises:
            TerraformError: If Terraform fails
            ConfigurationError: If config is invalid
            ValueError: If project validation fails, credentials are invalid, or context is None
        """
        # FAIL-FAST: Context is required for SDK operations
        if context is None:
            raise ValueError(
                "DeploymentContext is required. SDK operations (Kudu deployment, "
                "IoT registration, DTDL upload, Grafana config) cannot run without context."
            )
        logger.info("=" * 60)
        logger.info("  TERRAFORM DEPLOYMENT - STARTING")
        logger.info("=" * 60)
        
        # Step 0: Validate cloud credentials (optional)
        if not skip_credential_check:
            logger.info("\n[STEP 0/9] Validating cloud credentials...")
            self._validate_credentials()
        else:
            logger.info("\n[STEP 0/9] Skipping credential validation (skip_credential_check=True)")
        
        # Step 0.5: Initialize providers for SDK operations (must happen before Kudu)
        logger.info("\n[STEP 0.5/9] Initializing cloud providers for SDK operations...")
        self._initialize_providers(context)
        
        # Step 1: Validate project structure
        logger.info("\n[STEP 1/9] Validating project structure...")
        from src.validation.directory_validator import validate_project_directory
        validate_project_directory(self.project_path)
        logger.info("✓ Project validation passed")
        
        # Step 2: Build function packages
        logger.info("\n[STEP 2/9] Building function packages...")
        self._build_packages()
        
        # Step 3: Generate tfvars
        logger.info("\n[STEP 3/9] Generating tfvars.json...")
        self._generate_tfvars()
        
        # Step 4: Terraform init
        logger.info("\n[STEP 4/9] Terraform init...")
        self.runner.init()
        
        # Step 5: Terraform apply (AWS Lambda uses pre-built ZIPs)
        logger.info("\n[STEP 5/9] Terraform apply...")
        self.runner.apply(var_file=str(self.tfvars_path))
        
        # Get outputs
        self._terraform_outputs = self.runner.output()
        logger.info(f"✓ Terraform outputs: {list(self._terraform_outputs.keys())}")
        
        # Step 6: Deploy Azure function code (Kudu)
        logger.info("\n[STEP 6/9] Deploying Azure function code...")
        self._deploy_azure_function_code(context)
        
        # Step 7: Post-deployment SDK operations (IoT, DTDL, Grafana)
        logger.info("\n[STEP 7/9] Running post-deployment operations...")
        self._run_post_deployment(context)
        
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
    
    def _validate_credentials(self) -> None:
        """
        Validate cloud credentials before deployment.
        
        Checks credentials for each provider configured in config_providers.json.
        This provides fail-fast behavior with clear error messages instead of
        waiting for Terraform to fail 10+ minutes into deployment.
        
        Raises:
            ValueError: If credentials are invalid or missing required permissions
        """
        providers = self._load_providers_config()
        credentials = self._load_credentials()
        
        # Determine which clouds are in use
        all_layers = ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider",
                      "layer_3_cold_provider", "layer_3_archive_provider",
                      "layer_4_provider", "layer_5_provider"]
        
        used_clouds = set()
        for layer in all_layers:
            cloud = providers.get(layer)
            if cloud:
                used_clouds.add(cloud)
        
        logger.info(f"  Configured clouds: {', '.join(used_clouds) or 'none'}")
        
        # Validate Azure credentials
        if "azure" in used_clouds:
            azure_creds = credentials.get("azure", {})
            if not azure_creds:
                raise ValueError("Azure is configured but no Azure credentials found")
            
            try:
                from api.azure_credentials_checker import check_azure_credentials
                result = check_azure_credentials(azure_creds)
                
                if result["status"] == "error":
                    raise ValueError(f"Azure credential validation failed: {result['message']}")
                elif result["status"] == "invalid":
                    logger.warning(f"  ⚠ Azure: {result['message']}")
                    logger.warning("    Deployment may fail due to missing permissions")
                elif result["status"] == "partial":
                    logger.warning(f"  ⚠ Azure: {result['message']}")
                else:
                    logger.info("  ✓ Azure credentials validated")
            except ImportError:
                logger.warning("  ⚠ Azure SDK not installed, skipping credential check")
        
        # Validate AWS credentials
        if "aws" in used_clouds:
            aws_creds = credentials.get("aws", {})
            if not aws_creds:
                raise ValueError("AWS is configured but no AWS credentials found")
            
            try:
                from api.credentials_checker import check_aws_credentials
                result = check_aws_credentials(aws_creds)
                
                if result["status"] == "error":
                    raise ValueError(f"AWS credential validation failed: {result['message']}")
                elif result["status"] == "invalid":
                    logger.warning(f"  ⚠ AWS: {result['message']}")
                    logger.warning("    Deployment may fail due to missing permissions")
                elif result["status"] == "partial":
                    logger.warning(f"  ⚠ AWS: {result['message']}")
                else:
                    logger.info("  ✓ AWS credentials validated")
            except ImportError:
                logger.warning("  ⚠ boto3 not installed, skipping AWS credential check")
        
        # Validate GCP credentials
        if "google" in used_clouds:
            gcp_creds = credentials.get("gcp", {})
            if not gcp_creds:
                raise ValueError("GCP is configured but no GCP credentials found")
            
            try:
                from api.gcp_credentials_checker import check_gcp_credentials
                result = check_gcp_credentials(gcp_creds)
                
                if result["status"] == "error":
                    raise ValueError(f"GCP credential validation failed: {result['message']}")
                elif result["status"] == "invalid":
                    logger.warning(f"  ⚠ GCP: {result['message']}")
                    logger.warning("    Deployment may fail due to missing permissions")
                elif result["status"] == "partial":
                    logger.warning(f"  ⚠ GCP: {result['message']}")
                else:
                    logger.info("  ✓ GCP credentials validated")
            except ImportError:
                logger.warning("  ⚠ google-auth not installed, skipping GCP credential check")
    
    def _build_packages(self) -> None:
        """Build all Lambda/Function packages before Terraform."""
        from src.providers.terraform.package_builder import build_all_packages
        
        providers = self._load_providers_config()
        build_all_packages(self.terraform_dir, self.project_path, providers)
    
    def _initialize_providers(self, context: 'DeploymentContext') -> None:
        """
        Initialize cloud provider SDK clients for post-Terraform operations.
        
        This must run EARLY (before Kudu deployment) because:
        - Azure Kudu deployment needs provider.clients["web"]
        - AWS/GCP SDK operations need their respective clients
        
        Args:
            context: DeploymentContext to populate with providers
            
        Raises:
            ValueError: If required credentials are missing
        """
        providers = self._load_providers_config()
        credentials = self._load_credentials()
        
        # Determine which clouds need SDK operations
        sdk_layers = ["layer_1_provider", "layer_2_provider", "layer_4_provider", "layer_5_provider"]
        used_clouds = set()
        for layer in sdk_layers:
            cloud = providers.get(layer)
            if cloud:
                used_clouds.add(cloud)
        
        logger.info(f"  Clouds requiring SDK initialization: {', '.join(sorted(used_clouds)) or 'none'}")
        
        # Initialize Azure provider
        if "azure" in used_clouds and "azure" not in context.providers:
            logger.info("  Initializing Azure provider...")
            from src.providers.azure.provider import AzureProvider
            azure_provider = AzureProvider()
            azure_creds = credentials.get("azure", {})
            azure_provider.initialize_clients(azure_creds, context.config.digital_twin_name)
            context.providers["azure"] = azure_provider
            logger.info("  ✓ Azure provider initialized")
        
        # Initialize AWS provider
        if "aws" in used_clouds and "aws" not in context.providers:
            logger.info("  Initializing AWS provider...")
            from src.providers.aws.provider import AWSProvider
            aws_provider = AWSProvider()
            aws_creds = credentials.get("aws", {})
            aws_provider.initialize_clients(aws_creds, context.config.digital_twin_name)
            context.providers["aws"] = aws_provider
            logger.info("  ✓ AWS provider initialized")
        
        # Initialize GCP provider (for future L4/L5 and consistency)
        if "google" in used_clouds and "gcp" not in context.providers:
            logger.info("  Initializing GCP provider...")
            from src.providers.gcp.provider import GCPProvider
            gcp_provider = GCPProvider()
            gcp_creds = credentials.get("gcp", {})
            gcp_provider.initialize_clients(gcp_creds, context.config.digital_twin_name)
            context.providers["gcp"] = gcp_provider
            logger.info("  ✓ GCP provider initialized")
    
    def _deploy_azure_function_code(self, context: 'DeploymentContext') -> None:
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
            context, self.project_path, providers, self._terraform_outputs
        )
    
    def _run_post_deployment(self, context: 'DeploymentContext') -> None:
        """
        Run post-Terraform SDK operations.
        
        Note: Providers are already initialized in _initialize_providers().
        This method only calls the cloud-specific SDK functions.
        """
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
            create_twinmaker_entities(context, self.project_path, self._terraform_outputs)
        
        if providers["layer_1_provider"] == "aws":
            register_aws_iot_devices(context, self.project_path)
        
        if providers["layer_5_provider"] == "aws":
            configure_aws_grafana(context, self._terraform_outputs)
