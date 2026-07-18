"""Production image build-context security invariants."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_docker_context_excludes_secrets_and_local_runtime_artifacts():
    patterns = {
        line.strip()
        for line in (PROJECT_ROOT / ".dockerignore").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        "**/__pycache__/",
        "**/*.py[cod]",
        ".local/",
        "**/.terraform/",
        ".terraform.d/",
        "**/*.tfstate",
        "**/*.tfvars.json",
        "upload/",
    } <= patterns
