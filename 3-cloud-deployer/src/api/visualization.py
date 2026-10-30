"""Read the fixed deployed L5 surface with one request-scoped credential package."""
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse, Response

from src.api.operation_context import operation_project_path
from src.core.config_loader import ProjectConfigLoader
from src.deployment_access.visualization import fetch_visualization
from src.providers.terraform.provider_runtime import initialize_providers
from src.runtime_outputs import load_terraform_outputs
from src.runtime.six_layer_eventing.visualization import HEADERS

router = APIRouter(tags=["Layer Access"])


@router.get("/projects/{project_name}/visualization", response_class=HTMLResponse)
def get_visualization(project_name: str, operation_token: Annotated[str, Header(alias="X-Operation-Package")]):
    with operation_project_path(project_name, operation_token) as project_path:
        try:
            context = ProjectConfigLoader().create_context_from_path(project_name, project_path)
            provider = context.config.providers.get("layer_5_provider")
            if provider not in {"aws", "azure"}:
                raise ValueError("Unsupported visualization provider")
            initialize_providers(context, {"layer_5_provider": provider}, context.credentials)
            outputs = load_terraform_outputs(project_name, project_path)
            html = fetch_visualization(provider, context.providers[provider], outputs)
        except Exception as exc:
            # Upstream URLs, keys and Terraform state never enter HTTP errors.
            raise HTTPException(502, "Deployed L5 visualization is unavailable") from exc
    return Response(content=html, headers=HEADERS)
