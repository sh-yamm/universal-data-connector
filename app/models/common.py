from pydantic import BaseModel
from typing import Any, List, Optional


# Wraps every API response — the LLM reads both `data` and `metadata` to answer questions
class Metadata(BaseModel):
    total_results: int       # how many records matched the filter (before slicing)
    returned_results: int    # how many we actually sent back (after limit)
    data_freshness: str      # e.g. "Data as of 3 minutes ago"
    context: Optional[str] = None  # plain-English summary, e.g. "Showing 10 of 25 tickets. 3 high-priority"


class DataResponse(BaseModel):
    data: List[Any]
    metadata: Metadata
