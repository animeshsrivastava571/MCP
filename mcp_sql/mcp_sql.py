from fastapi import FastAPI
from pydantic import BaseModel
from fastmcp import FastMCP, Client
import sqlite3
from typing import List, Dict

# --- Setup SQLite (in-memory) ---
conn = sqlite3.connect(":memory:", check_same_thread=False)
cursor = conn.cursor()

# Create departments table
cursor.execute("""
CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);
""")

# Create employees table with FK to departments
cursor.execute("""
CREATE TABLE employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department_id INTEGER,
    FOREIGN KEY(department_id) REFERENCES departments(id)
);
""")

# Insert sample data
cursor.executemany("INSERT INTO departments (name) VALUES (?)", [
    ("Engineering",),
    ("HR",),
    ("Finance",)
])
cursor.executemany("INSERT INTO employees (name, department_id) VALUES (?, ?)", [
    ("Alice", 1),
    ("Bob", 2),
    ("Charlie", 1),
    ("David", 3),
    ("Eve", 1),
    ("Frank", 2),
    ("Grace", 3),
    ("Heidi", 1),
    ("Ivan", 2),
    ("Judy", 3)
])
conn.commit()

# --- MCP Server Setup ---
mcp = FastMCP("SQLAssistant")


@mcp.tool()
def introspect_schema(dummy: str = "") -> str:
    """
    Returns a full summary of tables, columns, types, and constraints for the in-memory SQLite DB.
    This is intended to help LLMs generate accurate SQL queries.
    """
    try:
        tables = cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%';
        """).fetchall()

        if not tables:
            return "No user-defined tables found in the database."

        full_schema = []
        for table_row in tables:
            table_name = table_row[0]
            columns = cursor.execute(f"PRAGMA table_info({table_name});").fetchall()

            col_lines = []
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                is_pk = "PRIMARY KEY" if col[5] else ""
                is_not_null = "NOT NULL" if col[3] else ""
                constraints = " ".join(filter(None, [is_pk, is_not_null]))
                col_lines.append(f"- {col_name} ({col_type}) {constraints}".strip())

            # Foreign keys
            fks = cursor.execute(f"PRAGMA foreign_key_list({table_name});").fetchall()
            fk_lines = []
            for fk in fks:
                fk_lines.append(f"- FOREIGN KEY: `{fk[3]}` → `{fk[2]}.{fk[4]}`")

            schema_section = f"Table `{table_name}`:\n" + "\n".join(col_lines + fk_lines)
            full_schema.append(schema_section)

        return "\n\n".join(full_schema)

    except Exception as e:
        return f"Schema introspection failed: {e}"



@mcp.tool()
def query_sql(sql: str) -> List[Dict]:
    """Execute a SQL query and return results as a list of dictionaries."""
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return [{"error": str(e)}]

# --- FastAPI + MCP Bridge ---
app = FastAPI(title="MCP SQL Agent")

class SQLRequest(BaseModel):
    sql: str

@app.post("/query")
async def run_sql(payload: SQLRequest):
    async with Client(mcp) as client:
        result = await client.call_tool("query_sql", {"sql": payload.sql})
        return {"result": result[0].text}

@app.get("/schema")
async def get_schema():
    async with Client(mcp) as client:
        result = await client.call_tool("introspect_schema", {"dummy": ""})
        return {"schema": result[0].text}
