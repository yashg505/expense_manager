import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import psycopg
import sqlparse
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NEON_CONN_STR = os.environ["NEON_CONN_STR"]

client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="Expense DB Chatbot (3-stage LLM pipeline)")

# ----------------------------
# DB helpers
# ----------------------------

def is_read_only_sql(sql: str) -> bool:
    s = sql.strip().rstrip(";").lower()
    if not (s.startswith("select") or s.startswith("with")):
        return False
    banned = ["insert", "update", "delete", "drop", "alter", "truncate", "create", "grant", "revoke"]
    for w in banned:
        if re.search(rf"\b{w}\b", s):
            return False
    # disallow multiple statements
    return len(sqlparse.parse(s)) == 1

def run_query(sql: str, params: Optional[Tuple[Any, ...]] = None, limit: int = 500) -> List[Dict[str, Any]]:
    sql = sql.strip().rstrip(";")

    if not is_read_only_sql(sql):
        raise ValueError("Only single-statement read-only SELECT/WITH queries are allowed.")

    sql_lower = sql.lower()
    is_metadata_query = "information_schema" in sql_lower

    if (not is_metadata_query) and (" limit " not in sql_lower):
        sql = f"SELECT * FROM ({sql}) AS subq LIMIT {limit}"

    # Print every executed SQL for debugging
    print("\n========== SQL EXECUTE ==========")
    print(sql)
    print("PARAMS:", params)
    print("================================\n")

    with psycopg.connect(NEON_CONN_STR) as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 8000")  # 8s
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]

# ----------------------------
# Fixed schema context (deterministic grounding)
# ----------------------------

SCHEMA_CONTEXT = """
atabase schema (authoritative):

public.processed_items(
  id serial primary key,
  file_id text not null,
  shop_name text,
  receipt_date date,
  receipt_time time,
  item_text text not null,          -- raw product name from receipt
  taxonomy_id text not null,        -- category id, join to taxonomy.id
  item_type text,                   -- short normalized type (e.g., 'Tomato', 'Milk')
  quantity integer,
  price real,
  total real,
  discount real,
  created_at timestamp default current_timestamp
)

public.taxonomy(
  id text primary key,              -- join key: processed_items.taxonomy_id
  category text,
  sub_category_i text,
  sub_category_ii text,
  full_path text,                   -- e.g. "Food Items > Fruits and Vegetables > Vegetables"
  description text
)

public.corrections(
  shop_name text,
  item_text text,
  corrected_taxonomy_id text not null,
  user_id text default 'system',
  updated_at timestamp default current_timestamp,
  corrected_item_type text,
  primary key (shop_name, item_text)
)

public.image_metadata(
  file_id text primary key,
  file_name text,
  fingerprint text unique,
  image_path text,
  json_state text,
  status text default 'pending',
  updated_at timestamp default current_timestamp
)                                                -- not used for spend analytics
DATA DICTIONARY (critical meaning):
- "item" / "product" means: processed_items.item_text
- "item type" means: processed_items.item_type (NOT item_text)
- "store" / "shop" means: processed_items.shop_name
- "category" means: taxonomy.category OR taxonomy.full_path (via join)
- "sub-category I" means: taxonomy.sub_category_i (via join)
- "sub-category II" means: taxonomy.sub_category_ii (via join)
- "taxonomy id" means: processed_items.taxonomy_id
- "food vs non-food": use processed_items.taxonomy_id LIKE 'food_items%' for food

SPEND FORMULA (must use everywhere):
line_spend = COALESCE(total, price * COALESCE(quantity,1), 0)

DATE RULE:
month = date_trunc('month', COALESCE(receipt_date::timestamp, created_at))::date


Domain rules (use these for SQL):
- Spending per line = COALESCE(total, price * COALESCE(quantity,1), 0)
- Use processed_items for ANY spend/quantity/item/shop questions.
- For month grouping use: date_trunc('month', COALESCE(receipt_date::timestamp, created_at))::date
- Food items: taxonomy_id LIKE 'food_items%'. Non-food: taxonomy_id NOT LIKE 'food_items%' OR taxonomy_id IS NULL.
- If user asks "January" without a year: ask a clarification OR default to latest year in data (prefer asking).
"""

# ----------------------------
# LLM #1: Interpret user query -> intent JSON
# ----------------------------

