from typing import List, Dict, Any, Optional


def build_voice_context(
    data: List[Dict[str, Any]],
    total_count: int,
    data_type: str = "unknown",
) -> str:
    """
    Builds a short plain-English summary that goes into metadata.context.
    The LLM reads this and can quote it directly — no extra math needed on its end.
    """
    returned = len(data)  # how many records we actually returned (post-limit)

    if data_type == "tabular_support":
        # Count urgent items in the returned slice so the LLM can flag them
        high = sum(1 for t in data if t.get("priority") == "high")
        open_count = sum(1 for t in data if t.get("status") == "open")
        ctx = f"Showing {returned} of {total_count} tickets"
        if high:
            ctx += f". {high} high-priority"
        if open_count and open_count != returned:
            # Only mention open count if it's a meaningful subset (not just all of them)
            ctx += f". {open_count} open"
        return ctx

    if data_type == "tabular_crm":
        active = sum(1 for c in data if c.get("status") == "active")
        ctx = f"Showing {returned} of {total_count} customers"
        if active:
            ctx += f". {active} active"
        return ctx

    if data_type == "time_series":
        if data:
            values = [r.get("value", 0) for r in data]
            # Min/max gives a quick sense of volatility without extra LLM calls
            return (
                f"Showing {returned} of {total_count} data points. "
                f"Range: {min(values):.0f}-{max(values):.0f}"
            )
        return "No data points available"

    # Generic fallback for unknown data shapes
    return f"Showing {returned} of {total_count} records"


# Keep old name as alias
def summarize_if_large(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(data) > 10:
        return [{"summary": f"{len(data)} records found. Showing first 10."}]
    return data
