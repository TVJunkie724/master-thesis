from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import aws.lambda_manager as lambda_manager
from aws.api_lambda_schemas import LambdaUpdateRequest, LambdaLogsRequest, LambdaInvokeRequest
from logger import print_stack_trace, logger

router = APIRouter()

@router.post("/lambda_update", tags=["AWS"])
def lambda_update(req: LambdaUpdateRequest):
    """
    Update an AWS Lambda function with the latest local code.

    Behavior:
    - If `local_function_name` is "default-processor", updates all processor Lambdas for each IoT device.
    - Otherwise, updates a single Lambda function by name.
    - Optionally updates the Lambda environment variables if `environment` is provided.

    Parameters:
    - local_function_name: Name of the local Lambda function to update.
    - environment: JSON string defining environment variables to set (optional).

    Returns:
        JSON message confirming the update.
    """
    try:
        if req.environment:
            lambda_manager.update_function(req.local_function_name, req.environment)
        else:
            lambda_manager.update_function(req.local_function_name)
        return {"message": f"Lambda {req.local_function_name} updated successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/lambda_logs", tags=["AWS"])
def get_lambda_logs(req: LambdaLogsRequest = Depends()) -> List[str]:
    """
    Fetch the most recent log messages from a specified Lambda function.

    Parameters:
    - local_function_name: Name of the local Lambda function to fetch logs from.
    - n: Number of log lines to return (default 10).
    - filter_system_logs: Whether to exclude AWS system log messages (default True).

    Returns:
        List of log messages as strings.
    """
    try:
        logs = lambda_manager.fetch_logs(req.local_function_name, n=req.n, filter_system_logs=req.filter_system_logs)
        return logs
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/lambda_invoke", tags=["AWS"])
def lambda_invoke(req: LambdaInvokeRequest):
    """
    Invokes a lambda function.
    """
    try:
        lambda_manager.invoke_function(req.local_function_name, req.payload, req.sync)
        return {"message": f"Lambda {req.local_function_name} invoked successfully"}
    except Exception as e:
        print_stack_trace()
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
