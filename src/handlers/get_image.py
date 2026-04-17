"""
handlers/get_image.py — GET /images/{image_id}

Query parameters:
  download=true   — return raw binary (base64-encoded in Lambda proxy response)
                    instead of a presigned redirect URL

Default behaviour: returns metadata + a presigned S3 URL valid for 1 hour.
The client can redirect to that URL for direct, high-throughput downloads
(bypasses Lambda and API Gateway, saving cost + latency).

With ?download=true: returns the image bytes directly (good for small images
or when the client cannot follow redirects).
"""
import base64
import logging

from src.services.dynamodb_service import DynamoDBService
from src.services.s3_service import S3Service
from src.utils.response import error, not_found, internal_error, success

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_ddb = DynamoDBService()
_s3  = S3Service()


def handler(event: dict, context) -> dict:
    try:
        image_id = (event.get("pathParameters") or {}).get("image_id", "").strip()
        if not image_id:
            return error("Missing path parameter: image_id", 400)

        params   = event.get("queryStringParameters") or {}
        download = params.get("download", "").lower() == "true"

        # ---- Fetch metadata -------------------------------------------
        metadata = _ddb.get_image_metadata(image_id)
        if metadata is None:
            return not_found("Image")

        # ---- Direct binary download -----------------------------------
        if download:
            image_bytes, content_type = _s3.get_object(metadata.s3_key)
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": content_type,
                    "Content-Disposition": f'attachment; filename="{metadata.filename}"',
                    "Access-Control-Allow-Origin": "*",
                },
                "body": base64.b64encode(image_bytes).decode(),
                "isBase64Encoded": True,
            }

        # ---- Presigned URL (default) ----------------------------------
        presigned_url = _s3.generate_presigned_url(metadata.s3_key)
        return success(
            {
                "image":        metadata.to_response_dict(),
                "download_url": presigned_url,
                "expires_in":   3600,
            }
        )

    except Exception as exc:
        logger.exception("Unhandled error in get_image handler")
        return internal_error(exc)
