from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Site ─────────────────────────────────────────────────────────────────────

class CreateSiteRequest(BaseModel):
    site_name: str = Field(..., min_length=1, max_length=255)
    site_location: str = Field(..., min_length=1, max_length=255)
    methane_emission_limit: Decimal = Field(..., gt=0)
    site_metadata: dict[str, Any] | None = None


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: UUID
    customer_id: UUID
    site_name: str
    site_location: str
    methane_emission_limit: Decimal
    methane_accumulated_emissions_to_date: Decimal
    site_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime