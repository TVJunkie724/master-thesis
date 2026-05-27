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
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING

from src.terraform_runner import TerraformRunner, TerraformError
from src.tfvars_generator import generate_tfvars, ConfigurationError
from src.core.config_loader import load_credentials, load_project_config

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

# Pre-import cleanup modules to avoid ThreadPoolExecutor deadlock
# Python import locks can cause deadlock when multiple threads import simultaneously
from src.providers.aws.cleanup import cleanup_aws_resources
from src.providers.azure.cleanup import cleanup_azure_resources
from src.providers.gcp.cleanup import cleanup_gcp_resources

logger = logging.getLogger(__name__)


@dataclass
class DestroyResult:
    """Result of destroy operation (JSON-serializable)."""
    terraform_success: bool = False
    terraform_error: Optional[str] = None
    sdk_fallback_ran: bool = False
    sdk_fallback_results: Dict[str, bool] = field(default_factory=dict)
    dry_run: bool = False

    @property
    def sdk_fallback_success(self) -> bool:
        """True if all SDK cleanups succeeded (or none ran)."""
        return all(self.sdk_fallback_results.values()) if self.sdk_fallback_results else True
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {**asdict(self), "sdk_fallback_success": self.sdk_fallback_success}


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
            self._providers_config = load_project_config(self.project_path).providers
        return self._providers_config
    
    def _load_credentials(self) -> dict:
        """Load config_credentials.json."""
        credentials = load_credentials(self.project_path)
        if not credentials:
            raise ConfigurationError(f"No credentials found for project: {self.project_path}")
        return credentials
    
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
    
    def destroy_all(
        self, 
        context: Optional['DeploymentContext'] = None,
        # NOTE: Default is "always" because Terraform may return exit code 0 (success) even
        # when some resources fail to delete. This happens with AWS CloudControl provider
        # (AWSCC) for TwinMaker workspaces that contain SDK-created entities. The SDK cleanup
        # ensures all resources are properly removed regardless of Terraform's partial success.
        sdk_fallback: str = "always",
        dry_run: bool = False,
        sdk_timeout_seconds: int = 300,
        sdk_max_retries: int = 2
    ) -> 'DestroyResult':
        """
        Destroy all resources with optional SDK fallback cleanup.
        
        Args:
            context: DeploymentContext with credentials (REQUIRED for SDK cleanup)
            sdk_fallback: "never" | "on_failure" | "always"
            dry_run: If True, log what would be deleted without deleting
            sdk_timeout_seconds: Timeout per provider per attempt (default 5 min)
            sdk_max_retries: Retry count for failed SDK cleanup (default 2)
        
        Returns:
            DestroyResult with terraform_success, sdk_fallback_ran, etc.
        """
        result = DestroyResult(dry_run=dry_run)
        
        logger.info("=" * 60)
        logger.info("  TERRAFORM DESTROY - STARTING")
        logger.info("=" * 60)
        
        # Load credentials for pre-destroy and SDK fallback cleanup
        if context and not context.credentials:
            try:
                context.credentials = self._load_credentials()
            except Exception as e:
                logger.warning(f"Could not load credentials: {e}")
        
        # Pre-destroy: Clean orphaned diagnostic settings while parent resources still exist
        # This prevents 409 Conflict errors during Terraform destroy
        if context:
            try:
                azure_creds = context.credentials.get("azure", {})
                if azure_creds:
                    from src.providers.azure.diagnostic_settings_helper import DiagnosticSettingsHelper
                    from azure.identity import ClientSecretCredential
                    credential = ClientSecretCredential(
                        tenant_id=azure_creds["azure_tenant_id"],
                        client_id=azure_creds["azure_client_id"],
                        client_secret=azure_creds["azure_client_secret"]
                    )
                    helper = DiagnosticSettingsHelper(credential, azure_creds["azure_subscription_id"])
                    logger.info("[Pre-Destroy] Cleaning orphaned diagnostic settings...")
                    helper.cleanup_orphaned_by_prefix(context.project_name, dry_run=dry_run)
            except Exception as e:
                logger.warning(f"[Pre-Destroy] Diagnostic settings cleanup failed: {e}")
        
        # Pre-destroy: Clean TwinMaker SDK-created entities that block workspace deletion
        if context:
            try:
                self._pre_destroy_twinmaker_entities(context, dry_run)
            except Exception as e:
                logger.warning(f"[Pre-Destroy] TwinMaker cleanup failed: {e}")
        
        if dry_run:
            logger.info("[DRY RUN] Would run terraform destroy")
            result.terraform_success = True
        else:
            try:
                if not self.tfvars_path.exists():
                    logger.warning("tfvars.json not found, generating...")
                    self._generate_tfvars()
                
                self.runner.init()
                self.runner.destroy(var_file=str(self.tfvars_path))
                result.terraform_success = True
                logger.info("✓ Terraform destroy succeeded")
            except TerraformError as e:
                result.terraform_error = str(e)
                logger.error(f"✗ Terraform destroy failed: {e}")
        
        # SDK fallback (conditional)
        should_run_sdk = (
            sdk_fallback == "always" or 
            (sdk_fallback == "on_failure" and not result.terraform_success)
        )
        
        if should_run_sdk:
            if not context:
                logger.error("SDK fallback requested but no context provided")
            else:
                result.sdk_fallback_ran = True
                result.sdk_fallback_results = self._run_sdk_fallback_cleanup(
                    context, dry_run, sdk_timeout_seconds, sdk_max_retries
                )
        
        logger.info("=" * 60)
        logger.info("  TERRAFORM DESTROY - COMPLETE")
        logger.info("=" * 60)
        
        return result
    
    def get_outputs(self) -> dict:
        """Get Terraform outputs (run after deploy)."""
        if self._terraform_outputs is None:
            self._terraform_outputs = self.runner.output()
        return self._terraform_outputs
    
    # =========================================================================
    # Async Streaming Methods (for SSE)
    # =========================================================================
    
    async def deploy_all_async(self, context: Optional['DeploymentContext'] = None, skip_credential_check: bool = False):
        """
        Deploy all infrastructure with async streaming.
        
        Yields log lines for SSE streaming. Uses async subprocess for Terraform
        and async HTTP for Azure Kudu deployments.
        
        Args:
            context: DeploymentContext for SDK operations (REQUIRED)
            skip_credential_check: Skip pre-deployment credential validation
            
        Yields:
            Log lines during deployment
        """
        import asyncio
        from src.providers.azure.layers.deployment_helpers import (
            deploy_to_kudu_async,
            get_publishing_credentials_async
        )
        from src.providers.terraform.package_builder import build_azure_user_bundle
        
        if context is None:
            raise ValueError("DeploymentContext is required for SDK operations.")
        
        yield "=" * 60
        yield "  TERRAFORM DEPLOYMENT - STARTING"
        yield "=" * 60
        
        # Step 0: Validate credentials (sync, fast)
        if not skip_credential_check:
            yield "\n[STEP 0/9] Validating cloud credentials..."
            self._validate_credentials()
            yield "✓ Credentials validated"
        else:
            yield "\n[STEP 0/9] Skipping credential validation"
        
        # Step 0.5: Initialize providers (sync, fast)
        yield "\n[STEP 0.5/9] Initializing cloud providers..."
        self._initialize_providers(context)
        yield "✓ Providers initialized"
        
        # Step 1: Validate project (sync, fast)
        yield "\n[STEP 1/9] Validating project structure..."
        from src.validation.directory_validator import validate_project_directory
        validate_project_directory(self.project_path)
        yield "✓ Project validation passed"
        
        # Step 2: Build packages (sync, fast)
        yield "\n[STEP 2/9] Building function packages..."
        self._build_packages()
        yield "✓ Packages built"
        
        # Step 3: Generate tfvars (sync, fast)
        yield "\n[STEP 3/9] Generating tfvars.json..."
        self._generate_tfvars()
        yield f"✓ Generated: {self.tfvars_path}"
        
        # Step 4: Terraform init (async streaming)
        yield "\n[STEP 4/9] Terraform init..."
        async for line in self.runner.init_async():
            yield line
        
        # Step 5: Terraform apply (async streaming)
        yield "\n[STEP 5/9] Terraform apply..."
        async for line in self.runner.apply_async(str(self.tfvars_path)):
            yield line
        
        # Get outputs
        self._terraform_outputs = self.runner.output()
        yield f"✓ Terraform outputs: {list(self._terraform_outputs.keys())}"
        
        # Step 6: Deploy Azure function code (async with streaming)
        yield "\n[STEP 6/9] Deploying Azure function code..."
        providers_config = self._load_providers_config()
        
        if providers_config.get("layer_2_provider") == "azure":
            app_name = self._terraform_outputs.get("azure_user_functions_app_name")
            rg_name = self._terraform_outputs.get("azure_resource_group_name")
            
            if app_name and rg_name:
                provider = context.providers.get("azure")
                if provider:
                    # Build ZIP
                    combined_zip_path = build_azure_user_bundle(self.project_path, providers_config)
                    if combined_zip_path and combined_zip_path.exists():
                        with open(combined_zip_path, "rb") as f:
                            zip_bytes = f.read()
                        
                        # Get credentials (async, uses executor)
                        yield "  Getting publishing credentials..."
                        web_client = provider.clients["web"]
                        creds = await get_publishing_credentials_async(web_client, rg_name, app_name)
                        
                        # Deploy via Kudu (async streaming)
                        async for line in deploy_to_kudu_async(
                            app_name=app_name,
                            zip_content=zip_bytes,
                            publish_username=creds.publishing_user_name,
                            publish_password=creds.publishing_password
                        ):
                            yield line
                    else:
                        yield "  No user functions to deploy"
                else:
                    yield "  Azure provider not initialized, skipping Kudu"
            else:
                yield "  No user functions app deployed, skipping"
        else:
            yield "  No Azure layers configured, skipping Kudu"
        
        # Step 7: Post-deployment (sync, moderate - use executor for blocking calls)
        yield "\n[STEP 7/9] Running post-deployment operations..."
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._run_post_deployment(context))
        yield "✓ Post-deployment operations complete"
        
        yield "\n" + "=" * 60
        yield "  TERRAFORM DEPLOYMENT - COMPLETE"
        yield "=" * 60
    
    async def destroy_all_async(self, context: Optional['DeploymentContext'] = None):
        """
        Destroy all resources with async streaming.
        
        Yields log lines for SSE streaming.
        
        Args:
            context: DeploymentContext for SDK cleanup
            
        Yields:
            Log lines during destruction
        """
        import asyncio
        
        yield "=" * 60
        yield "  TERRAFORM DESTROY - STARTING"
        yield "=" * 60
        
        # Load credentials early (needed for pre-destroy and SDK cleanup)
        if context and not context.credentials:
            try:
                context.credentials = self._load_credentials()
            except Exception as e:
                yield f"  ⚠ Could not load credentials: {e}"
        
        # Generate tfvars if needed
        if not self.tfvars_path.exists():
            yield "tfvars.json not found, generating..."
            self._generate_tfvars()
        
        # Terraform init (async)
        yield "\n[STEP 1/4] Terraform init..."
        async for line in self.runner.init_async():
            yield line
        
        # Pre-destroy: Clean SDK-created resources that block terraform destroy
        yield "\n[STEP 2/4] Pre-destroy cleanup..."
        if context and context.credentials:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._pre_destroy_cleanup(context))
            yield "✓ Pre-destroy cleanup complete"
        else:
            yield "  No credentials, skipping"
        
        # Terraform destroy (async streaming)
        yield "\n[STEP 3/4] Terraform destroy..."
        async for line in self.runner.destroy_async(str(self.tfvars_path)):
            yield line
        
        # SDK fallback cleanup (sync, uses executor)
        yield "\n[STEP 4/4] SDK fallback cleanup..."
        if context:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._run_sdk_fallback_cleanup(context, dry_run=False, timeout_seconds=300, max_retries=2)
            )
            yield "✓ SDK cleanup complete"
        else:
            yield "  No context provided, skipping SDK cleanup"
        
        yield "\n" + "=" * 60
        yield "  TERRAFORM DESTROY - COMPLETE"
        yield "=" * 60
    
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
        if "gcp" in used_clouds:
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
        
        # Store credentials on context for SDK fallback cleanup
        context.credentials = credentials
        
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
        if "gcp" in used_clouds and "gcp" not in context.providers:
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
    
    # =========================================================================
    # Pre-Destroy Cleanup Methods
    # =========================================================================
    
    def _pre_destroy_cleanup(self, context: 'DeploymentContext') -> None:
        """Clean SDK-created resources that block terraform destroy.
        
        Called before terraform destroy in the async flow.
        Each cleanup is independently wrapped in try/except so one failure
        does not prevent the others from running.
        """
        # TwinMaker entities + component types (block workspace deletion)
        try:
            self._pre_destroy_twinmaker_entities(context, dry_run=False)
        except Exception as e:
            logger.warning(f"[Pre-Destroy] TwinMaker cleanup failed: {e}")
        
        # Azure diagnostic settings (block resource deletion)
        try:
            azure_creds = context.credentials.get("azure", {})
            if azure_creds:
                from src.providers.azure.diagnostic_settings_helper import DiagnosticSettingsHelper
                from azure.identity import ClientSecretCredential
                credential = ClientSecretCredential(
                    tenant_id=azure_creds["azure_tenant_id"],
                    client_id=azure_creds["azure_client_id"],
                    client_secret=azure_creds["azure_client_secret"]
                )
                helper = DiagnosticSettingsHelper(credential, azure_creds["azure_subscription_id"])
                logger.info("[Pre-Destroy] Cleaning orphaned diagnostic settings...")
                helper.cleanup_orphaned_by_prefix(context.project_name)
        except Exception as e:
            logger.warning(f"[Pre-Destroy] Diagnostic settings cleanup failed: {e}")
    
    def _pre_destroy_twinmaker_entities(self, context: 'DeploymentContext', dry_run: bool = False) -> None:
        """Delete TwinMaker entities and component types before terraform destroy.
        
        The TwinMaker workspace and scenes are managed by Terraform, but entities
        and component types are created via SDK (aws_deployer.py). AWS refuses to
        delete a workspace that still contains entities, so we must clean them first.
        
        Ported from cleanup.py L67-116 (entities + component types only,
        NOT workspace or scenes which Terraform manages).
        """
        import time
        
        providers_config = self._load_providers_config()
        if not self._uses_provider(providers_config, "aws"):
            return
        
        aws_creds = context.credentials.get("aws", {})
        if not aws_creds or not aws_creds.get("aws_access_key_id"):
            return
        
        try:
            import boto3
        except ImportError:
            logger.warning("[Pre-Destroy] boto3 not available, skipping TwinMaker cleanup")
            return
        
        region = aws_creds.get("aws_region", "eu-central-1")
        session = boto3.Session(
            aws_access_key_id=aws_creds["aws_access_key_id"],
            aws_secret_access_key=aws_creds["aws_secret_access_key"],
            region_name=region
        )
        twinmaker = session.client('iottwinmaker')
        prefix = context.project_name
        
        logger.info(f"[Pre-Destroy] TwinMaker: Checking for entities in workspaces matching '{prefix}'...")
        
        try:
            workspaces = twinmaker.list_workspaces()['workspaceSummaries']
        except Exception as e:
            logger.warning(f"[Pre-Destroy] TwinMaker: Could not list workspaces: {e}")
            return
        
        for ws in workspaces:
            if prefix not in ws['workspaceId']:
                continue
            
            workspace_id = ws['workspaceId']
            logger.info(f"[Pre-Destroy] TwinMaker: Cleaning workspace {workspace_id}")
            
            if dry_run:
                logger.info(f"  [DRY RUN] Would delete entities and component types")
                continue
            
            try:
                # Delete entities (async operation in AWS)
                entities = twinmaker.list_entities(workspaceId=workspace_id).get('entitySummaries', [])
                if entities:
                    for entity in entities:
                        twinmaker.delete_entity(
                            workspaceId=workspace_id,
                            entityId=entity['entityId'],
                            isRecursive=True
                        )
                    logger.info(f"  Requested deletion of {len(entities)} entities")
                    
                    # Wait for entities to be fully deleted (up to 60s)
                    start_time = time.time()
                    max_wait = 60
                    while time.time() - start_time < max_wait:
                        remaining = twinmaker.list_entities(workspaceId=workspace_id).get('entitySummaries', [])
                        if not remaining:
                            break
                        remaining_time = int(max_wait - (time.time() - start_time))
                        logger.info(f"  Waiting for {len(remaining)} entities ({remaining_time}s remaining)...")
                        time.sleep(3)
                    else:
                        logger.warning(f"  Timeout waiting for entity deletion, proceeding anyway")
                else:
                    logger.info(f"  No entities found")
                
                # Delete component types (SDK-created, may still reference entities)
                component_types = twinmaker.list_component_types(workspaceId=workspace_id).get('componentTypeSummaries', [])
                for ct in component_types:
                    if ct['componentTypeId'].startswith('com.amazon'):
                        continue  # Skip built-in types
                    ct_id = ct['componentTypeId']
                    for attempt in range(3):
                        try:
                            twinmaker.delete_component_type(workspaceId=workspace_id, componentTypeId=ct_id)
                            logger.info(f"  ✓ Deleted component type: {ct_id}")
                            break
                        except Exception as e:
                            if "being used by entities" in str(e) and attempt < 2:
                                wait = 2 ** attempt
                                logger.warning(f"  Retry {attempt+1}/3 for {ct_id}: waiting {wait}s")
                                time.sleep(wait)
                            else:
                                logger.warning(f"  ✗ Failed to delete {ct_id}: {e}")
                                break
                
                logger.info(f"[Pre-Destroy] TwinMaker: ✓ Workspace {workspace_id} cleaned")
            except Exception as e:
                logger.warning(f"[Pre-Destroy] TwinMaker: Error cleaning {workspace_id}: {e}")
    
    # =========================================================================
    # SDK Fallback Cleanup Methods
    # =========================================================================
    
    def has_deployed_resources(self) -> bool:
        """Check if there are deployed resources in Terraform state."""
        try:
            state = self.runner.show_state()
            resources = state.get("values", {}).get("root_module", {}).get("resources", [])
            return len(resources) > 0
        except Exception as e:
            logger.warning(f"Could not check state: {e}")
            return False
    
    def _run_sdk_fallback_cleanup(
        self, 
        context: 'DeploymentContext',
        dry_run: bool,
        timeout_seconds: int,
        max_retries: int
    ) -> Dict[str, bool]:
        """Run provider-specific SDK cleanup IN PARALLEL."""
        import time
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import Callable
        
        credentials = context.credentials
        providers_config = context.config.providers  # Use context, not file loading
        prefix = context.project_name
        
        outputs = self._get_terraform_outputs_safe()
        platform_user_email = self._get_platform_user_email(context)
        
        # Build tasks with CAPTURED values (avoid lambda closure bug)
        cleanup_tasks: list = []
        
        if self._uses_provider(providers_config, "aws"):
            def aws_task(
                creds=credentials, pfx=prefix,
                cleanup_user=outputs.get("aws_platform_user_created", False),
                email=platform_user_email, dr=dry_run
            ):
                return self._cleanup_provider("aws", creds, pfx, cleanup_user, email, dr)
            cleanup_tasks.append(("aws", aws_task))
        
        if self._uses_provider(providers_config, "azure"):
            def azure_task(
                creds=credentials, pfx=prefix,
                cleanup_user=outputs.get("azure_platform_user_created", False),
                email=platform_user_email, dr=dry_run
            ):
                return self._cleanup_provider("azure", creds, pfx, cleanup_user, email, dr)
            cleanup_tasks.append(("azure", azure_task))
        
        if self._uses_provider(providers_config, "gcp"):
            def gcp_task(creds=credentials, pfx=prefix, dr=dry_run):
                return self._cleanup_provider("gcp", creds, pfx, False, "", dr)
            cleanup_tasks.append(("gcp", gcp_task))
        
        if not cleanup_tasks:
            logger.info("No providers to clean up")
            return {}
        
        # Run IN PARALLEL
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    self._run_with_retry_and_timeout, 
                    task_fn, max_retries, timeout_seconds
                ): name
                for name, task_fn in cleanup_tasks
            }
            
            for future in futures:
                provider = futures[future]
                try:
                    results[provider] = future.result(timeout=timeout_seconds * (max_retries + 1) + 60)
                except Exception as e:
                    logger.error(f"[{provider.upper()}] Cleanup failed: {e}")
                    results[provider] = False
        
        return results
    
    def _run_with_retry_and_timeout(
        self, 
        task_fn,
        max_retries: int, 
        timeout_seconds: int
    ) -> bool:
        """Run task with per-attempt timeout and retry logic."""
        import time
        import threading
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"  Attempt {attempt + 1}/{max_retries + 1}...")
                
                # Per-attempt timeout using threading
                result = [None]
                exception = [None]
                
                def run_task():
                    try:
                        task_fn()
                        result[0] = True
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=run_task, daemon=True)
                thread.start()
                thread.join(timeout=timeout_seconds)
                
                if thread.is_alive():
                    raise TimeoutError(f"Task timed out after {timeout_seconds}s")
                
                if exception[0]:
                    raise exception[0]
                
                return True
                
            except Exception as e:
                logger.warning(f"  Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    wait_time = 5 * (attempt + 1)  # Backoff: 5s, 10s
                    logger.info(f"  Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        return False
    
    def _cleanup_provider(
        self, 
        provider: str, 
        credentials: dict, 
        prefix: str,
        cleanup_user: bool,
        platform_user_email: str,
        dry_run: bool
    ) -> None:
        """Unified cleanup dispatcher with logging."""
        logger.info(f"[{provider.upper()}] Starting SDK cleanup...")
        
        # Uses pre-imported cleanup modules (see top of file) to avoid ThreadPoolExecutor deadlock
        if provider == "aws":
            cleanup_aws_resources(credentials, prefix, cleanup_user, platform_user_email, dry_run=dry_run)
        elif provider == "azure":
            cleanup_azure_resources(credentials, prefix, cleanup_user, platform_user_email, dry_run=dry_run)
        elif provider == "gcp":
            cleanup_gcp_resources(credentials, prefix, dry_run=dry_run)
        
        logger.info(f"[{provider.upper()}] ✓ Cleanup complete")
    
    def _uses_provider(self, providers_config: dict, cloud: str) -> bool:
        """Check if any layer uses the specified cloud provider.
        
        Note: GCP can be specified as either 'gcp' or 'google' in configs.
        Terraform uses 'google' (the provider name), but SDK uses 'gcp'.
        We normalize by checking for both when cloud='gcp'.
        """
        # Check all possible layer keys including L3 sublayers
        layer_keys = [
            "layer_1_provider", "layer_2_provider", 
            "layer_3_provider", "layer_3_hot_provider", "layer_3_cold_provider", "layer_3_archive_provider",
            "layer_4_provider", "layer_5_provider"
        ]
        
        # Handle GCP naming inconsistency: config may use 'google' (Terraform) or 'gcp' (SDK)
        if cloud == "gcp":
            return any(providers_config.get(key) in ("gcp", "google") for key in layer_keys)
        
        return any(providers_config.get(key) == cloud for key in layer_keys)
    
    def _get_platform_user_email(self, context: 'DeploymentContext') -> str:
        """Get platform user email from context.config.user."""
        return context.config.user.get("admin_email", "")
    
    def _get_terraform_outputs_safe(self) -> dict:
        """Get Terraform outputs, returning empty dict on failure."""
        try:
            return self.runner.output()
        except Exception as e:
            logger.warning(f"Could not get Terraform outputs: {e}")
            return {}
