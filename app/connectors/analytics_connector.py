import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base import BaseConnector

logger = logging.getLogger(__name__)


def _clamp_date(date_str: str) -> str:
    """LLMs sometimes hallucinate dates like 2026-02-29. Clamp them to the real last day of the month."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str  # already valid
    except ValueError:
        # Try to salvage year-month and clamp to last valid day
        parts = date_str.split("-")
        if len(parts) == 3:
            import calendar
            year, month = int(parts[0]), int(parts[1])
            last_day = calendar.monthrange(year, month)[1]
            clamped = f"{year:04d}-{month:02d}-{last_day:02d}"
            logger.warning("Invalid date %s clamped to %s", date_str, clamped)
            return clamped
        return date_str  # give up, let string comparison proceed


DATA_PATH = Path(__file__).parent.parent.parent / "data" / "analytics.json"


class AnalyticsConnector(BaseConnector):

    def fetch(
        self,
        metric: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        # Load metrics — JSON is wrapped in {"last_updated": ..., "records": [...]}
        with open(DATA_PATH) as f:
            records = json.load(f)["records"]

        logger.info("Loaded %d metric records from file", len(records))

        # Filter to one metric type if specified
        if metric:
            records = [r for r in records if r["metric"] == metric]
            logger.info("After metric filter (%s): %d records", metric, len(records))

        # Date range filtering — YYYY-MM-DD strings sort correctly with plain string comparison
        if date_from:
            date_from = _clamp_date(date_from)
            records = [r for r in records if r["date"] >= date_from]
            logger.info("After date_from filter (%s): %d records", date_from, len(records))

        if date_to:
            date_to = _clamp_date(date_to)
            records = [r for r in records if r["date"] <= date_to]
            logger.info("After date_to filter (%s): %d records", date_to, len(records))

        return records
