from langgraph.graph import StateGraph, END, START
from typing import TypedDict, List, Literal, Annotated
from operator import add
import requests
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_openai import ChatOpenAI

# This is the master MCP CLient

# --- State definition
class InputState(TypedDict):
    query: str

class OutputState(TypedDict):
    generated_sql: str
    result: str

class AgentState(InputState, OutputState):
    messages: Annotated[List[BaseMessage], add]

# --- LLM
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini")

# --- MCP Config
MCP_QUERY_URL = "http://127.0.0.1:8000/query"
MCP_INTROSPECT_TOOL = "introspect_schema"
MCP_TOOL_CALL_URL = "http://127.0.0.1:8000/query"

def call_introspect_schema(state: AgentState) -> AgentState:
    print("🔍 Calling MCP introspect_schema via /schema...")
    
    try:
        response = requests.get("http://127.0.0.1:8000/schema")  # ✅ Use FastAPI schema endpoint
        response.raise_for_status()
        schema = response.json()["schema"]
    except Exception as e:
        schema = f"Schema fetch failed: {str(e)}"
    
    print(f"Schema is:\n{schema}")

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


# --- Tool 2: Generate SQL from LLM
def call_llm_generate_sql(state: AgentState) -> AgentState:
    messages = state["messages"]
    response = llm.invoke(messages)
    sql = response.content.strip().strip("```sql").strip("```")
    state["messages"].append(response)
    state["generated_sql"] = sql
    print("🧠 LLM Generated SQL:\n", sql)
    return state

# --- Tool 3: Run SQL on MCP Server
def call_query_sql(state: AgentState) -> AgentState:
    sql = state["generated_sql"]
    print("📤 Sending SQL to MCP:", sql)
    response = requests.post(MCP_QUERY_URL, json={"sql": sql})
    result = response.json()["result"]
    state["result"] = result
    return state

# --- Build the graph
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

# --- Run the agent with a query
if __name__ == "__main__":
    agent = build_graph()
    query = "List the names of employees in the Engineering department"
    state = {"query": query, "messages": []}
    result = agent.invoke(state)

    print("\n✅ Final SQL:", result["generated_sql"])
    print("\n📊 Result:", result["result"])
