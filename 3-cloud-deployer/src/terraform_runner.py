"""
Terraform CLI Wrapper for Hybrid Deployment.

This module provides a Python interface to Terraform for the hybrid deployment
approach where Terraform handles infrastructure and Python handles dynamic
operations (DTDL upload, Grafana config, function code deployment).

Usage:
    from terraform_runner import TerraformRunner
    
    runner = TerraformRunner(
        terraform_dir="/app/src/terraform",
        state_path="/app/upload/my_project/terraform/terraform.tfstate"
    )
    runner.init()
    runner.plan(var_file="/app/upload/my_project/terraform/generated.tfvars.json")
    runner.apply()
    outputs = runner.output()
"""

import asyncio
# The executable is fixed and every argument is validated before invocation.
import subprocess  # nosec B404
import json
import logging
from pathlib import Path
from typing import Optional

from src.core.observability import redact_sensitive

logger = logging.getLogger(__name__)

_ALLOWED_TERRAFORM_COMMANDS = frozenset(
    {"apply", "destroy", "init", "output", "plan", "show", "state", "validate"}
)
_STATEFUL_COMMANDS = frozenset({"apply", "destroy", "output", "plan", "show"})


class TerraformError(Exception):
    """Raised when a Terraform command fails."""
    
    def __init__(self, command: str, return_code: int, stderr: str):
        self.command = command
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(f"Terraform {command} failed (exit {return_code}): {stderr}")


