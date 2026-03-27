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
        customer_ids: Optional[List[int]] = None,
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

        # Supports single or multiple customer IDs — used for cross-customer queries
        if customer_ids:
            id_set = set(customer_ids)
            tickets = [t for t in tickets if t["customer_id"] in id_set]
            logger.info("After customer_ids filter %s: %d tickets", customer_ids, len(tickets))

        return tickets
