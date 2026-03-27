"""
Universal Data Connector – LLM Demo
====================================
Demonstrates end-to-end function calling:

  User question  →  OpenAI (decides which tool to call)
                 →  FastAPI server (fetches + filters data)
                 →  OpenAI (generates natural-language answer)
                 →  Printed response

Usage:
  # From project root with venv active:
  python -m client.llm_demo

  # Or pass a question directly:
  python -m client.llm_demo "How many open tickets do we have?"

Make sure the FastAPI server is running first:
  uvicorn app.main:app --reload
"""

import json
import logging
import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv
import time
from openai import OpenAI, RateLimitError, AuthenticationError, APIConnectionError, BadRequestError

logger = logging.getLogger(__name__)

# Ensure project root is on sys.path when run as a script (not a module)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.tool_definitions import TOOLS  # noqa: E402

load_dotenv(override=True)  # override=True ensures .env always wins over existing env vars

from datetime import date

API_BASE = "http://localhost:8000/api"
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # Llama 4 Scout — best Groq model for tool use
GROQ_BASE_URL = "https://api.groq.com/openai/v1"     # Groq is OpenAI-SDK-compatible, just swap the base URL


def _system_prompt() -> str:
    today = date.today().isoformat()
    # Inject today's date so the LLM can resolve "last 7 days" → actual YYYY-MM-DD range.
    # Without this, the model sends literal strings like "last 7 days" as date params.
    return (
        f"You are a concise business intelligence assistant. Today's date is {today}. "
        "Use the provided tools to answer questions about customers, "
        "support tickets, and analytics metrics. "
        "Always cite the numbers you get from the data. "
        "When calling tools that accept dates, always convert relative dates "
        f"(e.g. 'last 7 days', 'this month') to absolute ISO dates (YYYY-MM-DD) based on today ({today})."
    )

DEMO_QUESTIONS = [
    "How many open support tickets do we have?",
    "Show me our high priority tickets.",
    "How many active customers do we have?",
    "What's our total revenue for the last 7 days?",
    "What was the peak daily active user count this month?",
    "Show me tickets for customer number 5.",
    "How many customers signed up this year?",
]


def _call_api(function_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Bridge between the LLM's tool call and our FastAPI server — maps function name → HTTP GET."""
    endpoint_map = {
        "get_customers": f"{API_BASE}/customers",
        "get_support_tickets": f"{API_BASE}/support/tickets",
        "get_analytics_metrics": f"{API_BASE}/analytics/metrics",
    }
    url = endpoint_map.get(function_name)
    if not url:
        return {"error": f"Unknown function: {function_name}"}

    # Strip None values — FastAPI treats missing params as "no filter", not null
    params = {k: v for k, v in arguments.items() if v is not None}

    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("FastAPI returned %s for %s: %s", exc.response.status_code, url, exc.response.text)
        return {"error": f"API returned {exc.response.status_code}: {exc.response.text}"}
    except httpx.ConnectError:
        logger.error("Cannot connect to FastAPI server at %s", url)
        return {"error": "Cannot connect to FastAPI server. Is it running on localhost:8000?"}


def ask(question: str, client: OpenAI, verbose: bool = True) -> str:
    """
    Send a question through the full function-calling loop and return the
    final natural-language answer.
    """
    if verbose:
        print(f"\n{'-' * 60}")
        print(f"  Q: {question}")
        print("-" * 60)

    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": question},
    ]

    # --- Step 1: let the LLM decide which tool to call ---
    # tool_choice="auto" means the model can pick a tool or answer directly.
    # Retry once if Groq returns a tool_use_failed (transient formatting glitch).
    logger.debug("Step 1: sending question to LLM for tool selection — model=%s", MODEL)
    response = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            break
        except AuthenticationError:
            msg = "ERROR: Invalid API key. Check GROQ_API_KEY in your .env file."
            logger.error("Groq authentication failed — invalid API key")
            print(f"\n  {msg}")
            return msg
        except RateLimitError as exc:
            msg = f"ERROR: Rate limit hit. Wait a moment and try again.\n  ({exc})"
            logger.warning("Groq rate limit hit: %s", exc)
            print(f"\n  {msg}")
            return msg
        except APIConnectionError:
            msg = "ERROR: Cannot reach Groq API. Check your internet connection."
            logger.error("Groq API connection failed")
            print(f"\n  {msg}")
            return msg
        except BadRequestError as exc:
            if "tool_use_failed" in str(exc) and attempt == 0:
                logger.warning("tool_use_failed on attempt %d, retrying: %s", attempt + 1, exc)
                if verbose:
                    print("  (tool formatting glitch, retrying...)")
                time.sleep(1)
                continue
            msg = f"ERROR: Bad request: {exc}"
            logger.error("Groq bad request error: %s", exc)
            print(f"\n  {msg}")
            return msg

    if response is None:
        return "ERROR: Failed to get a response after retries."

    message = response.choices[0].message

    # --- Step 2: execute the tool call against our FastAPI server ---
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        fn_name = tool_call.function.name
        fn_args = json.loads(tool_call.function.arguments)  # LLM returns args as a JSON string

        if verbose:
            print(f"  Tool called : {fn_name}")
            print(f"  Arguments   : {json.dumps(fn_args, indent=4)}")

        logger.debug("Step 2: calling FastAPI — %s with args %s", fn_name, fn_args)
        api_result = _call_api(fn_name, fn_args)  # hit our FastAPI server

        if verbose:
            meta = api_result.get("metadata", {})
            print(f"  API context : {meta.get('context', '-')}")
            print(f"  Returned    : {meta.get('returned_results', '?')} / "
                  f"{meta.get('total_results', '?')} records")

        # Feed the tool result back into the conversation
        messages.append(message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(api_result),  # the full API response goes in as context
        })

        try:
            # tool_choice="none" is critical here — without it the model tries to call
            # another tool instead of just writing a plain-English answer
            final = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="none",
            )
            answer = final.choices[0].message.content or "(no response)"
        except RateLimitError as exc:
            answer = f"(quota exceeded while generating answer: {exc})"
    else:
        # LLM skipped tool calling and answered directly (e.g. "What is 2+2?")
        answer = message.content or "(no response)"

    if verbose:
        print(f"\n  A: {answer}")

    return answer


def main() -> None:
    # Set up logging — DEBUG shows internal LLM call steps, WARNING+ shows errors only
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)

    print("=" * 60)
    print("  Universal Data Connector - LLM Demo")
    print("=" * 60)

    # If a question was passed on the command line, answer it and exit
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        ask(question, client)
        return

    print("\nDemo questions:")
    for i, q in enumerate(DEMO_QUESTIONS, 1):
        print(f"  {i}. {q}")

    print("\nOptions:")
    print("  - Press Enter to run all demo questions")
    print("  - Type a number (1-7) to run one demo question")
    print("  - Type your own question")
    print("  - Type 'quit' to exit")

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        if user_input == "":
            for q in DEMO_QUESTIONS:
                ask(q, client)
            break

        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(DEMO_QUESTIONS):
                ask(DEMO_QUESTIONS[idx], client)
            else:
                print(f"Please enter a number between 1 and {len(DEMO_QUESTIONS)}.")
            continue

        ask(user_input, client)


if __name__ == "__main__":
    main()
