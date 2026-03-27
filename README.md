# Universal Data Connector

A FastAPI server that gives an LLM unified, voice-optimized access to multiple data sources through function calling. Built for a SaaS company where customers query their CRM, support tickets, and analytics data via an AI voice assistant.

---

## Table of Contents

1. [What This Is](#what-this-is)
2. [Architecture](#architecture)
3. [How It Works](#how-it-works)
4. [Setup](#setup)
5. [Running the Server](#running-the-server)
6. [API Reference](#api-reference)
7. [LLM Function Calling](#llm-function-calling)
8. [Running the LLM Demo](#running-the-llm-demo)
9. [Docker](#docker)
10. [Design Decisions & Tradeoffs](#design-decisions--tradeoffs)
11. [Challenges & Solutions](#challenges--solutions)
12. [Assumptions](#assumptions)
13. [What I Learned](#what-i-learned)

---

## What This Is

A voice assistant backend. The LLM never queries data directly — it describes what it wants using a structured tool schema, this server fetches and filters the data, and the LLM turns the result into a spoken answer.

**Data sources covered:**
- CRM — customer records with status and signup date
- Support — tickets with priority, status, and customer linkage
- Analytics — time-series metrics (daily active users, revenue)

**What the server adds on top of raw data:**
- Filtering by any combination of parameters
- Business rules: sort by relevance (priority-first for tickets, recency-first for others)
- Pagination: default cap of 10 results, configurable up to 50
- Metadata: total vs returned count, data freshness timestamp, plain-English context summary
- Error handling: 503 with a clear message if a data file is missing

---

## Architecture

```
universal-data-connector/
├── app/
│   ├── main.py                    # FastAPI app — wires routers together
│   ├── config.py                  # Reads .env via pydantic-settings
│   ├── connectors/
│   │   ├── base.py                # Abstract BaseConnector — enforces .fetch() interface
│   │   ├── crm_connector.py       # Loads + filters customers.json
│   │   ├── support_connector.py   # Loads + filters support_tickets.json
│   │   └── analytics_connector.py # Loads + filters analytics.json, handles date clamping
│   ├── models/
│   │   ├── common.py              # DataResponse + Metadata — shared response envelope
│   │   ├── crm.py                 # Customer Pydantic model
│   │   ├── support.py             # Ticket Pydantic model
│   │   └── analytics.py           # Metric Pydantic model
│   ├── routers/
│   │   ├── health.py              # GET /health
│   │   └── data.py                # GET /api/customers, /api/support/tickets, /api/analytics/metrics
│   ├── services/
│   │   ├── business_rules.py      # Sorts + caps results by data type
│   │   ├── voice_optimizer.py     # Builds metadata.context string (plain-English summary)
│   │   └── data_identifier.py     # Detects data shape (tabular, time-series, etc.)
│   └── utils/
│       └── logging.py             # Structured logging setup
├── client/
│   ├── llm_demo.py                # End-to-end LLM function calling demo
│   └── tool_definitions.py        # OpenAI-format tool schemas sent to the LLM
├── data/
│   ├── customers.json             # 50 sample CRM records
│   ├── support_tickets.json       # 60 sample tickets
│   └── analytics.json             # 90 days of DAU + revenue metrics
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
└── WRITEUP.md                     # Extended written summary
```

---

## How It Works

### Request lifecycle

```
User question
     │
     ▼
LLM Step 1 — decides which tool to call, extracts params from the question
     │
     ▼
_call_api() — HTTP GET to FastAPI with query params
     │
     ▼
Router — validates params, calls connector.fetch()
     │
     ▼
Connector — loads JSON, applies filters, returns List[Dict]
     │
     ▼
business_rules() — sorts by relevance, caps to limit
     │
     ▼
voice_optimizer() — builds plain-English metadata.context
     │
     ▼
DataResponse — {"data": [...], "metadata": {...}} returned to LLM
     │
     ▼
LLM Step 2 — reads data + metadata, writes spoken-English answer
     │
     ▼
Printed / spoken answer
```

### Connector abstraction

Every data source implements `BaseConnector`:

```python
class BaseConnector(ABC):
    @abstractmethod
    def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        pass
```

The router calls `.fetch()` without knowing or caring what is underneath. Swapping from JSON files to a Postgres database or a REST API only requires changing the connector — the router, business rules, and LLM layer are completely untouched.

### Response envelope

Every endpoint returns the same shape:

```json
{
  "data": [ ...records... ],
  "metadata": {
    "total_results": 25,
    "returned_results": 10,
    "data_freshness": "Data as of 3 hours ago",
    "context": "Showing 10 of 25 tickets. 4 high-priority. 18 open"
  }
}
```

`total_results` vs `returned_results` tells the LLM that more records exist than it received. Without this, the model would count 10 returned records and confidently say "there are 10 tickets total." The `context` string is pre-computed so the LLM can quote it directly without counting records itself — reducing hallucination risk on aggregation questions.

### Business rules engine

`apply_business_rules()` sorts records by relevance before slicing to the limit:

| Data type | Sort order |
|---|---|
| `tabular_support` | Priority first (high → medium → low), then newest within each priority |
| `tabular_crm` | Newest customers first |
| `time_series` | Most recent dates first |

This ensures the limit always cuts the *least relevant* records, not random ones.

### Data freshness

Each JSON file is wrapped in:
```json
{"last_updated": "2026-02-20T00:00:00Z", "records": [...]}
```

`_freshness()` reads this field directly rather than checking the file's OS modification time. This makes the timestamp immune to deploy or copy operations that touch the file without changing its data — the timestamp only moves when someone intentionally updates it.

---

## Setup

### Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com) — free account, globally available

### Install

```bash
git clone https://github.com/sh-yamm/universal-data-connector
cd universal-data-connector

python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
APP_NAME=Universal Data Connector
MAX_RESULTS=10
GROQ_API_KEY=your_groq_api_key_here
```

`MAX_RESULTS` is the default page size returned by all endpoints. It can be overridden per request with the `limit` query parameter (valid range: 1–50).

---

## Running the Server

```bash
uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`.

| URL | What it is |
|---|---|
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/docs` | Swagger UI — interactive, try-it-in-browser API explorer |
| `http://localhost:8000/redoc` | ReDoc — clean readable API reference |
| `http://localhost:8000/openapi.json` | Raw OpenAPI schema (used by LLM function calling tools) |

---

## API Reference

### `GET /health`

```json
{"status": "ok"}
```

---

### `GET /api/customers`

Returns CRM customer records.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | — | `active` \| `inactive` \| `all` |
| `created_after` | string (ISO date) | — | Return customers created on or after this date, e.g. `2026-01-01` |
| `limit` | integer (1–50) | 10 | Max records to return |

Results are sorted newest-first before the limit is applied.

**Example request:**
```
GET /api/customers?status=active&created_after=2026-01-01
```

**Example response:**
```json
{
  "data": [
    {
      "id": 39,
      "name": "User 39",
      "email": "user39@example.com",
      "status": "active",
      "created_at": "2026-01-19"
    }
  ],
  "metadata": {
    "total_results": 4,
    "returned_results": 4,
    "data_freshness": "Data as of 2 days ago",
    "context": "Showing 4 of 4 customers. 3 active"
  }
}
```

---

### `GET /api/support/tickets`

Returns support tickets. Results are sorted high-priority first, then newest within each priority level.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | — | `open` \| `closed` \| `all` |
| `priority` | string | — | `high` \| `medium` \| `low` \| `all` |
| `customer_ids` | integer (repeatable) | — | Filter by one or more customer IDs. Repeat the param: `?customer_ids=5&customer_ids=39` |
| `limit` | integer (1–50) | 10 | Max records to return |

**Example request:**
```
GET /api/support/tickets?priority=high&status=open&customer_ids=5&customer_ids=39
```

---

### `GET /api/analytics/metrics`

Returns time-series analytics data.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metric` | string | — | `daily_active_users` \| `revenue` |
| `date_from` | string (YYYY-MM-DD) | — | Start date, inclusive |
| `date_to` | string (YYYY-MM-DD) | — | End date, inclusive |
| `aggregation` | string | — | `sum` \| `avg` \| `max` \| `min` — collapses all matching records into one number. When set, `limit` is ignored. |
| `limit` | integer (1–50) | 10 | Max raw records (ignored when `aggregation` is set) |

**Example — total revenue for last 7 days:**
```
GET /api/analytics/metrics?metric=revenue&date_from=2026-02-13&date_to=2026-02-20&aggregation=sum
```

**Example response:**
```json
{
  "data": [
    {"metric": "revenue", "aggregation": "sum", "value": 84523.0, "records_used": 7}
  ],
  "metadata": {
    "total_results": 7,
    "returned_results": 7,
    "data_freshness": "Data as of 1 day ago",
    "context": "SUM across 7 daily records = 84523.0"
  }
}
```

---

## LLM Function Calling

### The two-step contract

The LLM never accesses data directly. The process is:

**Step 1** — The user's question and the tool schemas are sent to the LLM with `tool_choice="auto"`. The model responds with a structured JSON object describing *which tool to call* and *what parameters to use*. It has not seen any data yet.

**Step 2** — Client code executes the tool call (HTTP GET to FastAPI), feeds the result back into the conversation, and calls the LLM again with `tool_choice="none"`. The model reads the data and writes a natural-language answer.

This separation is fundamental: the LLM is the router and interpreter, not the data fetcher.

### Tool schemas (`client/tool_definitions.py`)

The `TOOLS` list is sent to the LLM with every request. These schemas mirror the FastAPI query parameters exactly — the LLM fills in values that map directly to valid HTTP requests:

```python
{
    "type": "function",
    "function": {
        "name": "get_support_tickets",
        "description": (
            "Retrieve support tickets. Use this for questions about open or "
            "closed tickets, ticket priorities, or tickets belonging to a "
            "specific customer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status":   {"type": "string", "enum": ["open", "closed", "all"]},
                "priority": {"type": "string", "enum": ["high", "medium", "low", "all"]},
                "customer_ids": {
                    "type": "string",
                    "description": "JSON array of customer IDs, e.g. '[5, 39, 50]'"
                },
                "limit": {"type": "integer", "default": 10}
            }
        }
    }
}
```

The `description` field is prompt engineering. Vague descriptions cause wrong tool selection. The descriptions here explicitly name the use cases ("tickets belonging to a specific customer") so the LLM routes correctly even on ambiguous questions.

### System prompt

`_system_prompt()` in `llm_demo.py` does three things:
1. Injects today's date so the LLM converts "last 7 days" into actual ISO dates
2. Instructs the LLM to answer in natural spoken English — no markdown, no bullet points
3. Scopes the LLM to only use the three provided tools

### Session memory

The `messages` list is initialized once with the system prompt and passed into every `ask()` call. Each turn appends the user question and assistant answer, enabling follow-up questions like "who are they?" or "show me their tickets" to resolve correctly using prior context. The list is discarded on exit — matching the stateless-per-call model of a real IVR system.

---

## Running the LLM Demo

Make sure the FastAPI server is running in a separate terminal first, then:

```bash
python "client/llm_demo.py"
```

**Example session:**

```
============================================================
  Universal Data Connector - LLM Demo
============================================================

> how many customers signed up this year

------------------------------------------------------------
  Q: how many customers signed up this year
------------------------------------------------------------
  Tool called : get_customers
  Arguments   : {"created_after": "2026-01-01"}
  API context : Showing 4 of 4 customers. 3 active
  Returned    : 4 / 4 records

  A: Four customers signed up this year, all joining in January 2026.

> who are they

  A: The four customers are Customer 39, Customer 5, Customer 50, and Customer 40.

> how many of them have high priority tickets

  Tool called : get_support_tickets
  Arguments   : {"customer_ids": "[39, 5, 50, 40]", "priority": "high"}
  API context : Showing 2 of 2 tickets. 2 high-priority
  Returned    : 2 / 2 records

  A: Two of those customers have high priority tickets.

> quit
Bye!
```

Type a number (1–7) to run a preset question, press Enter to run all presets, or type any question directly. Type `quit` to exit.

---

## Docker

The Docker setup runs the server on any machine without installing Python.

**Build and start:**
```bash
docker compose up --build
```

**Stop:**
```bash
docker compose down
```

The `.env` file is injected at runtime via `env_file` in `docker-compose.yml` — it is never baked into the image. `.dockerignore` excludes `.env`, `venv/`, `__pycache__/`, and `.git/` from the build context to keep the image small.

`restart: unless-stopped` in `docker-compose.yml` means the container automatically restarts after a crash, and only stops on an explicit `docker compose down`.

**Note on remote machines:** When Docker runs on Machine B, `localhost:8000` refers to Machine B's localhost. To access the API from another machine on the same network, use Machine B's IP: `http://192.168.x.x:8000`. The `llm_demo.py` client must run on the same machine as the container, or `API_BASE` must be updated.

---

## Design Decisions & Tradeoffs

> Full rationale, tradeoffs, and production comparisons for each decision are in [WRITEUP.md](WRITEUP.md).

| Decision | Why |
|---|---|
| `BaseConnector.fetch()` abstraction | Swap data source (JSON → Postgres, REST API) by changing only the connector — router and LLM layer untouched |
| Filtering in Python, not at the source | Correct for small static files; a real DB would push filters into the SQL query instead |
| Two LLM calls per question | Required — `tool_choice="none"` on Call 2 forces a text answer; without it the model loops into another tool call |
| Pre-computed `metadata.context` | LLM quotes the plain-English summary directly, avoiding hallucinations on count/aggregate questions |
| `total_results` vs `returned_results` | Prevents the LLM from treating a 10-record page as the full dataset |
| Session memory in a Python list, no persistence | Matches real IVR model: context within a call, discarded on exit — no Redis or LangGraph needed |
| `customer_ids` as a set before filtering | O(1) per-record lookup vs O(n×m) list scan — constant cost regardless of how many IDs are passed |
| Voice format enforced via system prompt | More reliable than post-processing markdown; the prompt controls output format at the source |
| Pydantic only at the response boundary | Static trusted JSON doesn't justify per-record CPU overhead; only needed for sensitive/untrusted sources |

---

## Challenges & Solutions

| Challenge | Fix |
|---|---|
| OpenAI free tier gave no credits; Gemini had India regional restrictions | Switched to Groq — free, global, OpenAI-SDK-compatible via `base_url` swap |
| `llama3-groq-70b` and `mixtral-8x7b` decommissioned mid-project | Switched to `llama-4-scout-17b-16e-instruct`; added one-retry loop for transient `tool_use_failed` errors |
| LLM sent `"last 7 days"` as a literal date param | Injected today's date into system prompt; instructed model to convert relative dates to ISO format |
| LLM hallucinated `2026-02-29` (invalid date) | Added `_clamp_date()` in analytics connector to clamp to real month-end |
| After tool result, model called another tool instead of answering | Added `tool_choice="none"` on the second LLM call |
| Llama stringified `customer_ids` array as `"[39, 5]"` — Groq rejected it | Changed schema type to `"string"`; parsed back to `List[int]` with `json.loads()` in `_call_api()` before sending to FastAPI |
| `.env` with API key committed before `.gitignore` was created | Wiped git history (`rm -rf .git`), reinit, clean commit with `.env` already ignored |

---

## Assumptions

1. **Single tool call per question.** The loop handles one tool call per question. A question like "which active customers have open high-priority tickets?" would require joining CRM and support results — this needs a multi-tool agent loop and is out of scope.

2. **Data files are present at runtime.** If a data file is missing, the endpoint returns HTTP 503 with a descriptive message. The server does not pre-validate file presence on startup.

3. **JSON data is trusted.** Records are not validated against Pydantic models at the connector level. This is intentional for static, read-only analytics data — connector-level `model_validate()` adds per-record CPU overhead that only makes sense for sensitive or untrusted sources (financial data, external APIs). The full reasoning — when to hard-fail vs skip-and-log, and when Pydantic validation is actually worth the cost — is covered in detail in [WRITEUP.md](WRITEUP.md).

4. **Customer ID values are integers in the JSON.** The support connector filters using `t["customer_id"] in id_set` where `id_set` contains Python `int` values. If the JSON stored IDs as strings, the filter would silently return zero results.

5. **Groq free tier is sufficient for the demo.** No rate-limit retry-with-backoff is implemented. A production deployment would need exponential backoff and a fallback model.

6. **One active session at a time.** `llm_demo.py` manages a single `messages` list. Multiple simultaneous sessions would require per-session storage keyed by session ID.

---

## What I Learned

- **Function calling is a two-step contract.** The LLM outputs a JSON description of what it wants to call; your code executes it; the LLM reads the result and writes an answer. It never touches the data directly.
- **Tool descriptions are prompt engineering.** Vague descriptions cause wrong tool selection. Specific descriptions with enum constraints and use-case examples work reliably.
- **Date handling is deceptively hard.** Without an injected current date in the system prompt, relative queries produce wrong parameters. Even with a date, models occasionally hallucinate invalid calendar dates — requiring clamping logic in the connector.
- **Schema types must match model behavior, not the ideal spec.** Llama stringifies arrays regardless of the schema. The practical fix is to accept the model's output format and normalize it at the client boundary.
- **Metadata matters as much as data.** `total_results` vs `returned_results` and the pre-computed `context` string are what prevent the LLM from misreporting totals.
- **Free-tier LLM APIs carry real operational risk.** Two models were decommissioned mid-project. Production systems need pinned model versions and fallback strategies.
- **Connector abstraction pays off on the first change.** Adding `customer_ids`, handling 503s, and date-clamping all happened inside the connector without touching the router or LLM layer.
