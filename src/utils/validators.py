"""
utils/validators.py — Input validation utilities.
"""
import base64
import binascii
from typing import Optional, Tuple

from src.config import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_SIZE


def validate_image_payload(
    image_data: Optional[str],
    content_type: Optional[str],
) -> Tuple[bool, str, Optional[bytes]]:
    """
    Validate a base64-encoded image payload.

    Returns (is_valid, error_message, decoded_bytes).
    """
    if not image_data:
        return False, "Missing 'image_data' field (base64-encoded image).", None

    if not content_type:
        return False, "Missing 'content_type' field.", None

    if content_type not in ALLOWED_CONTENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_CONTENT_TYPES))
        return False, f"Unsupported content_type. Allowed: {allowed}", None

    try:
        decoded = base64.b64decode(image_data)
    except (binascii.Error, ValueError):
        return False, "image_data is not valid base64.", None

    if len(decoded) > MAX_UPLOAD_SIZE:
        mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return False, f"Image exceeds maximum size of {mb} MB.", None

    return True, "", decoded


def validate_required_fields(body: dict, fields: list) -> Tuple[bool, str]:
    missing = [f for f in fields if not body.get(f)]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    return True, ""
