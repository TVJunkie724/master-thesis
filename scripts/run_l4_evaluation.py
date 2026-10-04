"""Supervised fixed AWS/Azure L4 experiment. Requires separate live approval.

No Core graph, simulator, federation or L5 is deployed. Invoke once per provider;
inspect cleanup before proceeding. All state/logs/reports are private. No personal
spending limit is stored in this source; --approve-live is an operator interlock,
not a substitute for user authorization or a cloud billing cap.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from types import SimpleNamespace
import uuid

from scripts.prepare_l4_evaluation import prepare, EXPECTED
from scripts.l4_projection_check import check, wait_for, BoundedClient, DEVICE
from scripts.run_core_evaluation import save, terraform_resource_timings, utc_now
from src.providers.azure.layers.layer_4_adt import six_layer_seed


class L4DeadlineExceeded(BaseException):
    """Must escape SDK/application Exception handlers and enter cleanup."""


@contextmanager
def deadline(seconds):
    def expired(*_):
        raise L4DeadlineExceeded()
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def lifecycle(functional, cleanup, inventory, report):
    """Always attempt both cleanup and independent inventory, including on interrupt."""
    try:
        functional()
    except BaseException as exc:
        report["functional_error_type"] = type(exc).__name__
        report["functional_pass"] = False
    finally:
        for name, action in (("cleanup", cleanup), ("inventory", inventory)):
            started = time.monotonic()
            try:
                result = action()
                report[name + "_pass"] = result is True
            except BaseException as exc:
                report[name + "_pass"] = False
                report[name + "_error_type"] = type(exc).__name__
            report[name + "_seconds"] = round(time.monotonic() - started, 3)
    report["passed"] = all(report.get(key) is True for key in
                           ("functional_pass", "cleanup_pass", "inventory_pass"))


def absent(action, missing_codes):
    try:
        action()
        return False
    except Exception as exc:
        response = getattr(exc, "response", {})
        code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
        if code in missing_codes or getattr(exc, "status_code", None) == 404:
            return True
        raise


class Experiment:
    def __init__(self, provider, credentials, terraform_dir, folder):
        self.provider, self.credentials = provider, credentials
        self.tf, self.folder = terraform_dir, folder
        self.variables = json.loads((folder / "private.tfvars.json").read_text())
        self.name = self.variables["digital_twin_name"]
        if not re.fullmatch("l4-" + provider + "-[a-f0-9]{8}", self.name):
            raise ValueError("L4_OWNERSHIP_PREFIX_REJECTED")
        self.report = {"provider": provider, "started_at": utc_now(), "functional_pass": False,
                       "terraform_resource_timings": [], "billed_cost": "pending_attribution"}
        self.report["saved_plan_sha256"] = hashlib.sha256((folder / "review.plan").read_bytes()).hexdigest()
        revision = os.environ.get("L4_SOURCE_REVISION")
        if revision is None:
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True).strip()
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("L4_SOURCE_REVISION_REQUIRED")
        self.report["source_revision"] = revision
        self.sequence, self.data, self.scope, self.role_id = 0, None, None, None
        self.apply_started = False
        self.env = dict(os.environ, TF_IN_AUTOMATION="1", TF_INPUT="0")
        if provider == "aws":
            import boto3
            from botocore.config import Config
            aws = credentials["aws"]
            session = boto3.Session(aws_access_key_id=aws["aws_access_key_id"],
                aws_secret_access_key=aws["aws_secret_access_key"],
                aws_session_token=aws.get("aws_session_token"), region_name=aws["aws_region"])
            config = Config(connect_timeout=10, read_timeout=20, retries={"total_max_attempts": 2, "mode": "standard"})
            self.tm = session.client("iottwinmaker", config=config)
            self.s3 = session.client("s3", config=config)
            self.iam = session.client("iam", config=config)
        else:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource import ResourceManagementClient
            from azure.mgmt.authorization import AuthorizationManagementClient
            azure = credentials["azure"]
            self.credential = ClientSecretCredential(azure["azure_tenant_id"],
                azure["azure_client_id"], azure["azure_client_secret"], retry_total=1)
            subscription = azure["azure_subscription_id"]
            self.arm = ResourceManagementClient(self.credential, subscription, retry_total=1)
            self.auth = AuthorizationManagementClient(self.credential, subscription, retry_total=1)
            plan = json.loads((folder / "plan.json").read_text())
            self.group = next(r["change"]["after"]["name"] for r in plan["resource_changes"]
                              if r["address"] == "azurerm_resource_group.main[0]")
            if not self.group.startswith(self.name):
                raise ValueError("L4_RESOURCE_GROUP_OWNERSHIP_REJECTED")

    def terraform(self, *args):
        self.sequence += 1
        path = self.folder / (f"terraform-{self.sequence:02}.log")
        try:
            with path.open("wb") as log:
                proc = subprocess.Popen(["terraform", *args], cwd=self.tf, env=self.env,
                                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = proc.wait(timeout=1200)
                except BaseException:
                    os.killpg(proc.pid, signal.SIGINT)
                    try:
                        proc.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                    raise
        finally:
            self.report["terraform_resource_timings"].extend(terraform_resource_timings(path))
        if code:
            raise RuntimeError("L4_TERRAFORM_FAILED")
        return path

    def state(self):
        state = self.folder / "fresh.tfstate"
        if not state.exists():
            return {}
        data = json.loads(self.terraform("show", "-json", str(state)).read_text())
        root = data.get("values", {}).get("root_module", {})
        if root.get("child_modules"):
            raise RuntimeError("L4_STATE_SCOPE_REJECTED")
        resources = root.get("resources", [])
        managed = {r["address"]: r["values"] for r in resources if r["mode"] == "managed"}
        if not set(managed) <= EXPECTED[self.provider]:
            raise RuntimeError("L4_STATE_SCOPE_REJECTED")
        return managed

    def functional(self):
        with deadline(1200):
            now = datetime.now(timezone.utc)
            if (now.year, now.month) != ((now + timedelta(hours=1)).year, (now + timedelta(hours=1)).month):
                raise RuntimeError("L4_CROSS_MONTH_COST_REVIEW_REQUIRED")
            if not self.inventory():
                raise RuntimeError("L4_PREFIX_ALREADY_EXISTS")
            if self.provider == "aws":
                pricing = self.tm.get_pricing_plan()
                if pricing.get("currentPricingPlan", {}).get("pricingMode") != "STANDARD":
                    raise RuntimeError("L4_UNREVIEWED_PRICING_MODE")
            started = time.monotonic()
            self.report["apply_started_at"] = utc_now()
            self.apply_started = True
            try:
                self.terraform("apply", "-input=false", "-no-color", "-parallelism=2",
                    "-state=" + str(self.folder / "fresh.tfstate"), str(self.folder / "review.plan"))
            finally:
                self.report["apply_seconds"] = round(time.monotonic() - started, 3)
            resources = self.state()
            if self.provider == "aws":
                workspace = resources["awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0]"]["workspace_id"]
                self.report["projection"] = {}
                result = check("aws", self.tm, self.name, workspace_id=workspace, report=self.report["projection"])
            else:
                from azure.digitaltwins.core import DigitalTwinsClient
                instance = resources["azurerm_digital_twins_instance.azure_azure_digital_twins[0]"]
                self.scope, self.role_id = instance["id"], str(uuid.uuid4())
                save(self.folder / "sdk-owned.json", {"scope": self.scope, "role_id": self.role_id})
                token = self.credential.get_token("https://management.azure.com/.default").token
                claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "===") )
                role = "/providers/Microsoft.Authorization/roleDefinitions/bcd981a7-7f74-457b-83e1-cceb9e632ffe"
                self.auth.role_assignments.create(self.scope, self.role_id, {
                    "role_definition_id": role, "principal_id": claims["oid"], "principal_type": "ServicePrincipal"})
                endpoint = instance["host_name"]
                self.data = DigitalTwinsClient("https://" + endpoint.removeprefix("https://"), self.credential,
                    retry_total=1, connection_timeout=10, read_timeout=20)
                started = time.monotonic()
                def authorized():
                    try:
                        self.data.get_model("dtmi:twin2multicloud:poc:TwinNode;1")
                        return True
                    except Exception as exc:
                        if getattr(exc, "status_code", None) == 404:
                            return True
                        if getattr(exc, "status_code", None) == 403:
                            return False
                        raise
                self.report["role_readiness_attempts"] = wait_for(authorized, attempts=60, interval=3)
                self.report["role_readiness_seconds"] = round(time.monotonic() - started, 3)
                self.report["projection"] = {}
                result = check("azure", self.data, self.name, report=self.report["projection"])
            self.report["functional_pass"] = result["functional_pass"]

    def workspaces(self):
        response = self.tm.list_workspaces(maxResults=100)
        if response.get("nextToken"):
            raise RuntimeError("L4_INVENTORY_PAGINATION_REQUIRES_REVIEW")
        return [w["workspaceId"] for w in response.get("workspaceSummaries", [])
                if w["workspaceId"].startswith(self.name + "-")]

    def cleanup_children(self):
        if self.provider == "aws":
            client = BoundedClient(self.tm, limit=300)
            for workspace in self.workspaces():
                root = dict(workspaceId=workspace, entityId="twin2multicloud-poc-root")
                missing = ("ResourceNotFoundException",)
                if not absent(lambda: client.get_entity(**root), missing):
                    client.delete_entity(**root, isRecursive=True)
                    wait_for(lambda: absent(lambda: client.get_entity(**root), missing))
                component = dict(workspaceId=workspace, componentTypeId=self.name + "-telemetry")
                if not absent(lambda: client.get_component_type(**component), missing):
                    client.delete_component_type(**component)
                    wait_for(lambda: absent(lambda: client.get_component_type(**component), missing))
        elif self.data is not None:
            seed = six_layer_seed(SimpleNamespace(digital_twin_name=self.name, iot_devices=[{"id": DEVICE}]))
            for rel in seed["relationships"]:
                absent(lambda: self.data.delete_relationship(rel["$dtId"], rel["$relationshipId"]), ())
            for twin in reversed(seed["twins"]):
                absent(lambda: self.data.delete_digital_twin(twin["$dtId"]), ())
            for model in seed["models"]:
                absent(lambda: self.data.delete_model(model["@id"]), ())

    def cleanup(self):
        if not self.apply_started:
            return True  # A preflight rejection must never delete an existing prefix.
        errors = []
        started = time.monotonic()
        try:
            self.cleanup_children()
        except Exception as exc:
            errors.append(type(exc).__name__)
        if self.role_id:
            try:
                absent(lambda: self.auth.role_assignments.delete(self.scope, self.role_id), ())
            except Exception as exc:
                errors.append(type(exc).__name__)
        self.report["sdk_cleanup_seconds"] = round(time.monotonic() - started, 3)
        self.report["sdk_cleanup_errors"] = errors
        # Destroy still runs if SDK cleanup failed. Never cancel it at the functional deadline.
        self.state()  # Fail closed against unexpected state before destruction.
        started = time.monotonic()
        self.report["destroy_started_at"] = utc_now()
        try:
            self.terraform("destroy", "-auto-approve", "-input=false", "-no-color", "-parallelism=2",
                "-state=" + str(self.folder / "fresh.tfstate"),
                "-var-file=" + str(self.folder / "private.tfvars.json"),
                *("-target=" + address for address in sorted(EXPECTED[self.provider])))
        finally:
            self.report["destroy_seconds"] = round(time.monotonic() - started, 3)
        return not errors

    def inventory(self):
        if self.provider == "aws":
            workspaces = self.workspaces()
            buckets = self.s3.list_buckets()
            roles = self.iam.list_roles(MaxItems=100)
            if roles.get("IsTruncated") or buckets.get("ContinuationToken"):
                raise RuntimeError("L4_INVENTORY_PAGINATION_REQUIRES_REVIEW")
            counts = {"workspaces": len(workspaces),
                      "buckets": sum(b["Name"].startswith(self.name + "-") for b in buckets.get("Buckets", [])),
                      "roles": sum(r["RoleName"].startswith(self.name + "-") for r in roles.get("Roles", []))}
        else:
            counts = {"resource_groups": int(self.arm.resource_groups.check_existence(self.group))}
            if self.role_id:
                counts["role_assignments"] = int(not absent(lambda:
                    self.auth.role_assignments.get(self.scope, self.role_id), ()))
        self.report["residual_counts"] = counts
        return not any(counts.values())


def run(args):
    if not args.approve_live:
        raise ValueError("L4_EXPLICIT_LIVE_APPROVAL_REQUIRED")
    os.umask(0o077)
    # Preparation creates a fresh, private folder and admits only the exact create-only cut.
    started = time.monotonic()
    prepare(args.provider, args.credentials, args.terraform_dir, args.output_dir)
    experiment = Experiment(args.provider, json.loads(args.credentials.read_text()),
                            args.terraform_dir, args.output_dir)
    experiment.report["plan_seconds"] = round(time.monotonic() - started, 3)
    def interrupted(*_):
        raise SystemExit("L4_INTERRUPTED")
    previous = signal.signal(signal.SIGTERM, interrupted)
    with (args.output_dir / "sdk.log").open("w") as private_log:
        handler = logging.StreamHandler(private_log)
        logging.getLogger().addHandler(handler)
        try:
            with redirect_stdout(private_log), redirect_stderr(private_log):
                lifecycle(experiment.functional, experiment.cleanup, experiment.inventory, experiment.report)
        finally:
            logging.getLogger().removeHandler(handler)
            signal.signal(signal.SIGTERM, previous)
            experiment.report["finished_at"] = utc_now()
            save(args.output_dir / "result.json", experiment.report)
    return {key: experiment.report.get(key) for key in
            ("provider", "functional_pass", "cleanup_pass", "inventory_pass", "passed")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("aws", "azure"))
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--terraform-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--approve-live", action="store_true")
    try:
        result = run(parser.parse_args())
        print(json.dumps(result))
        raise SystemExit(0 if result["passed"] else 1)
    except Exception as exc:
        print(json.dumps({"passed": False, "error_type": type(exc).__name__}))
        raise SystemExit(1)
