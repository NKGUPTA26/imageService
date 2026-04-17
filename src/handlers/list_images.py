"""
handlers/list_images.py — GET /images

Query parameters:
  user_id  (filter 1) — return images belonging to this user
  tag      (filter 2) — return images with this tag
  limit    — max records per page (default 20, max 100)
  cursor   — pagination token (opaque base64-encoded LastEvaluatedKey)

Both filters can be combined (AND logic: images by user_id that also carry tag).
"""
import base64
import json
import logging

from src.services.dynamodb_service import DynamoDBService
from src.utils.response import error, success, internal_error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_ddb = DynamoDBService()

MAX_LIMIT = 100


def handler(event: dict, context) -> dict:
    try:
        params = event.get("queryStringParameters") or {}

        user_id = params.get("user_id", "").strip() or None
        tag     = params.get("tag", "").strip() or None

        # ---- Pagination limit -----------------------------------------
        try:
            limit = min(int(params.get("limit", 20)), MAX_LIMIT)
        except ValueError:
            return error("'limit' must be a positive integer.", 400)

        # ---- Decode cursor --------------------------------------------
        last_evaluated_key = None
        cursor = params.get("cursor", "").strip()
        if cursor:
            try:
                last_evaluated_key = json.loads(
                    base64.urlsafe_b64decode(cursor.encode()).decode()
                )
            except Exception:
                return error("Invalid pagination cursor.", 400)

        # ---- Query ----------------------------------------------------
        result = _ddb.list_images(
            user_id=user_id,
            tag=tag,
            limit=limit,
            last_evaluated_key=last_evaluated_key,
        )

        # ---- Encode next cursor ---------------------------------------
        next_cursor = None
        if result["last_evaluated_key"]:
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(result["last_evaluated_key"]).encode()
            ).decode()

        images = [img.to_response_dict() for img in result["items"]]

        return success(
            {
                "count":       len(images),
                "images":      images,
                "next_cursor": next_cursor,
                "filters":     {"user_id": user_id, "tag": tag},
            }
        )

    except Exception as exc:
        logger.exception("Unhandled error in list_images handler")
        return internal_error(exc)
