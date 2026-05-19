class EmissionsError(Exception):
    """Base domain exception. Carries an error code + HTTP status hint."""
    def __init__(self, code: str, message: str, status_hint: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_hint = status_hint


class SiteNotFoundError(EmissionsError):
    def __init__(self, site_id: str):
        super().__init__(
            "SITE_NOT_FOUND",
            f"Site {site_id} not found",
            404,
        )
