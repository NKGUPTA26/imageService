"""
handlers/delete_image.py — DELETE /images/{image_id}

Performs a two-phase delete:
  1. Delete the S3 object
  2. Delete the DynamoDB record

Both operations are attempted even if one fails so we don't leave orphaned
records. The response indicates partial failure when it occurs.

Returns 200 on full success, 404 if the image was not found, 207 on partial
failure.
"""
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

        # ---- Verify existence -----------------------------------------
        metadata = _ddb.get_image_metadata(image_id)
        if metadata is None:
            return not_found("Image")

        errors = []

        # ---- Delete from S3 -------------------------------------------
        try:
            _s3.delete_object(metadata.s3_key)
        except Exception as exc:
            logger.error("Failed to delete S3 object %s: %s", metadata.s3_key, exc)
            errors.append(f"S3 delete failed: {exc}")

        # ---- Delete from DynamoDB -------------------------------------
        try:
            _ddb.delete_image_metadata(image_id)
        except Exception as exc:
            logger.error("Failed to delete DynamoDB record %s: %s", image_id, exc)
            errors.append(f"DynamoDB delete failed: {exc}")

        if errors:
            return {
                "statusCode": 207,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": str({
                    "message": "Partial deletion — some resources could not be cleaned up.",
                    "errors": errors,
                    "image_id": image_id,
                }),
            }

        return success(
            {"message": "Image deleted successfully.", "image_id": image_id}
        )

    except Exception as exc:
        logger.exception("Unhandled error in delete_image handler")
        return internal_error(exc)
