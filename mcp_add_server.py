from fastapi import FastAPI
from pydantic import BaseModel
from fastmcp import FastMCP, Client

# Initialize FastMCP server and register the tool
mcp = FastMCP("MyAssistantServer")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers and return the sum."""
    return a + b

# Initialize FastAPI application
app = FastAPI()

# Define a Pydantic model for the request body
class AddRequest(BaseModel):
    a: int
    b: int

# FastAPI endpoint that uses the MCP tool internally

@app.post("/add")
async def add_numbers(payload: AddRequest):
    async with Client(mcp) as client:
        result = await client.call_tool("add", {"a": payload.a, "b": payload.b})
        final_result = result[0].text  # ✅ Fix here
        return {"sum": int(final_result)}

