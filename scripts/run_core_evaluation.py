"""Supervised, single-provider Core research run; never full-profile admission.

Run inside the deployment container. All raw output/state remains in a private
directory; stdout contains only phase names, timings and non-identifying counts.
The operator supplies an external cumulative allowance ledger (not cloud billing).
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import traceback
import uuid

from scripts.prepare_core_runtime import ROOT, prepare
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.deployer_strategy import (
    AWS_SIX_LAYER_IMAGE_FOUNDATION_TARGETS, AZURE_SIX_LAYER_IMAGE_FOUNDATION_TARGETS,
    GCP_SIX_LAYER_IMAGE_FOUNDATION_TARGETS,
)


def save(path, value):
    atomic_write_private_bytes(path, (json.dumps(value, indent=2) + "\n").encode())


@contextmanager
def deadline(seconds):
    def expired(*_):
        raise TimeoutError("CORE_DEADLINE")
    old = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def reserve(ledger_path, provider, run_id, cap, amount):
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    used = sum(item["allowance_eur"] for item in ledger if item["provider"] == provider)
    if amount <= 0 or cap <= 0 or used + amount > cap:
        raise RuntimeError("CORE_CUMULATIVE_ALLOWANCE_EXHAUSTED")
    ledger.append({"provider": provider, "run_id": run_id, "allowance_eur": amount})
    save(ledger_path, ledger)


class Terraform:
    def __init__(self, folder, env):
        self.folder, self.env, self.sequence = folder, env, 0

    def run(self, *args):
        self.sequence += 1
        log = self.folder / f"command-{self.sequence:02d}.log"
        with log.open("wb") as output:
            proc = subprocess.Popen(["terraform", *args], cwd=self.folder, env=self.env,
                                    stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = proc.wait()
            except BaseException:
                os.killpg(proc.pid, signal.SIGINT)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise
        if code:
            raise RuntimeError(f"TERRAFORM_{args[0].upper()}_FAILED_LOG_{self.sequence:02d}")
        return log

    def outputs(self):
        return {k: v["value"] for k, v in json.loads(self.run("output", "-json").read_text()).items()}


def run(args):
    os.umask(0o077)
    def interrupted(*_):
        raise SystemExit("CORE_TERMINATED")
    signal.signal(signal.SIGTERM, interrupted)
    provider = args.provider
    run_id = "core" + provider + "-" + uuid.uuid4().hex[:8]
    root = args.output_dir.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = prepare(provider, root / "runtime")
    values["digital_twin_name"] = run_id
    save(root / "runtime/config.json", {"digital_twin_name": run_id})
    credentials = json.loads(args.credentials.read_text())
    aws = credentials["aws"]
    values.update(aws_access_key_id=aws["aws_access_key_id"],
                  aws_secret_access_key=aws["aws_secret_access_key"])
    # Terraform initializes aliased providers even with zero selected resources.
    values.update({key: credentials["azure"][key] for key in (
        "azure_subscription_id", "azure_client_id", "azure_client_secret", "azure_tenant_id")})
    ops = importlib.import_module("scripts.core_live_" + provider)
    publisher_module = importlib.import_module("src.providers.terraform." + provider + "_six_layer_image_publisher")
    publisher_class = getattr(publisher_module, {"aws": "Aws", "azure": "Azure", "gcp": "Gcp"}[provider] + "SixLayerImagePublisher")
    targets = {"aws": AWS_SIX_LAYER_IMAGE_FOUNDATION_TARGETS,
               "azure": AZURE_SIX_LAYER_IMAGE_FOUNDATION_TARGETS,
               "gcp": GCP_SIX_LAYER_IMAGE_FOUNDATION_TARGETS}[provider]
    if provider == "aws":
        account = ops.session(values).client("sts").get_caller_identity()["Account"]
        values["aws_six_layer_storage_mover_image"] = (
            f"{account}.dkr.ecr.{values['aws_region']}.amazonaws.com/{run_id}-six-images@sha256:" + "0" * 64
        )
    elif provider == "azure":
        values["azure_six_layer_storage_mover_image"] = "unpublished.azurecr.io/storage-mover@sha256:" + "0" * 64
    else:
        info = json.loads(args.gcp_credentials.read_text())
        if info["project_id"] != credentials["gcp"]["gcp_project_id"]:
            raise RuntimeError("CORE_GCP_PROJECT_MISMATCH")
        values.update(gcp_credentials_json=json.dumps(info), gcp_project_id=info["project_id"],
                      gcp_deployment_principal_email=info["client_email"])
        values.update(publisher_module.placeholder_image_tfvars(values))
    folder = root / "terraform"
    shutil.copytree(ROOT / "3-cloud-deployer/src/terraform", folder,
                    ignore=shutil.ignore_patterns(".terraform", "*.tfstate*", "*.tfplan"))
    if args.provider_cache:
        shutil.copytree(args.provider_cache, folder / ".terraform")
    env = dict(os.environ, TF_IN_AUTOMATION="1", TF_INPUT="0")
    for key, value in values.items():
        env["TF_VAR_" + key] = json.dumps(value) if not isinstance(value, str) else value
    tf = Terraform(folder, env)
    report = {"provider": provider, "scope": "core", "green": False}
    outputs, mutated = {}, False

    def phase(name, action):
        print(provider + ": " + name, flush=True)
        started = time.monotonic()
        result = action()
        report[name + "_seconds"] = round(time.monotonic() - started, 3)
        save(root / "report.json", report)
        return result

    try:
        phase("initialize", lambda: tf.run("init", "-no-color"))
        baseline = phase("baseline_inventory", lambda: ops.inventory(values, run_id))
        if any(baseline.values()):
            raise RuntimeError("CORE_PREFIX_NOT_EMPTY")
        phase("review_plan", lambda: tf.run("plan", "-no-color", "-out=review.plan"))
        plan = json.loads(tf.run("show", "-json", "review.plan").read_text())
        changes = [r for r in plan.get("resource_changes", []) if r["mode"] == "managed"]
        if any(r["change"]["actions"] not in (["create"], ["no-op"]) for r in changes):
            raise RuntimeError("CORE_PLAN_NOT_CREATE_ONLY")
        report["create_counts"] = {}
        for resource in changes:
            kind = resource["type"]
            prefixes = {"aws": ("aws_", "awscc_"), "azure": ("azurerm_", "azapi_"),
                        "gcp": ("google_", "kubernetes_", "tls_", "local_")}[provider]
            if not kind.startswith(prefixes + ("random_", "terraform_")):
                raise RuntimeError("CORE_WRONG_PROVIDER_RESOURCE")
            report["create_counts"][kind] = report["create_counts"].get(kind, 0) + 1
        print(json.dumps({"provider": provider, "create_counts": report["create_counts"]}), flush=True)
        reserve(args.ledger, provider, run_id, args.cap_eur, args.reserve_eur)
        mutated = True  # Set before the first mutation, including partial failure.
        with deadline(args.functional_seconds):
            phase("image_foundation", lambda: tf.run("apply", "-auto-approve", "-no-color",
                  *["-target=" + target for target in targets]))
            outputs = tf.outputs()
            publisher = publisher_class.from_tfvars_and_outputs(
                project_path=root / "runtime", tfvars=values, outputs=outputs)
            images = phase("publish_images", lambda: publisher.publish(
                publisher_module.image_requests(root / "runtime", values)))
            values.update(publisher_module.image_tfvars(images, values))
            for key, value in values.items():
                env["TF_VAR_" + key] = json.dumps(value) if not isinstance(value, str) else value
            save(root / "image-digests.json", images)
            phase("deploy", lambda: tf.run("apply", "-auto-approve", "-no-color"))
            if provider == "gcp":
                values["gcp_six_layer_kubernetes_stage_enabled"] = True
                env["TF_VAR_gcp_six_layer_kubernetes_stage_enabled"] = "true"
                phase("deploy_kubernetes", lambda: tf.run("apply", "-auto-approve", "-no-color"))
            outputs = tf.outputs()
            report["verification"] = phase("verify", lambda: ops.smoke(values, outputs))
    except BaseException as exc:
        atomic_write_private_bytes(root / "failure.log", traceback.format_exc().encode())
        # Do not emit exception text: provider errors may contain secret payloads.
        report["failure_type"] = type(exc).__name__
        if isinstance(exc, (RuntimeError, TimeoutError)) and str(exc).replace("_", "").isalnum():
            report["failure_code"] = str(exc)
        print(provider + ": failed (" + report["failure_type"] + ")", flush=True)
    finally:
        if mutated:
            if hasattr(ops, "diagnostics"):
                try:
                    with deadline(60):
                        save(root / "runtime-diagnostics.json", ops.diagnostics(values, outputs))
                except BaseException as exc:
                    report["diagnostics_error"] = type(exc).__name__
            try:
                with deadline(1200):
                    phase("stop_builds", lambda: ops.stop_builds(values, outputs))
            except BaseException as exc:
                report["stop_builds_error"] = type(exc).__name__
            try:
                if provider == "gcp" and values.get("gcp_six_layer_kubernetes_stage_enabled"):
                    with deadline(300):
                        # Keep GKE alive until its controller removes LoadBalancer children.
                        env["TF_VAR_gcp_six_layer_kubernetes_stage_enabled"] = "false"
                        phase("remove_kubernetes", lambda: tf.run("apply", "-auto-approve", "-no-color"))
            except BaseException as exc:
                report["kubernetes_cleanup_error"] = type(exc).__name__
                # Full destroy must still be attempted if stage removal fails.
                env["TF_VAR_gcp_six_layer_kubernetes_stage_enabled"] = "true"
            try:
                if hasattr(ops, "before_destroy") and (folder / "terraform.tfstate").exists():
                    with deadline(60):
                        phase("prepare_destroy", lambda: ops.before_destroy(values,
                              json.loads((folder / "terraform.tfstate").read_text())))
            except BaseException as exc:
                report["prepare_destroy_error"] = type(exc).__name__
            try:
                with deadline(1200):
                    phase("destroy", lambda: tf.run("destroy", "-auto-approve", "-no-color"))
                report["destroy_succeeded"] = True
            except BaseException as exc:
                report["cleanup_error"] = type(exc).__name__
            try:
                with deadline(180):
                    for _ in range(6):
                        remaining = phase("residual_inventory", lambda: ops.inventory(values, run_id))
                        if not any(value for key, value in remaining.items() if not key.startswith("pending_deletion:")):
                            break
                        time.sleep(10)
                    report["residual_counts"] = remaining
            except BaseException as exc:
                report["inventory_error"] = type(exc).__name__
        report["functional_passed"] = bool(report.get("verification") and not report.get("failure_type"))
        report["green"] = bool(report.get("verification") and report.get("destroy_succeeded")
                               and "residual_counts" in report and not any(report["residual_counts"].values())
                               and not report.get("failure_type") and not report.get("stop_builds_error"))
        save(root / "report.json", report)
        print(json.dumps(report), flush=True)
    return 0 if report["green"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("aws", "azure", "gcp"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--gcp-credentials", type=Path)
    parser.add_argument("--provider-cache", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--cap-eur", type=float, required=True)
    parser.add_argument("--reserve-eur", type=float, required=True)
    parser.add_argument("--functional-seconds", type=int, default=1200)
    raise SystemExit(run(parser.parse_args()))
