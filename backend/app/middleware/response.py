from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi.responses import JSONResponse


API_VERSION = "v1"

def _meta() -> dict[str, str]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": API_VERSION,
    }

def success(data: Any, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "meta": _meta(),
        },
    )

def error(
    code: str,
    message: str,
    status_code: int = 400,
    details: Any = None,
) -> JSONResponse:
    error_body: dict[str, Any] = {
        "code": code,
        "message": message,
    }

    if details is not None:
        error_body["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_body,
            "meta": _meta(),
        },
    )