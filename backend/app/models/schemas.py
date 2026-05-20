from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
class MethaneEmissionUnit(str, Enum):
    kg = "kg"
    tonnes = "tonnes"
    lbs = "lbs"


class ComplianceStatus(str, Enum):
    within_limit = "within_limit"
    limit_exceeded = "limit_exceeded"
class IngestionProcessingStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    duplicate = "duplicate"
    failed = "failed"
class NotificationCategory(str, Enum):
    limit_warning = "limit_warning"
    limit_exceeded = "limit_exceeded"
    ingestion_failed = "ingestion_failed"
    system = "system"

# Site
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

# Methane ingestion


class MethaneEmissionReadingItem(BaseModel):
    emission_value: Decimal = Field(..., gt=0)
    emission_unit: MethaneEmissionUnit = MethaneEmissionUnit.kg
    captured_at: datetime


class IngestBatchRequest(BaseModel):
    site_id: UUID
    ingestion_token: str = Field(..., min_length=1, max_length=255)
    trace_request_id: str = Field(..., min_length=1, max_length=255)
    readings: list[MethaneEmissionReadingItem] = Field(
        ...,
        min_length=1,
        max_length=100,
    )


class IngestBatchResponse(BaseModel):
    ingestion_job_id: UUID
    customer_id: UUID
    site_id: UUID
    ingestion_token: str
    trace_request_id: str
    processing_status: IngestionProcessingStatus
    received_record_count: int
    processed_record_count: int
    total_methane_emission_value: float
    response_message: str | None = None
    response_error_message: str | None = None


# Notifications
class EmissionNotificationResponse(BaseModel):
    notification_id: UUID
    customer_id: UUID
    notification_category: NotificationCategory
    notification_message: str
    is_acknowledged: bool
    created_at: datetime
    acknowledged_at: datetime | None = None


# Audit events
class EmissionAuditEventResponse(BaseModel):
    audit_event_id: UUID
    customer_id: UUID
    performed_by: str | None = None
    event_action: str
    resource_type: str
    resource_id: UUID | None = None
    event_payload: dict[str, Any] | None = None
    created_at: datetime


class SiteMetricsResponse(BaseModel):
    site_id: UUID
    site_name: str
    emission_limit: float
    total_emissions_to_date: float
    compliance_status: ComplianceStatus
    utilization_percent: float
    measurement_count: int
    last_measurement_at: Optional[datetime]
