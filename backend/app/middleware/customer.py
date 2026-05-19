from __future__ import annotations
from uuid import UUID

from fastapi import Header, HTTPException

DEMO_CUSTOMER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_customer_id(x_customer_id: str | None = Header(default=None)) -> UUID:
    """
    Inject the resolved customer ID. Falls back to DEMO_CUSTOMER_ID for
    unauthenticated local development. Raises 400 on a malformed header.
    """
    if x_customer_id is None:
        return DEMO_CUSTOMER_ID
    try:
        return UUID(x_customer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_CUSTOMER_ID",
            "message": "X-customer-Id header must be a valid UUID",
        })
