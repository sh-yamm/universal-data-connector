# Universal Data Connector — Written Summary

## Challenges Faced & Solutions

**LLM provider failures**
OpenAI's free tier no longer gives credits to new accounts — both original and new keys failed immediately. Switched to Gemini, which hit regional restrictions (India's free tier returns `limit: 0`). Finally settled on Groq, which is free and globally available, using the OpenAI-compatible SDK with just a `base_url` swap.

**Model tool-use reliability**
`llama-3.3-70b-versatile` intermittently returned `tool_use_failed` errors with malformed JSON in tool calls. `llama3-groq-70b` and `mixtral-8x7b` were both decommissioned mid-project. Resolved by switching to `meta-llama/llama-4-scout-17b-16e-instruct` (Llama 4 Scout) and adding a one-retry loop for transient failures.

**LLM sending relative dates**
When asked "last 7 days", the model sent the literal string as a date param instead of converting it. Fixed by injecting today's date into the system prompt and explicitly instructing the model to convert relative dates to ISO format before calling tools.

**Hallucinated invalid dates**
The LLM occasionally generated dates like `2026-02-29` (Feb has no 29th in 2026). Added `_clamp_date()` in the analytics connector to salvage the year-month and clamp to the real last day of the month.

**Second LLM call looping**
After receiving the tool result, the model kept trying to call another tool instead of answering in plain text. Fixed with `tool_choice="none"` on the second API call, forcing a text response.

**Windows encoding errors**
The terminal couldn't render Unicode box-drawing characters (`─`, `═`). Replaced all with ASCII equivalents (`-`, `=`).

---

## Design Decisions & Tradeoffs

**LLM-based tool routing vs rule-based routing**
Letting the LLM pick the tool costs extra tokens per request and is sensitive to model changes. But it handles ambiguous, free-form questions naturally — a rule-based router would break on anything outside the expected patterns.

A rule-based router (keyword matching or regex on the question) would cut latency roughly in half by eliminating the first LLM call entirely, and would reduce token cost proportionally. For a production system with predictable query patterns, that's the right tradeoff. However, this project is specifically scoped to demonstrate LLM function calling — routing via the LLM is the point of the exercise, not an oversight.

**Two LLM calls per question**
Call 1 decides which tool to call; Call 2 generates the answer. This doubles latency and token cost compared to a single call, but is necessary — without `tool_choice="none"` on Call 2, the model attempts another tool call instead of writing an answer.

**Filtering in Python, not at the source**
The connectors load the full JSON and filter in memory. Simple and correct for small datasets, but won't scale. With a real database, the filter would be pushed into the query itself — for example, `SELECT * FROM customers WHERE status = 'active' LIMIT 10` — so the database returns only matching rows and Python never loads the rest. The connector abstraction makes this swap clean: only the connector's `fetch()` changes; the router, business rules, and LLM layer stay untouched. The current Python filtering is essentially a JSON limitation — JSON has no query engine.

**Pre-computed `metadata.context`**
The server summarises results into a plain-English string ("Showing 8 of 12 tickets. 3 high-priority") before the LLM sees the data. The LLM can quote this directly without counting records itself, reducing hallucination risk. The tradeoff is that the summary logic is hardcoded and must be updated if requirements change.

**Data-driven freshness via `last_updated`**
Each JSON file is wrapped in `{"last_updated": "...", "records": [...]}`. The `_freshness()` function reads this field directly instead of using the file's OS mtime. This makes freshness immune to deploy/copy operations that touch the file without changing the data — the timestamp only moves when someone intentionally updates it.

**Connector abstraction**
Connectors add a layer over what is currently just JSON reads. For this project they're mostly demonstrating separation of concerns — the real value shows up when swapping sources (JSON → Postgres, REST API). Only the connector changes; the router, models, and business logic stay untouched.

**Pydantic models defined but not enforced at the connector level**
The repo defines `Customer`, `Metric`, and `Ticket` Pydantic models, but the connectors return raw `List[Dict]` — the models are never called to validate incoming records. Pydantic is only enforced at the FastAPI response boundary (`DataResponse`). For this project's controlled, static JSON files this is acceptable: the data is trusted and read-only, so a bad record is unlikely. In a production system, connectors should parse each record through `model_validate()` at the point data enters the application — a `ValidationError` there is far easier to debug than a `KeyError` deep in business logic. The only practical reasons to skip connector-level validation are extreme batch-processing scale (where per-record overhead matters) or legacy codebases where retrofitting is deferred. Neither applies here; it was a scope shortcut.

---

## What I'd Improve With More Time

- **Push filtering to the source** — for a DB-backed version, pass filters as query predicates rather than loading all records and filtering in Python.
- **Multi-tool questions** — currently handles only one tool call per question. A question like "which active customers have open high-priority tickets?" requires calling both CRM and support tools and joining results. This needs an agent loop.
- **Streaming responses** — for longer answers, stream the second LLM call back to the user instead of waiting for the full response.
- **Tests** — add unit tests for connectors (filter logic), business rules (sort order), and voice optimizer (context strings). The connector abstraction makes these easy to mock.
- **Model fallback** — if the primary Groq model is unavailable, automatically retry with a backup model instead of failing hard.

---

## What I Learned

**Function calling is a two-step contract** — the LLM never directly calls your API. It outputs a structured JSON description of what it *wants* to call, your code executes it, and then the LLM reads the result. Understanding this loop was the core insight.

**Tool descriptions are prompt engineering** — the quality of the tool `description` fields in the schema directly determines whether the LLM picks the right tool. Vague descriptions lead to wrong routing; specific ones with examples work reliably.

**Date handling is surprisingly tricky** — LLMs reason about relative time ("last week") in training data terms, not real calendar terms. Without an injected current date in the system prompt, every date-based query produces wrong or unusable params.

**Free-tier LLM APIs have real operational risks** — two models were decommissioned during development, one provider had regional restrictions, and one required a retry loop for transient failures. Production systems need model versioning and fallback strategies.

**Metadata is as important as data** — the `total_results` vs `returned_results` distinction and the `context` string are what allow the LLM to give accurate answers. Without them, the model would count 10 returned records and confidently say "there are 10 tickets total."
