"""
Terraform CLI Wrapper for Hybrid Deployment.

This module provides a Python interface to Terraform for the hybrid deployment
approach where Terraform handles infrastructure and Python handles dynamic
operations (DTDL upload, Grafana config, function code deployment).

Usage:
    from terraform_runner import TerraformRunner
    
    runner = TerraformRunner(terraform_dir="/app/src/terraform")
    runner.init()
    runner.plan(var_file="/app/upload/my_project/terraform/generated.tfvars.json")
    runner.apply()
    outputs = runner.output()
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
    
    def __init__(self, terraform_dir: str):
        """
        Initialize the Terraform runner.
        
        Args:
            terraform_dir: Absolute path to the Terraform configuration directory
                           (typically /app/src/terraform inside Docker)
        
        Raises:
            ValueError: If terraform_dir is empty or None
        """
        if not terraform_dir:
            raise ValueError("terraform_dir is required")
        
        self.terraform_dir = Path(terraform_dir)
        
        if not self.terraform_dir.exists():
            raise ValueError(f"Terraform directory does not exist: {terraform_dir}")
    
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
        cmd = ["terraform", f"-chdir={self.terraform_dir}"] + args
        logger.info(f"Running: {' '.join(cmd)}")
        
        if stream_output:
            # For long-running commands, stream output to console and capture for error handling
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output line by line and collect it
            output_lines = []
            for line in process.stdout:
                print(line, end='', flush=True)
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
            result = subprocess.run(
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
            out_file: Optional path to save the plan (defaults to tfplan in terraform_dir)
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
            out_file = str(self.terraform_dir / "tfplan")
        
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
