from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Mirrors one record in data/customers.json
class Customer(BaseModel):
    customer_id: int
    name: str
    email: str
    created_at: datetime
    status: str


# What the /api/customers endpoint accepts as query params
class CustomerQuery(BaseModel):
    status: Optional[str] = None        # "active" | "inactive" | "all"
    created_after: Optional[str] = None  # ISO date string e.g. "2025-01-01"
    limit: int = 10
