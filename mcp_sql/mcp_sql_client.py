from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Literal, Annotated
from operator import add
import requests
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

# --- LLM
from dotenv import load_dotenv

# Thsis is the slave mcp server

load_dotenv()

# -------------------------
# LangGraph State Definition
# -------------------------
class InputState(TypedDict):
    query: str

class OutputState(TypedDict):
    generated_sql: str
    result: str

class AgentState(InputState, OutputState):
    messages: Annotated[List[BaseMessage], add]

# -------------------------
# MCP Config
# -------------------------
MCP_QUERY_URL = "http://127.0.0.1:8000/query"
MCP_SCHEMA_URL = "http://127.0.0.1:8000/schema"

# -------------------------
# LangGraph Nodes
# -------------------------
llm = ChatOpenAI(model="gpt-4o-mini")

def call_introspect_schema(state: AgentState) -> AgentState:
    response = requests.get(MCP_SCHEMA_URL)
    schema = response.json()["schema"]

    system_prompt = f"""
You are a strict SQL assistant for a SQLite database.

ONLY use the following schema to answer the user's question.
Do NOT invent columns. Do NOT rename anything. If the info is missing, say it can't be answered.

--- DATABASE SCHEMA ---
{schema}
------------------------

Return a single valid SQL query using only this schema.
No explanations. No markdown.
""".strip()

    state["messages"] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["query"])
    ]
    return state

def call_llm_generate_sql(state: AgentState) -> AgentState:
    response = llm.invoke(state["messages"])
    sql = response.content.strip().strip("```sql").strip("```")
    state["generated_sql"] = sql
    state["messages"].append(response)
    return state

def call_query_sql(state: AgentState) -> AgentState:
    response = requests.post(MCP_QUERY_URL, json={"sql": state["generated_sql"]})
    state["result"] = response.json()["result"]
    return state

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("introspect_schema", call_introspect_schema)
    graph.add_node("llm_generate_sql", call_llm_generate_sql)
    graph.add_node("query_sql", call_query_sql)

    graph.set_entry_point("introspect_schema")
    graph.add_edge("introspect_schema", "llm_generate_sql")
    graph.add_edge("llm_generate_sql", "query_sql")
    graph.add_edge("query_sql", END)

    return graph.compile()

# -------------------------
# FastAPI Wrapper
# -------------------------
app = FastAPI(title="MCP SQL LangGraph API")
agent = build_graph()

class AskSQLRequest(BaseModel):
    query: str

@app.post("/ask_sql")
def ask_sql(req: AskSQLRequest):
    state = {"query": req.query, "messages": []}
    result = agent.invoke(state)
    return {
        "query": req.query,
        "generated_sql": result["generated_sql"],
        "result": result["result"]
    }

@app.get("/")
def root():
    return {"message": "POST /ask_sql with a query like: 'Show employees in HR'"}
