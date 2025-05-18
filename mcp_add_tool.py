from langchain_core.tools import tool
import requests

@tool
def add(a: int, b: int) -> str:
    """Add two numbers using the MCP server running at http://localhost:8000/add"""
    try:
        response = requests.post("http://localhost:8000/add", json={"a": a, "b": b})
        response.raise_for_status()
        result = response.json()["sum"]
        return f"The sum of {a} and {b} is {result}."
    except Exception as e:
        return f"Error calling MCP server: {str(e)}"
