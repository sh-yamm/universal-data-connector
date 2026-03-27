"""
OpenAI function/tool definitions for the Universal Data Connector.

These schemas are sent to the LLM with every request via the `tools` parameter.
The LLM reads them to decide which function to call and what args to fill in —
it never sees the actual data until after it makes the call.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_customers",
            # Good descriptions matter: the LLM uses these to pick the right tool
            "description": (
                "Retrieve customer records from the CRM system. "
                "Use this for any question about customers: how many exist, "
                "their status (active / inactive), or when they signed up."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "all"],
                        "description": "Filter customers by account status.",
                    },
                    "created_after": {
                        "type": "string",
                        "description": (
                            "Return only customers created on or after this date. "
                            "ISO 8601 date string, e.g. '2025-01-01'."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of records to return (1–50).",
                    },
                },
                "required": [],  # no required params — all filters are optional
            },
        },
    },
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
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter tickets by status.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "all"],
                        "description": "Filter tickets by priority level.",
                    },
                    "customer_ids": {
                        "type": "string",
                        "description": (
                            "Return only tickets for these customer IDs. "
                            "Pass as a JSON array string, e.g. '[39, 5, 50]'."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of records to return (1–50).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_analytics_metrics",
            "description": (
                "Retrieve analytics metrics such as daily active users (DAU) or "
                "revenue. Use this for performance KPIs, trends over a date range, "
                "or aggregated totals / averages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["daily_active_users", "revenue"],
                        "description": "Which metric to retrieve.",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (inclusive).",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (inclusive).",
                    },
                    "aggregation": {
                        "type": "string",
                        "enum": ["sum", "avg", "max", "min"],
                        "description": (
                            "Collapse all matching records into a single aggregated value. "
                            "When set, `limit` is ignored."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of raw records to return (1–50).",
                    },
                },
                "required": [],
            },
        },
    },
]