INTENT_PROMPT = f"""
You are an intent parser for a receipts/expenses assistant.

Return ONLY valid JSON (no markdown, no commentary).
JSON schema:
{{
  "intent": one of [
    "total_spend_by_item_monthly",
    "total_spend_by_item_overall",
    "total_spend_monthly",
    "spend_by_item_for_month",
    "most_spent_item",
    "cutdown_suggestions",
    "compare_shops_most_spent",
    "unique_items_by_month",
    "non_food_spend_monthly",
    "schema_question",
    "other"
  ],
  "entities": {{
    "item_query": string|null,
    "shop_a": string|null,
    "shop_b": string|null,
    "shop_name": string|null,
    "month": "YYYY-MM"|null,
    "year": int|null,
    "is_food": true|false|null
    "group_by": one of ["category","sub_category_i","sub_category_ii","full_path","shop_name","item_text","item_type"] or null
    "metric": one of ["spend","count","quantity"] or null
  }},
  "needs_clarification": true|false,
  "clarification_question": string|null
}}

Rules:
- If user asks for a month name (e.g. January) without year, set needs_clarification=true and ask for year.
- If user asks "compare Lidl vs Umami" interpret as shop comparison (shops, not items).
- If user asks "cut down on" interpret as cutdown_suggestions.
- If user asks "unique items per month" interpret as unique_items_by_month.
- If user asks about "non food" interpret as non_food_spend_monthly.
- If you cannot map it, use intent="other".
- If the user asks "what categories do I have" / "what categories are in my data" / "my categories":
  intent="list_categories_in_data" (NOT schema_question)
- If the user asks for "categories in items" / "categories in my items" / "what categories do I have":
    - This is a DATA question, not schema.
    - Set intent = "category_list_or_spend"
    - Set entities.group_by = "category"
    - Set entities.metric = "list_distinct" unless they say "expenses/spend/total", then metric="spend".

"""

def llm_parse_intent(user_text: str) -> Dict[str, Any]:
    r = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    content = (r.choices[0].message.content or "").strip()
    return json.loads(content)

# ----------------------------
# LLM #2: Intent JSON -> SQL (SQL ONLY)
# ----------------------------

SQL_PROMPT = f"""
You are a Postgres SQL generator for this database.

{SCHEMA_CONTEXT}

Return ONLY SQL (no markdown, no backticks, no explanation).
Hard rules:
- Only SELECT/WITH. No semicolons.
- Only use columns that exist in the schema above.
- Never use strftime or '%m' patterns.
- Use ILIKE for item text search.
- Use processed_items for spend queries.
- If intent requires a specific month and it is missing, output SQL that returns a single row asking for clarification is NOT allowed.
  Instead, the caller will ask clarification; you should still generate SQL for what you can only when parameters are complete.
- If the user asks for multiple attributes (e.g. item AND shop), you MUST include all those attributes in SELECT and GROUP BY.
- If the user says "item type", use processed_items.item_type.
- If the user says "item", use processed_items.item_text.

  
SQL patterns:
- total_spend_by_item_monthly(item_query):
  group by month and sum(line spend) where item_text ILIKE %item_query%

- unique_items_by_month:
  group by month + item_text; return month, item_text, total_quantity (sum quantity default 1)

- non_food_spend_monthly:
  group by month; filter taxonomy_id NOT LIKE 'food_items%'

- spend_by_item_for_month(month YYYY-MM):
  filter receipt_date between month start/end; group by item_text

- compare_shops_most_spent(shop_a, shop_b):
  for each shop, find item_text with max total_spend.

- cutdown_suggestions:
  show top items by spend in last 60 days.

Always compute spend as:
SUM(CASE WHEN total IS NOT NULL THEN total WHEN price IS NOT NULL THEN price * COALESCE(quantity,1) ELSE 0 END)

Special rule:
- For intent "most_spent_item":
  You MUST group by BOTH item_text and shop_name.
  Return columns: item_text, shop_name, total_spend.

JOIN RULES:
- If group_by is category/sub_category_i/sub_category_ii/full_path:
  you MUST join taxonomy tx ON tx.id = processed_items.taxonomy_id
  and group by the requested tx column.

METRIC RULES:
- If metric is spend: use SUM(line_spend)
- If metric is count: use COUNT(*) or COUNT(DISTINCT ...) depending on intent
- If metric is quantity: SUM(COALESCE(quantity,1))

TIME GROUPING RULE (very important):
- Do NOT group by month/date unless the user explicitly asks for monthly/by month/each month.
- Default is all-time totals.

VALIDATION RULES (self-check before returning SQL):
- Do a final pass and verify the SQL matches the user's intent JSON and question.
- Confirm the SELECT returns exactly the fields needed to answer the question (no missing asked-for fields).
- Confirm filters/grouping match the intent (e.g., do not add monthly grouping unless explicitly requested; do not omit it if requested).
- Confirm any requested breakdown dimension (shop/category/sub-category/item_type/item_text) is present in SELECT and GROUP BY when aggregating.
- Confirm category/sub-category questions use taxonomy join (tx.id = processed_items.taxonomy_id) and select the correct tx column.
- If any check fails, revise the SQL and re-check. Return only the final corrected SQL.

"""

