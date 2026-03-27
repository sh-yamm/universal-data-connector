from typing import List, Dict, Any, Optional
from app.config import settings

# Lower number = higher priority when sorting (high=0 beats medium=1 beats low=2)
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def apply_business_rules(
    data: List[Dict[str, Any]],
    data_type: str = "unknown",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Sort and cap results based on data type — keeps the most useful records at the top.

    Sorting strategy:
    - Support tickets: priority first (high → low), then newest within each priority
    - Customers: newest first
    - Analytics/time-series: most recent dates first
    """
    if limit is None:
        limit = settings.MAX_RESULTS  # fall back to global cap from .env

    if data_type == "tabular_support":
        # Two-pass stable sort: recency first, then priority on top.
        # Python's sort is stable, so equal-priority tickets keep their recency order.
        data = sorted(data, key=lambda x: x.get("created_at", ""), reverse=True)
        data = sorted(data, key=lambda x: PRIORITY_ORDER.get(x.get("priority", "low"), 2))

    elif data_type == "tabular_crm":
        # Newest customers first — useful for "who signed up recently?"
        data = sorted(data, key=lambda x: x.get("created_at", ""), reverse=True)

    elif data_type == "time_series":
        # Most recent dates first so the LLM sees current data before older data
        data = sorted(data, key=lambda x: x.get("date", ""), reverse=True)

    return data[:limit]  # slice after sorting so limit applies to the ranked list


# Keep old name as alias so nothing breaks if it's imported elsewhere
def apply_voice_limits(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return data[:settings.MAX_RESULTS]
