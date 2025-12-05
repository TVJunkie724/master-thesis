
from pydantic import BaseModel, Field

class LambdaRequestEnvironment(BaseModel):
    Variables: dict = Field(
        ...,
        example={
            "LOG_LEVEL": "INFO",
            "API_ENDPOINT": "https://api.example.com",
            "ENABLE_DEBUG": "true"
        },
        description="Key-value pairs of environment variables to be set for the Lambda function."
    )


class LambdaUpdateRequest(BaseModel):
    local_function_name: str = Field(
        ...,
        example="default-processor",
        description="Name of the local Lambda function to update. "
                    "If 'default-processor', all processor Lambdas will be updated for each IoT device."
    )
    environment: LambdaRequestEnvironment | None = Field(
        None,
        example={
            "Variables": {
                "LOG_LEVEL": "DEBUG",
                "MAX_RETRIES": "3"
            }
        },
        description="Optional environment configuration for the Lambda function."
    )

    class Config:
        schema_extra = {
            "example": {
                "local_function_name": "temperature-processor",
                "environment": {
                    "Variables": {
                        "LOG_LEVEL": "INFO",
                        "MAX_RETRIES": "5",
                        "API_URL": "https://api.iot.example.com"
                    }
                }
            }
        }
        


class LambdaLogsRequest(BaseModel):
    local_function_name: str = Field(..., description="Name of the local Lambda function to fetch logs from.")
    n: int = Field(10, description="Number of log lines to fetch (default 10).")
    filter_system_logs: bool = Field(True, description="Exclude AWS system logs like INIT_START, START, END, REPORT.")


class LambdaInvokeRequest(BaseModel):
    local_function_name: str = Field(..., description="Name of the local Lambda function to invoke.")
    payload: dict = Field(..., description="JSON payload to pass to the function.")
    sync: bool = Field(True, description="If true, waits for response (RequestResponse). If false, async (Event).")

    class Config:
        schema_extra = {
            "example": {
                "local_function_name": "temperature-processor",
                "payload": {"temperature": 45.5, "unit": "C"},
                "sync": True
            }
        }

