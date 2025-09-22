import sys
import io
import subprocess
import json
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


@app.get("/api/test")
def test_get(test: str = "default"):
    return {"message": f"Test successful! You sent: {test}"}

@app.post("/api/test")
def test_post(test: str):
    return {"message": f"Test successful! You sent: {test}"}