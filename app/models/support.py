from pydantic import BaseModel
from typing import Optional
from enum import Enum
from datetime import datetime


# Enums keep the LLM tool definitions and query params honest — no free-text values
class TicketStatus(str, Enum):
    open = "open"
    closed = "closed"
    all = "all"


class TicketPriority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    all = "all"


# Mirrors one record in data/support_tickets.json
class Ticket(BaseModel):
    ticket_id: int
    customer_id: int
    subject: str
    priority: str
    created_at: datetime
    status: str


# What the /api/support/tickets endpoint accepts as query params
class TicketQuery(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    customer_id: Optional[int] = None
    limit: int = 10
