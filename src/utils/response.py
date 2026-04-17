"""
utils/response.py — Lambda proxy integration response helpers.
"""
import json
from typing import Any, Dict, Optional


def success(body: Any, status_code: int = 200) -> Dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


def error(message: str, status_code: int = 400, details: Optional[Any] = None) -> Dict:
    payload: Dict[str, Any] = {"error": message}
    if details:
        payload["details"] = details
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(payload),
    }


def not_found(resource: str = "Resource") -> Dict:
    return error(f"{resource} not found", 404)


def internal_error(exc: Exception) -> Dict:
    return error("Internal server error", 500, str(exc))
