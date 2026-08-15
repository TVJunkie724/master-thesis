"""Five-layer v2 Azure package-to-Terraform input tests."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from src.tfvars_generator import _load_graph_azure_function_zips


def test_loads_content_verified_azure_v2_graph_package(monkeypatch, tmp_path):
    package = tmp_path / ".build" / "azure" / "five-layer-v2.zip"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"deterministic-azure-v2-package")
    graph = SimpleNamespace(content_digest="sha256:graph")
    evidence = tmp_path / ".twin2multicloud" / "graph" / "package-evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        json.dumps(
            {
                "evidence_version": "graph-package-evidence.v1",
                "graph_digest": graph.content_digest,
                "built_packages": [
                    {
                        "package_id": "azure_five-layer-v2",
                        "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(
        "src.providers.terraform.package_builder._selected_static_function_packages",
        lambda _graph: (
            {"aws": (), "azure": ("five-layer-v2",), "gcp": ()},
            {"azure_five-layer-v2"},
        ),
    )

    result = _load_graph_azure_function_zips(tmp_path, graph)

    assert result["azure_v2_zip_path"] == str(package)
