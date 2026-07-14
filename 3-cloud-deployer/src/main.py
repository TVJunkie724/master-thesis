"""
Provider-neutral Deployer CLI.

The REST API is the primary production entrypoint. This CLI is kept as a thin
adapter for local operator workflows and delegates to the canonical Terraform
deployer facade.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.factory import create_context  # noqa: E402 - supports direct script execution
from logger import logger  # noqa: E402 - supports direct script execution
from providers.deployer import deploy_all, destroy_all  # noqa: E402 - supports direct script execution


VALID_PROVIDERS = {"aws", "azure", "gcp"}


def _normalize_provider(provider: str) -> str:
    normalized = provider.lower()
    if normalized == "google":
        normalized = "gcp"
    if normalized not in VALID_PROVIDERS:
        raise ValueError(f"Invalid provider '{provider}'. Valid providers are: aws, azure, gcp")
    return normalized


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical Terraform deployer CLI")
    parser.add_argument(
        "--project",
        default="template",
        help="Project context under the upload directory",
    )

    subcommands = parser.add_subparsers(dest="command", required=True)

    for command in ("deploy", "destroy"):
        command_parser = subcommands.add_parser(command)
        command_parser.add_argument(
            "provider",
            choices=sorted(VALID_PROVIDERS | {"google"}),
            help="Provider used for compatibility with the API parameter",
        )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    provider = _normalize_provider(args.provider)
    context = create_context(args.project, provider)

    if args.command == "deploy":
        logger.info(f"Deploying project '{args.project}' via canonical Terraform path")
        outputs = deploy_all(context, provider)
        print(json.dumps({"message": "Deployment completed successfully", "terraform_outputs": outputs}, default=str))
        return 0

    if args.command == "destroy":
        logger.info(f"Destroying project '{args.project}' via canonical Terraform path")
        destroy_all(context, provider)
        print(json.dumps({"message": "Destruction completed successfully"}))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
