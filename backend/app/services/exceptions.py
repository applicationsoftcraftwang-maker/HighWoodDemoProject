from __future__ import annotations


class EmissionsPlatformError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_hint: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_hint = status_hint


class CustomerSiteNotFoundError(EmissionsPlatformError):
    def __init__(self, site_id: str) -> None:
        super().__init__(
            code="CUSTOMER_SITE_NOT_FOUND",
            message=(
                f"Methane monitoring site '{site_id}' was not found for this "
                "customer."
            ),
            status_hint=404,
        )
        self.site_id = site_id


class MethaneIngestionTokenConflictError(EmissionsPlatformError):
    def __init__(self, ingestion_token: str) -> None:
        super().__init__(
            code="METHANE_INGESTION_TOKEN_CONFLICT",
            message=(
                "This methane ingestion token was already used for a different "
                "set of readings. Please submit the corrected data with a new "
                "ingestion token."
            ),
            status_hint=409,
        )
        self.ingestion_token = ingestion_token


class MethaneIngestionJobNotFoundError(EmissionsPlatformError):
    def __init__(self, ingestion_job_id: str) -> None:
        super().__init__(
            code="METHANE_INGESTION_JOB_NOT_FOUND",
            message=(
                f"Methane ingestion job '{ingestion_job_id}' was not found for "
                "this customer."
            ),
            status_hint=404,
        )
        self.ingestion_job_id = ingestion_job_id


class InvalidMethaneReadingError(EmissionsPlatformError):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="INVALID_METHANE_READING",
            message=message,
            status_hint=400,
        )


class MethaneEmissionThresholdExceededError(EmissionsPlatformError):
    def __init__(
        self,
        site_id: str,
        current_total: float | None = None,
        emission_limit: float | None = None,
    ) -> None:
        details = ""

        if current_total is not None and emission_limit is not None:
            details = (
                f" Current total: {current_total}. "
                f"Configured limit: {emission_limit}."
            )

        super().__init__(
            code="METHANE_EMISSION_THRESHOLD_EXCEEDED",
            message=(
                f"Methane monitoring site '{site_id}' has exceeded its "
                f"configured emission threshold.{details}"
            ),
            status_hint=409,
        )
        self.site_id = site_id
        self.current_total = current_total
        self.emission_limit = emission_limit
