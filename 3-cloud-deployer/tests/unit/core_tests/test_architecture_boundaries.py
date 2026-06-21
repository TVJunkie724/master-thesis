"""
Architecture boundary tests for the Deployer codebase.

These tests prevent the legacy direct AWS deployment stack from becoming a
production dependency again. The canonical production path is:

    src.api.deployment -> src.providers.deployer -> TerraformDeployerStrategy
"""

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
LEGACY_AWS_ROOT = SRC_ROOT / "aws"


def _production_python_files() -> list[Path]:
    return sorted(
        path
        for path in SRC_ROOT.rglob("*.py")
        if LEGACY_AWS_ROOT not in path.parents
    )


def _legacy_aws_imports(path: Path) -> list[str]:
    import_pattern = re.compile(r"^\s*import\s+((?:src\.)?aws(?:\.|\b)[^\s,]*)")
    from_pattern = re.compile(r"^\s*from\s+((?:src\.)?aws(?:\.|\b)[^\s]*)\s+import\s+")
    violations: list[str] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        import_match = import_pattern.match(line)
        if import_match:
            violations.append(f"{path.relative_to(PROJECT_ROOT)}:{line_number} imports {import_match.group(1)}")
            continue

        from_match = from_pattern.match(line)
        if from_match:
            violations.append(f"{path.relative_to(PROJECT_ROOT)}:{line_number} imports from {from_match.group(1)}")

    return violations


def test_production_code_does_not_import_legacy_aws_stack():
    violations = [
        violation
        for path in _production_python_files()
        for violation in _legacy_aws_imports(path)
    ]

    assert violations == []


def test_deployment_orchestration_uses_cleanup_registry_boundary():
    """Orchestration must not import provider cleanup modules directly."""
    orchestration_files = [
        SRC_ROOT / "providers" / "deployer.py",
        SRC_ROOT / "providers" / "terraform" / "deployer_strategy.py",
    ]
    forbidden_imports = (
        "src.providers.aws.cleanup",
        "src.providers.azure.cleanup",
        "src.providers.gcp.cleanup",
    )

    violations = []
    for path in orchestration_files:
        text = path.read_text(encoding="utf-8")
        for forbidden_import in forbidden_imports:
            if forbidden_import in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {forbidden_import}")

    assert violations == []
