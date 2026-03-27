import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseConnector

logger = logging.getLogger(__name__)

# Absolute path so it works regardless of where uvicorn is launched from
DATA_PATH = Path(__file__).parent.parent.parent / "data" / "customers.json"


class CRMConnector(BaseConnector):

    def fetch(
        self,
        status: Optional[str] = None,
        created_after: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        # Load customers — JSON is wrapped in {"last_updated": ..., "records": [...]}
        with open(DATA_PATH) as f:
            customers = json.load(f)["records"]

        logger.info("Loaded %d customers from file", len(customers))

        # Filter by account status — skip if "all" or not provided
        if status and status != "all":
            customers = [c for c in customers if c["status"] == status]
            logger.info("After status filter (%s): %d customers", status, len(customers))

        # Filter by signup date — useful for "customers who joined this month" queries
        if created_after:
            try:
                after_dt = datetime.fromisoformat(created_after)
                customers = [
                    c for c in customers
                    if datetime.fromisoformat(c["created_at"]) >= after_dt
                ]
                logger.info(
                    "After created_after filter (%s): %d customers",
                    created_after,
                    len(customers),
                )
            except ValueError:
                logger.warning("Invalid created_after date format: %s", created_after)

        return customers
