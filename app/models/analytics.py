from pydantic import BaseModel
from typing import Optional
from enum import Enum


class AggregationType(str, Enum):
    sum = "sum"
    avg = "avg"
    max = "max"
    min = "min"


# Mirrors one record in data/analytics.json
class Metric(BaseModel):
    metric: str   # "daily_active_users" | "revenue"
    date: str     # "YYYY-MM-DD"
    value: float


# Returned when the caller requests aggregation (collapses many records into one number)
class AggregatedMetric(BaseModel):
    metric: str
    aggregation: str
    value: float
    records_used: int  # so the LLM knows how many days of data went into this number


# What the /api/analytics/metrics endpoint accepts as query params
class MetricQuery(BaseModel):
    metric: Optional[str] = None            # "daily_active_users" | "revenue"
    date_from: Optional[str] = None         # "YYYY-MM-DD"
    date_to: Optional[str] = None           # "YYYY-MM-DD"
    aggregation: Optional[AggregationType] = None
    limit: int = 10
