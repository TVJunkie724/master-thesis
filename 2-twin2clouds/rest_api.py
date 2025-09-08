import sys
import io
import subprocess
import json
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Match your params object
class CalcParams(BaseModel):
    numberOfDevices: int
    deviceSendingIntervalInMinutes: float
    averageSizeOfMessageInKb: float
    hotStorageDurationInMonths: int
    coolStorageDurationInMonths: int
    archiveStorageDurationInMonths: int
    needs3DModel: str
    entityCount: int
    amountOfActiveEditors: int
    amountOfActiveViewers: int
    dashboardRefreshesPerHour: int
    dashboardActiveHoursPerDay: int

@app.put("/api/calc")
def calc(params: CalcParams):
    # Serialize request body to JSON string
    payload = json.dumps(params.dict())

    # Call your Node script with function + JSON payload
    result = subprocess.run(
        ["node", "cost_calculation.js", "calculateCheapestCostsFromApiCall", payload],
        capture_output=True,
        text=True
    )

    
    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    try:
        return {"result": json.loads(result.stdout.strip())}
    except Exception:
        return {"raw_output on error": result.stdout.strip()}