class TerraformRunner:
    """
    Wraps Terraform CLI commands for the hybrid deployment approach.
    
    The runner executes Terraform commands against the static configuration
    in src/terraform/, using per-project variable files for customization.
    
    Attributes:
        terraform_dir: Path to the Terraform configuration directory
    """
    
    def __init__(self, terraform_dir: str, state_path: str = None):
        """
        Initialize the Terraform runner.
        
        Args:
            terraform_dir: Absolute path to the Terraform configuration directory
                           (typically /app/src/terraform inside Docker)
            state_path: Optional absolute path to terraform.tfstate file
                       (for per-project state isolation)
        
        Raises:
            ValueError: If terraform_dir is empty or None
        """
        if not terraform_dir:
            raise ValueError("terraform_dir is required")
        
        self.terraform_dir = Path(terraform_dir)
        self.state_path = Path(state_path) if state_path else None
        
        if not self.terraform_dir.exists():
            raise ValueError(f"Terraform directory does not exist: {terraform_dir}")

    def _default_plan_path(self) -> Path:
        """Return the default plan path for this runner's workspace."""
        if self.state_path:
            return self.state_path.parent / "tfplan"
        return self.terraform_dir / "tfplan"

    def _build_command(
        self,
        args: list[str],
        *,
        no_color: bool = False,
    ) -> list[str]:
        """Build one allowlisted Terraform command without shell interpretation."""
        if not args:
            raise ValueError("Terraform subcommand is required")
        if args[0] not in _ALLOWED_TERRAFORM_COMMANDS:
            raise ValueError(f"Terraform subcommand is not allowed: {args[0]}")
        if any(
            not isinstance(argument, str) or "\x00" in argument or "\n" in argument
            for argument in args
        ):
            raise ValueError("Terraform arguments must be single-line strings")

        subcommand = args[0]
        command = ["terraform", f"-chdir={self.terraform_dir}", subcommand]
        if subcommand == "state":
            if len(args) != 2 or args[1] != "list":
                raise ValueError("Only 'terraform state list' is allowed")
            command.append("list")
            if self.state_path:
                command.append(f"-state={self.state_path}")
            return command
        if no_color:
            command.append("-no-color")
        if self.state_path and subcommand in _STATEFUL_COMMANDS:
            command.append(f"-state={self.state_path}")
        command.extend(args[1:])
        return command

    def state_list(self) -> subprocess.CompletedProcess:
        """List resources from the isolated project state without cloud mutation."""
        return self._run_command(["state", "list"], check=False)

    def refresh_only_plan(self, var_file: str) -> subprocess.CompletedProcess:
        """Run drift detection and preserve Terraform's detailed exit code."""
        if not var_file:
            raise ValueError("var_file is required")
        return self._run_command(
            [
                "plan",
                "-refresh-only",
                "-detailed-exitcode",
                f"-var-file={var_file}",
            ],
            check=False,
        )
    
    def _run_command(
        self,
        args: list[str],
        capture_output: bool = True,
        check: bool = True,
        stream_output: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Run a Terraform command.
        
        Args:
            args: Command arguments (without 'terraform' prefix)
            capture_output: Whether to capture stdout/stderr (ignored if stream_output=True)
            check: Whether to raise on non-zero exit
            stream_output: If True, stream output to console (for long-running commands)
        
        Returns:
            CompletedProcess with command results
        
        Raises:
            TerraformError: If command fails and check=True
        """
        cmd = self._build_command(args)
        
        logger.info(f"Running: {' '.join(cmd)}")
        
        if stream_output:
            # For long-running commands, stream output to console and capture for error handling
            # Command comes exclusively from _build_command's allowlist.
            process = subprocess.Popen(  # nosec B603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output line by line and collect it
            output_lines = []
            for line in process.stdout:
                logger.info("%s", redact_sensitive(line.rstrip()))
                output_lines.append(line)
            
            process.wait()
            captured_output = ''.join(output_lines)
            
            result = subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=captured_output,
                stderr=None
            )
        else:
            # Command comes exclusively from _build_command's allowlist.
            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=capture_output,
                text=True,
                check=False
            )
        
        if check and result.returncode != 0:
            # Combine stdout and stderr for full error context
            error_output = ""
            if result.stdout:
                error_output += result.stdout
            if result.stderr:
                error_output += "\n" + result.stderr if error_output else result.stderr
            if not error_output:
                error_output = "No output captured"
            raise TerraformError(args[0], result.returncode, error_output)
        
        return result
    
    def init(self, backend: bool = True, upgrade: bool = False) -> None:
        """
        Initialize Terraform (download providers).
        
        Args:
            backend: Whether to initialize backend (use False for validation only)
            upgrade: Whether to upgrade providers to latest versions
        
        Raises:
            TerraformError: If init fails
        """
        args = ["init"]
        
        if not backend:
            args.append("-backend=false")
        
        if upgrade:
            args.append("-upgrade")
        
        logger.info("Initializing Terraform...")
        self._run_command(args)
        logger.info("✓ Terraform initialized")
    
    def validate(self) -> bool:
        """
        Validate the Terraform configuration.
        
        Returns:
            True if configuration is valid
        
        Raises:
            TerraformError: If validation fails
        """
        logger.info("Validating Terraform configuration...")
        self._run_command(["validate"])
        logger.info("✓ Configuration is valid")
        return True
    
    def plan(
        self,
        var_file: str,
        out_file: Optional[str] = None,
        destroy: bool = False
    ) -> str:
        """
        Create an execution plan.
        
        Args:
            var_file: Path to the tfvars.json file
            out_file: Optional path to save the plan. Defaults to the project
                      workspace when state_path is set, otherwise terraform_dir.
            destroy: If True, plan for destruction instead of creation
        
        Returns:
            Path to the saved plan file
        
        Raises:
            ValueError: If var_file is empty
            TerraformError: If plan fails
        """
        if not var_file:
            raise ValueError("var_file is required")
        
        if out_file is None:
            out_file = str(self._default_plan_path())
        else:
            out_file = str(Path(out_file))

        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        
        args = ["plan", f"-var-file={var_file}", f"-out={out_file}"]
        
        if destroy:
            args.append("-destroy")
        
        logger.info(f"Creating execution plan (var_file={var_file})...")
        self._run_command(args)
        logger.info(f"✓ Plan saved to {out_file}")
        
        return out_file
    
    def apply(
        self,
        plan_file: Optional[str] = None,
        var_file: Optional[str] = None,
        auto_approve: bool = True
    ) -> None:
        """
        Apply the Terraform plan.
        
        Args:
            plan_file: Path to a saved plan file (from plan())
            var_file: Path to tfvars.json (required if plan_file not provided)
            auto_approve: Skip interactive approval
        
        Raises:
            ValueError: If neither plan_file nor var_file is provided
            TerraformError: If apply fails
        """
        if plan_file is None and var_file is None:
            raise ValueError("Either plan_file or var_file must be provided")
        
        args = ["apply"]
        
        if auto_approve:
            args.append("-auto-approve")
        
        if plan_file:
            args.append(plan_file)
        elif var_file:
            args.append(f"-var-file={var_file}")
        
        logger.info("Applying Terraform configuration...")
        self._run_command(args, stream_output=True)
        logger.info("✓ Apply complete")
    
    def destroy(
        self,
        var_file: str,
        auto_approve: bool = True
    ) -> None:
        """
        Destroy all managed resources.
        
        Args:
            var_file: Path to the tfvars.json file
            auto_approve: Skip interactive approval
        
        Raises:
            ValueError: If var_file is empty
            TerraformError: If destroy fails
        """
        if not var_file:
            raise ValueError("var_file is required")
        
        args = ["destroy", f"-var-file={var_file}"]
        
        if auto_approve:
            args.append("-auto-approve")
        
        logger.info("Destroying Terraform-managed resources...")
        self._run_command(args, stream_output=True)
        logger.info("✓ Destroy complete")
    
    def output(self, name: Optional[str] = None) -> dict:
        """
        Get Terraform outputs.
        
        Args:
            name: Optional specific output name (returns all if None)
        
        Returns:
            Dictionary of outputs (or single value if name specified)
        
        Raises:
            TerraformError: If output command fails
        """
        args = ["output", "-json"]
        
        if name:
            args.append(name)
        
        result = self._run_command(args, capture_output=True)
        
        if not result.stdout.strip():
            return {}
        
        outputs = json.loads(result.stdout)
        
        # Unwrap the value from Terraform's output format
        if name:
            return outputs
        
        return {k: v.get("value") for k, v in outputs.items()}
    
    def show_state(self) -> dict:
        """
        Show the current Terraform state.
        
        Returns:
            Dictionary representation of the state
        
        Raises:
            TerraformError: If show command fails
        """
        result = self._run_command(["show", "-json"], capture_output=True)
        
        if not result.stdout.strip():
            return {}
        
        return json.loads(result.stdout)

    # =========================================================================
    # Async Streaming Methods (for SSE)
    # =========================================================================
    
    async def _run_command_async(self, args: list[str]):
        """
        Run a Terraform command with async streaming. Yields output lines.
        
        Uses asyncio.subprocess for true async I/O without blocking the event loop.
        
        Args:
            args: Command arguments (without 'terraform' prefix)
            
        Yields:
            Output lines from the command
            
        Raises:
            TerraformError: If command fails
        """
        cmd = self._build_command(args, no_color=True)
        
        logger.info(f"Running (async): {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # Stream output line by line
        async for line in process.stdout:
            decoded = line.decode().rstrip()
            yield decoded
        
        await process.wait()
        
        if process.returncode != 0:
            raise TerraformError(args[0] if args else "terraform", process.returncode, "See streamed output")
    
    async def init_async(self, backend: bool = True, upgrade: bool = False):
        """
        Initialize Terraform with async streaming.
        
        Args:
            backend: Whether to initialize backend
            upgrade: Whether to upgrade providers
            
        Yields:
            Output lines from terraform init
        """
        args = ["init", "-input=false"]
        
        if not backend:
            args.append("-backend=false")
        
        if upgrade:
            args.append("-upgrade")
        
        yield "Initializing Terraform..."
        async for line in self._run_command_async(args):
            yield line
        yield "✓ Terraform initialized"
    
    async def apply_async(self, var_file: str):
        """
        Apply Terraform configuration with async streaming.
        
        Args:
            var_file: Path to the tfvars.json file
            
        Yields:
            Output lines from terraform apply
        """
        if not var_file:
            raise ValueError("var_file is required")
        
        args = ["apply", "-auto-approve", f"-var-file={var_file}"]
        
        yield "Applying Terraform configuration..."
        async for line in self._run_command_async(args):
            yield line
        yield "✓ Apply complete"
    
    async def destroy_async(self, var_file: str):
        """
        Destroy Terraform resources with async streaming.
        
        Args:
            var_file: Path to the tfvars.json file
            
        Yields:
            Output lines from terraform destroy
        """
        if not var_file:
            raise ValueError("var_file is required")
        
        args = ["destroy", "-auto-approve", f"-var-file={var_file}"]
        
        yield "Destroying Terraform-managed resources..."
        async for line in self._run_command_async(args):
            yield line
        yield "✓ Destroy complete"
