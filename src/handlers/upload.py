"""
handlers/upload.py — POST /images

Accepts a JSON body:
{
  "user_id":      "string (required)",
  "filename":     "string (required)",
  "content_type": "image/jpeg | image/png | ...",
  "image_data":   "<base64-encoded image bytes>",
  "description":  "optional free-text",
  "tags":         ["optional", "list", "of", "tags"]
}

Returns 201 with the saved metadata on success.
"""
import json
import logging

from src.models.image_metadata import ImageMetadata
from src.services.dynamodb_service import DynamoDBService
from src.services.s3_service import S3Service
from src.utils.response import error, success, internal_error
from src.utils.validators import validate_image_payload, validate_required_fields

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_s3  = S3Service()
_ddb = DynamoDBService()

REQUIRED_FIELDS = ["user_id", "filename", "content_type", "image_data"]


def handler(event: dict, context) -> dict:
    try:
        # ---- Parse body ------------------------------------------------
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return error("Request body must be valid JSON.", 400)

        # ---- Required-field validation ---------------------------------
        ok, msg = validate_required_fields(body, REQUIRED_FIELDS)
        if not ok:
            return error(msg, 400)

        user_id      = body["user_id"].strip()
        filename     = body["filename"].strip()
        content_type = body["content_type"].strip()
        image_data   = body["image_data"]
        description  = body.get("description", "")
        tags         = body.get("tags", [])

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # ---- Validate image payload ------------------------------------
        ok, msg, decoded_bytes = validate_image_payload(image_data, content_type)
        if not ok:
            return error(msg, 400)

        # ---- Build metadata record -------------------------------------
        metadata = ImageMetadata(
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            s3_key=f"images/{user_id}/{metadata_placeholder_id(filename)}",
            size_bytes=len(decoded_bytes),
            description=description,
            tags=tags,
        )
        # Fix s3_key now that image_id is known
        metadata.s3_key = f"images/{user_id}/{metadata.image_id}/{filename}"

        # ---- Upload to S3 ----------------------------------------------
        _s3.upload_image(
            s3_key=metadata.s3_key,
            data=decoded_bytes,
            content_type=content_type,
            metadata={
                "image_id":  metadata.image_id,
                "user_id":   user_id,
                "filename":  filename,
            },
        )

        # ---- Persist metadata to DynamoDB ------------------------------
        _ddb.put_image_metadata(metadata)

        return success(
            {
                "message": "Image uploaded successfully.",
                "image": metadata.to_response_dict(),
            },
            status_code=201,
        )

    except Exception as exc:
        logger.exception("Unhandled error in upload handler")
        return internal_error(exc)


def metadata_placeholder_id(filename: str) -> str:
    """Placeholder used before image_id is assigned — never actually stored."""
    return filename
