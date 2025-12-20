"""
AWS Gateway API - Lambda management endpoints.

Provides endpoints for updating, invoking, and fetching logs from AWS Lambda functions.
All endpoints require an explicit `project` parameter for stateless API design.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel
import src.providers.aws.lambda_manager as lambda_manager
from src.providers.aws.api_lambda_schemas import LambdaUpdateRequest, LambdaLogsRequest, LambdaInvokeRequest
from logger import print_stack_trace, logger
import src.core.state as state
from src.core.factory import create_context

router = APIRouter()


@router.post("/lambda_update", tags=["AWS"], deprecated=True)
def lambda_update(
    req: LambdaUpdateRequest,
    project: str = Query(..., description="Project name (required)")
):
    """
    Update an AWS Lambda function with the latest local code.

    > **⚠️ DEPRECATED**: Use `POST /functions/update_function/{name}?project=` instead.

    **Parameters:**
    - `project`: Project name (required for stateless API)
    - `local_function_name`: Name of the local Lambda function to update
    - `environment`: JSON string defining environment variables (optional)

    **Behavior:**
    - If `local_function_name` is "default-processor", updates all processor Lambdas
    - Otherwise, updates a single Lambda function by name
    """
    # Protect template project from modifications
    if project == "template":
        raise HTTPException(
            status_code=400,
            detail="Cannot update functions in the 'template' project. It is a protected system folder."
        )
    
    try:
        context = create_context(project, "aws")
        aws_provider = context.providers["aws"]
        
        if req.environment:
            lambda_manager.update_function(
                req.local_function_name, 
                req.environment,
                provider=aws_provider,
                project_path=str(context.project_path),
                iot_devices=context.config.iot_devices
            )
        else:
            lambda_manager.update_function(
                req.local_function_name,
                provider=aws_provider,
                project_path=str(context.project_path),
                iot_devices=context.config.iot_devices
            )
        return {"message": f"Lambda {req.local_function_name} updated successfully", "project": project}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lambda_logs", tags=["AWS"], deprecated=True)
def get_lambda_logs(
    req: LambdaLogsRequest = Depends(),
    project: str = Query(..., description="Project name (required)")
) -> List[str]:
    """
    Fetch the most recent log messages from a specified Lambda function.

    > **⚠️ DEPRECATED**: This endpoint will be removed in a future version.
    > Consider using CloudWatch directly or AWS CLI for log access.

    **Parameters:**
    - `project`: Project name (required for stateless API)
    - `local_function_name`: Name of the local Lambda function
    - `n`: Number of log lines to return (default 10)
    - `filter_system_logs`: Exclude AWS system log messages (default True)

    **Returns:** List of log messages as strings.
    """
    try:
        context = create_context(project, "aws")
        aws_provider = context.providers["aws"]

        logs = lambda_manager.fetch_logs(
            req.local_function_name, 
            n=req.n, 
            filter_system_logs=req.filter_system_logs,
            provider=aws_provider
        )
        return logs
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lambda_invoke", tags=["AWS"], deprecated=True)
def lambda_invoke(
    req: LambdaInvokeRequest,
    project: str = Query(..., description="Project name (required)")
):
    """
    Invoke a Lambda function.

    > **⚠️ DEPRECATED**: This endpoint will be removed in a future version.
    > Use AWS CLI or SDK directly for function invocation.

    **Parameters:**
    - `project`: Project name (required for stateless API)
    - `local_function_name`: Lambda function to invoke
    - `payload`: JSON payload to pass to the function
    - `sync`: Whether to wait for response (default True)
    """
    # Protect template project from modifications
    if project == "template":
        raise HTTPException(
            status_code=400,
            detail="Cannot invoke functions on the 'template' project. It is a protected system folder."
        )
    
    try:
        context = create_context(project, "aws")
        aws_provider = context.providers["aws"]

        lambda_manager.invoke_function(
            req.local_function_name, 
            req.payload, 
            req.sync,
            provider=aws_provider
        )
        return {"message": f"Lambda {req.local_function_name} invoked successfully", "project": project}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
