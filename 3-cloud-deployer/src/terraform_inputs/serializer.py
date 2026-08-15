"""Deterministic serialization for graph-derived Terraform values."""

from __future__ import annotations

import json

from .models import TerraformInputSet


def serialize_inputs(inputs: TerraformInputSet) -> bytes:
    return (
        json.dumps(
            dict(inputs.values),
            ensure_ascii=True,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
