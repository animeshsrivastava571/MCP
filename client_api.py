from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI(title="Client Wrapper for MCP Add API")

# MCP wrapper API endpoint
MCP_WRAPPER_URL = "http://127.0.0.1:8000/add"

class AddRequest(BaseModel):
    a: int
    b: int

@app.post("/call_add")
def call_wrapped_mcp_add(req: AddRequest):
    try:
        response = requests.post(MCP_WRAPPER_URL, json={"a": req.a, "b": req.b})
        response.raise_for_status()
        return {"proxied_result": response.json()["sum"]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def root():
    return {
        "message": "Use POST /call_add to reach MCP-wrapped /add endpoint at http://127.0.0.1:8000/add"
    }
