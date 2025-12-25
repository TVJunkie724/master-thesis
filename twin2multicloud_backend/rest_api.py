import sys
import io
import subprocess
import json
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "API is running"}
