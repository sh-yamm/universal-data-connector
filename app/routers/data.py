import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.connectors.crm_connector import CRMConnector, DATA_PATH as CRM_DATA_PATH
from app.connectors.support_connector import SupportConnector, DATA_PATH as SUPPORT_DATA_PATH
from app.connectors.analytics_connector import AnalyticsConnector, DATA_PATH as ANALYTICS_DATA_PATH
from app.services.business_rules import apply_business_rules
from app.services.voice_optimizer import build_voice_context
from app.models.common import DataResponse, Metadata

logger = logging.getLogger(__name__)

# All three data endpoints share this /api prefix
router = APIRouter(prefix="/api")


def _freshness(data_path: Path) -> str:
    """Reads last_updated from the JSON file itself — immune to deploy/copy touching the mtime."""
    try:
        with open(data_path) as f:
            last_updated_str = json.load(f).get("last_updated")
    except FileNotFoundError:
        return "Data freshness unknown"

    if not last_updated_str:
        return "Data freshness unknown"

    # Parse the ISO timestamp stored in the file (e.g. "2026-02-20T00:00:00Z")
    last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - last_updated
    seconds = int(delta.total_seconds())

    # Bucket into minutes / hours / days — avoids confusing "3600 seconds ago"
    if seconds < 60:
        return "Data updated just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"Data as of {minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"Data as of {hours} hour{'s' if hours != 1 else ''} ago"
    days = seconds // 86400
    return f"Data as of {days} day{'s' if days != 1 else ''} ago"


# ---------------------------------------------------------------------------
# CRM endpoint
# ---------------------------------------------------------------------------

@router.get("/customers", response_model=DataResponse, summary="Get customers")
def get_customers(
    status: Optional[str] = Query(
        None,
        description="Filter by status: active | inactive | all",
        pattern="^(active|inactive|all)$",  # regex keeps invalid values out at the HTTP layer
    ),
    created_after: Optional[str] = Query(
        None,
        description="ISO date string – return customers created on or after this date, e.g. 2025-01-01",
    ),
    limit: int = Query(10, ge=1, le=50, description="Max records to return"),
):
    connector = CRMConnector()
    try:
        raw = connector.fetch(status=status, created_after=created_after)
    except FileNotFoundError:
        logger.error("Customer data file not found: %s", CRM_DATA_PATH)
        raise HTTPException(status_code=503, detail="Customer data is currently unavailable.")
    total = len(raw)  # total before slicing — goes into metadata so LLM knows there's more

    results = apply_business_rules(raw, data_type="tabular_crm", limit=limit)
    context = build_voice_context(results, total, "tabular_crm")

    logger.info("GET /api/customers → %d/%d records", len(results), total)
    return DataResponse(
        data=results,
        metadata=Metadata(
            total_results=total,
            returned_results=len(results),
            data_freshness=_freshness(CRM_DATA_PATH),
            context=context,
        ),
    )


# ---------------------------------------------------------------------------
# Support tickets endpoint
# ---------------------------------------------------------------------------

@router.get("/support/tickets", response_model=DataResponse, summary="Get support tickets")
def get_support_tickets(
    status: Optional[str] = Query(
        None,
        description="Filter by status: open | closed | all",
        pattern="^(open|closed|all)$",
    ),
    priority: Optional[str] = Query(
        None,
        description="Filter by priority: high | medium | low | all",
        pattern="^(high|medium|low|all)$",
    ),
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    limit: int = Query(10, ge=1, le=50, description="Max records to return"),
):
    connector = SupportConnector()
    try:
        raw = connector.fetch(status=status, priority=priority, customer_id=customer_id)
    except FileNotFoundError:
        logger.error("Support data file not found: %s", SUPPORT_DATA_PATH)
        raise HTTPException(status_code=503, detail="Support ticket data is currently unavailable.")
    total = len(raw)

    results = apply_business_rules(raw, data_type="tabular_support", limit=limit)
    context = build_voice_context(results, total, "tabular_support")

    logger.info("GET /api/support/tickets → %d/%d records", len(results), total)
    return DataResponse(
        data=results,
        metadata=Metadata(
            total_results=total,
            returned_results=len(results),
            data_freshness=_freshness(SUPPORT_DATA_PATH),
            context=context,
        ),
    )


# ---------------------------------------------------------------------------
# Analytics endpoint
# ---------------------------------------------------------------------------

@router.get("/analytics/metrics", response_model=DataResponse, summary="Get analytics metrics")
def get_analytics_metrics(
    metric: Optional[str] = Query(
        None,
        description="Metric name: daily_active_users | revenue",
        pattern="^(daily_active_users|revenue)$",
    ),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD (inclusive)"),
    aggregation: Optional[str] = Query(
        None,
        description="Aggregate values: sum | avg | max | min",
        pattern="^(sum|avg|max|min)$",
    ),
    limit: int = Query(10, ge=1, le=50, description="Max records to return (ignored when aggregation is set)"),
):
    connector = AnalyticsConnector()
    try:
        raw = connector.fetch(metric=metric, date_from=date_from, date_to=date_to)
    except FileNotFoundError:
        logger.error("Analytics data file not found: %s", ANALYTICS_DATA_PATH)
        raise HTTPException(status_code=503, detail="Analytics data is currently unavailable.")
    total = len(raw)

    # When aggregation is requested, collapse all matching records into one number
    if aggregation and raw:
        values = [r.get("value", 0) for r in raw]
        agg_map = {
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "max": max(values),
            "min": min(values),
        }
        agg_value = round(agg_map[aggregation], 2)
        # Return a single synthetic record so the response shape stays consistent
        result_record = {
            "metric": metric or "all",
            "aggregation": aggregation,
            "value": agg_value,
            "records_used": len(raw),  # tells the LLM how many days fed into this number
        }
        ctx = f"{aggregation.upper()} across {total} daily records = {agg_value}"
        logger.info("GET /api/analytics/metrics (aggregated) → %s=%s", aggregation, agg_value)
        return DataResponse(
            data=[result_record],
            metadata=Metadata(
                total_results=total,
                returned_results=total,  # all records were used in the aggregation
                data_freshness=_freshness(ANALYTICS_DATA_PATH),
                context=ctx,
            ),
        )

    results = apply_business_rules(raw, data_type="time_series", limit=limit)
    context = build_voice_context(results, total, "time_series")

    logger.info("GET /api/analytics/metrics → %d/%d records", len(results), total)
    return DataResponse(
        data=results,
        metadata=Metadata(
            total_results=total,
            returned_results=len(results),
            data_freshness=_freshness(ANALYTICS_DATA_PATH),
            context=context,
        ),
    )
