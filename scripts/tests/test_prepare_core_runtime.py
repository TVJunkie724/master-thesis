"""Real processor/package preparation must remain local and incomplete."""

import hashlib
import json
import zipfile

import pytest

from scripts.prepare_core_runtime import prepare


@pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
def test_real_core_packages_keep_scope_and_digest_binding(tmp_path, provider):
    output = tmp_path / provider
    values = prepare(provider, output)
    assert values["evaluation_scope"] == "core"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert not any(key.endswith("_image") for key in values)
    assert not any("credential" in key or "secret" in key for key in values)
    package = output / ".build" / provider / "core-processor.zip"
    expected = "sha256:" + hashlib.sha256(package.read_bytes()).hexdigest()
    assert values["validated_extension_packages"][0]["package_digest"] == expected
    evidence = json.loads((output / "processor-package-evidence.json").read_text())
    assert evidence["provider"] == provider
    assert evidence["package_digest"] == expected
    with zipfile.ZipFile(package) as archive:
        assert {"process.py", "_platform_runtime.py", "_extension_config.json"} <= set(
            archive.namelist()
        )
    assert not (output / "deployment_manifest.json").exists()
    with pytest.raises(FileExistsError):
        prepare(provider, output)


def test_nonlocal_or_unknown_provider_rejected_before_creating_files(tmp_path):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError):
        prepare("aws-to-gcp", output)
    assert not output.exists()
