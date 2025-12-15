"""
Terraform Deployer Strategy.

This module provides a deployment strategy that uses Terraform for infrastructure
provisioning and Python for dynamic operations (function code, DTDL, Grafana).

Architecture:
    TerraformDeployerStrategy
        ├── terraform apply (all infrastructure)
        └── Post-terraform steps:
            ├── Function code deployment (Kudu ZIP)
            ├── DTDL model upload (Azure SDK)
            ├── IoT device registration (Azure SDK)
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
from typing import Optional, TYPE_CHECKING

from src.terraform_runner import TerraformRunner, TerraformError
from src.tfvars_generator import generate_tfvars, ConfigurationError
from src.providers.azure.layers.function_bundler import (
    bundle_l0_functions,
    bundle_l1_functions,
    bundle_l2_functions,
    bundle_l3_functions,
)
from src.providers.azure.layers.deployment_helpers import (
    deploy_to_kudu,
    get_publishing_credentials_with_retry,
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
    3. Deploys function code via Kudu
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
        
        self._runner: Optional[TerraformRunner] = None
        self._providers_config: Optional[dict] = None
        self._terraform_outputs: Optional[dict] = None
    
    @property
    def runner(self) -> TerraformRunner:
        """Lazy-load Terraform runner."""
        if self._runner is None:
            self._runner = TerraformRunner(str(self.terraform_dir))
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
    
    def deploy_all(self, context: Optional['DeploymentContext'] = None) -> dict:
        """
        Deploy all infrastructure and code.
        
        Steps:
        1. Generate tfvars.json
        2. terraform init
        3. terraform apply
        4. Deploy function code (Kudu)
        5. Post-deployment SDK operations
        
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
        
        # Step 1: Generate tfvars
        logger.info("\n[STEP 1/5] Generating tfvars.json...")
        self.tfvars_path.parent.mkdir(parents=True, exist_ok=True)
        generate_tfvars(str(self.project_path), str(self.tfvars_path))
        logger.info(f"✓ Generated: {self.tfvars_path}")
        
        # Step 2: Terraform init
        logger.info("\n[STEP 2/5] Terraform init...")
        self.runner.init()
        
        # Step 3: Terraform apply
        logger.info("\n[STEP 3/5] Terraform apply...")
        self.runner.apply(var_file=str(self.tfvars_path))
        
        # Get outputs
        self._terraform_outputs = self.runner.output()
        logger.info(f"✓ Terraform outputs: {list(self._terraform_outputs.keys())}")
        
        # Step 4: Deploy function code
        logger.info("\n[STEP 4/5] Deploying function code...")
        self._deploy_all_function_code()
        
        # Step 5: Post-deployment SDK operations
        logger.info("\n[STEP 5/5] Running post-deployment operations...")
        if context:
            self._run_post_deployment(context)
        else:
            logger.info("  Skipping SDK operations (no context provided)")
        
        logger.info("\n" + "=" * 60)
        logger.info("  TERRAFORM DEPLOYMENT - COMPLETE")
        logger.info("=" * 60)
        
        return self._terraform_outputs
    
    def destroy_all(self) -> None:
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
            generate_tfvars(str(self.project_path), str(self.tfvars_path))
        
        self.runner.init()
        self.runner.destroy(var_file=str(self.tfvars_path))
        
        logger.info("✓ All resources destroyed")
    
    def _deploy_all_function_code(self) -> None:
        """Deploy all function code via Kudu ZIP deploy."""
        providers = self._load_providers_config()
        
        # Validate required provider keys
        required_keys = [
            "layer_1_provider", "layer_2_provider", "layer_3_hot_provider",
            "layer_4_provider", "layer_5_provider"
        ]
        for key in required_keys:
            if key not in providers:
                raise ValueError(f"Missing required provider config: {key}")
        
        # Deploy L0 glue functions (if needed)
        l0_zip, l0_funcs = bundle_l0_functions(str(self.project_path), providers)
        if l0_zip and l0_funcs:
            app_name = self._terraform_outputs.get("azure_l0_function_app_name")
            if app_name:
                self._deploy_to_app(app_name, l0_zip, f"L0 ({len(l0_funcs)} functions)")
        
        # Deploy L1 functions
        if providers["layer_1_provider"] == "azure":
            app_name = self._terraform_outputs.get("azure_l1_function_app_name")
            if app_name:
                l1_zip = bundle_l1_functions(str(self.project_path))
                self._deploy_to_app(app_name, l1_zip, "L1")
        
        # Deploy L2 functions
        if providers["layer_2_provider"] == "azure":
            app_name = self._terraform_outputs.get("azure_l2_function_app_name")
            if app_name:
                l2_zip = bundle_l2_functions(str(self.project_path))
                self._deploy_to_app(app_name, l2_zip, "L2")
        
        # Deploy L3 functions
        if providers["layer_3_hot_provider"] == "azure":
            app_name = self._terraform_outputs.get("azure_l3_function_app_name")
            if app_name:
                l3_zip = bundle_l3_functions(str(self.project_path))
                self._deploy_to_app(app_name, l3_zip, "L3")
    
    def _deploy_to_app(self, app_name: str, zip_bytes: bytes, label: str) -> None:
        """Deploy ZIP bytes to a Function App via Kudu."""
        logger.info(f"  Deploying {label} to {app_name}...")
        
        # Get credentials from Terraform outputs or Azure SDK
        azure_creds = self._load_credentials().get("azure", {})
        rg_name = self._terraform_outputs.get("azure_resource_group_name")
        
        if not rg_name:
            logger.warning(f"  Resource group not found, skipping {label}")
            return
        
        try:
            creds = get_publishing_credentials_with_retry(
                resource_group=rg_name,
                app_name=app_name,
                credentials=azure_creds
            )
            
            deploy_to_kudu(
                app_name=app_name,
                zip_content=zip_bytes,
                publish_username=creds.publishing_user_name,
                publish_password=creds.publishing_password
            )
            logger.info(f"  ✓ {label} deployed")
        except Exception as e:
            logger.error(f"  ✗ {label} deployment failed: {e}")
            raise
    
    def _run_post_deployment(self, context: 'DeploymentContext') -> None:
        """Run post-Terraform SDK operations."""
        providers = self._load_providers_config()
        
        # Validate required provider keys
        for key in ["layer_1_provider", "layer_4_provider", "layer_5_provider"]:
            if key not in providers:
                raise ValueError(f"Missing required provider config: {key}")
        
        # DTDL model upload (L4)
        if providers["layer_4_provider"] == "azure":
            self._upload_dtdl_models(context)
        
        # IoT device registration (L1)
        if providers["layer_1_provider"] == "azure":
            self._register_iot_devices(context)
        
        # Grafana datasource configuration (L5)
        if providers["layer_5_provider"] == "azure":
            self._configure_grafana(context)
    
    def _upload_dtdl_models(self, context: 'DeploymentContext') -> None:
        """Upload DTDL models to Azure Digital Twins."""
        logger.info("  Uploading DTDL models...")
        try:
            from src.providers.azure.layers.layer_4_adt import upload_dtdl_models
            provider = context.providers.get("azure")
            if provider:
                upload_dtdl_models(provider, context.config, str(self.project_path))
                logger.info("  ✓ DTDL models uploaded")
        except ImportError:
            logger.warning("  layer_4_adt not available, skipping DTDL upload")
        except Exception as e:
            logger.warning(f"  DTDL upload failed: {e}")
    
    def _register_iot_devices(self, context: 'DeploymentContext') -> None:
        """Register IoT devices via SDK."""
        logger.info("  Registering IoT devices...")
        try:
            from src.providers.azure.layers.layer_1_iot import register_iot_devices
            provider = context.providers.get("azure")
            if provider:
                register_iot_devices(provider, context.config, str(self.project_path))
                logger.info("  ✓ IoT devices registered")
        except ImportError:
            logger.warning("  layer_1_iot not available, skipping device registration")
        except Exception as e:
            logger.warning(f"  IoT device registration failed: {e}")
    
    def _configure_grafana(self, context: 'DeploymentContext') -> None:
        """Configure Grafana datasources."""
        logger.info("  Configuring Grafana...")
        try:
            from src.providers.azure.layers.layer_5_grafana import configure_grafana_datasource
            provider = context.providers.get("azure")
            if provider:
                hot_reader_url = self._terraform_outputs.get("azure_l3_hot_reader_url")
                if hot_reader_url:
                    configure_grafana_datasource(provider, hot_reader_url)
                    logger.info("  ✓ Grafana configured")
        except ImportError:
            logger.warning("  layer_5_grafana not available, skipping config")
        except Exception as e:
            logger.warning(f"  Grafana config failed: {e}")
