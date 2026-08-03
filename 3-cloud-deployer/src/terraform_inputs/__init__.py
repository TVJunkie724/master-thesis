"""Graph-owned Terraform input translation."""

from .compatibility_projection import provider_projection
from .graph_translator import translate_graph_inputs
from .models import TerraformInputSet
from .serializer import serialize_inputs

__all__ = [
    "TerraformInputSet",
    "provider_projection",
    "serialize_inputs",
    "translate_graph_inputs",
]
