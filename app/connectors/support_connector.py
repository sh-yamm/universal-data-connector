import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base import BaseConnector

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "support_tickets.json"


class SupportConnector(BaseConnector):

    def fetch(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        customer_id: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        # Load tickets — JSON is wrapped in {"last_updated": ..., "records": [...]}
        with open(DATA_PATH) as f:
            tickets = json.load(f)["records"]

        logger.info("Loaded %d tickets from file", len(tickets))

        # Each filter is independent — stack them to narrow down results
        if status and status != "all":
            tickets = [t for t in tickets if t["status"] == status]
            logger.info("After status filter (%s): %d tickets", status, len(tickets))

        if priority and priority != "all":
            tickets = [t for t in tickets if t["priority"] == priority]
            logger.info("After priority filter (%s): %d tickets", priority, len(tickets))

        # Used when someone asks "show me tickets for customer #5"
        if customer_id is not None:
            tickets = [t for t in tickets if t["customer_id"] == customer_id]
            logger.info("After customer_id filter (%d): %d tickets", customer_id, len(tickets))

        return tickets