def llm_intent_to_sql(intent_obj: Dict[str, Any]) -> str:
    r = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SQL_PROMPT},
            {"role": "user", "content": json.dumps(intent_obj)},
        ],
    )
    sql = (r.choices[0].message.content or "").strip()
    return sql.rstrip(";").strip()

# ----------------------------
# LLM #3: Validate/repair SQL with feedback loop
# ----------------------------

SQL_REPAIR_PROMPT = f"""
You are a Postgres SQL repair assistant.

{SCHEMA_CONTEXT}

You will receive:
- the user's question
- the intent JSON
- the SQL that failed
- the exact Postgres/psycopg error

Return ONLY corrected SQL (no markdown, no explanation).
Rules:
- Only SELECT/WITH, no semicolons.
- Must use existing columns only.
- Avoid placeholders with percent patterns like '%m'. Use date_trunc/to_char properly.
- Prefer receipt_date (fallback created_at).
- If the user's question is about categories in their data, the SQL must query processed_items and join taxonomy.
It must NOT query information_schema.
- If user did NOT ask for monthly breakdown and SQL groups by month/date_trunc, remove the month grouping.
- If the error indicates a missing table/column, fix it accordingly.
"""

def llm_repair_sql(user_text: str, intent_obj: Dict[str, Any], bad_sql: str, error_text: str) -> str:
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SQL_REPAIR_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "user_question": user_text,
                    "intent": intent_obj,
                    "failed_sql": bad_sql,
                    "error": error_text
                }),
            },
        ],
    )
    sql = (r.choices[0].message.content or "").strip()
    return sql.rstrip(";").strip()

def execute_with_repair_loop(user_text: str, intent_obj: Dict[str, Any], sql: str, max_repairs: int = 1):
    last_err = None
    for attempt in range(max_repairs + 1):
        try:
            rows = run_query(sql)
            return {"ok": True, "sql": sql, "rows": rows}
        except Exception as e:
            last_err = str(e)
            print("\n!!!!! SQL FAILED !!!!!")
            print("ERROR:", last_err)
            print("SQL:\n", sql)
            print("!!!!!!!!!!!!!!!!!!!!!!\n")

            if attempt >= max_repairs:
                break

            sql = llm_repair_sql(user_text, intent_obj, sql, last_err)

    return {"ok": False, "error": last_err, "sql": sql}

# ----------------------------
# Final answer synthesis (grounded in rows)
# ----------------------------

ANSWER_PROMPT = """
You are a concise assistant. Use ONLY the provided rows to answer.
If rows are empty, say you found no matching records.
Do not mention SQL unless asked.
Prefer bullets or a compact table-style text.
"""

def llm_summarize(user_text: str, intent_obj: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    r = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": ANSWER_PROMPT},
            {"role": "user", "content": json.dumps({
                "question": user_text,
                "intent": intent_obj,
                "rows": rows
            }, default=str)},
        ],
    )
    return (r.choices[0].message.content or "").strip()

# ----------------------------
# API
# ----------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

@app.post("/chat")
def chat(req: ChatRequest):
    user_text = req.message.strip()

    # 1) Interpret
    intent_obj = llm_parse_intent(user_text)

    if intent_obj.get("needs_clarification"):
        return {"answer": intent_obj.get("clarification_question") or "I need more details to answer."}

    # 2) Generate SQL
    sql = llm_intent_to_sql(intent_obj)

    # 3) Validate & repair loop (exec + retry)
    exec_result = execute_with_repair_loop(user_text, intent_obj, sql, max_repairs=1)
    if not exec_result["ok"]:
        # Return error (and include SQL for debugging if you want)
        return {"answer": f"Database query failed: {exec_result['error']}"}

    rows = exec_result["rows"]

    # 4) Summarize grounded answer
    answer = llm_summarize(user_text, intent_obj, rows)
    return {"answer": answer}
