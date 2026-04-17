"""
services/s3_service.py — All S3 interactions in one place.
"""
import logging
from typing import Optional, Tuple

from botocore.exceptions import ClientError

from src.config import S3_BUCKET, PRESIGNED_URL_EXPIRY
from src.utils.aws_clients import get_s3_client

logger = logging.getLogger(__name__)


class S3Service:
    def __init__(self):
        self._client = get_s3_client()

    # ------------------------------------------------------------------ #
    #  Write
    # ------------------------------------------------------------------ #

    def upload_image(
        self,
        s3_key: str,
        data: bytes,
        content_type: str,
        metadata: dict,
    ) -> bool:
        """Upload raw bytes to S3. Returns True on success."""
        try:
            self._client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=data,
                ContentType=content_type,
                Metadata={k: str(v) for k, v in metadata.items()},
                ServerSideEncryption="AES256",
            )
            logger.info("Uploaded s3://%s/%s (%d bytes)", S3_BUCKET, s3_key, len(data))
            return True
        except ClientError as e:
            logger.error("S3 upload failed: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Read
    # ------------------------------------------------------------------ #

    def generate_presigned_url(self, s3_key: str) -> str:
        """
        Return a time-limited presigned URL.
        Callers can redirect to this URL for direct browser downloads.
        """
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )

    def get_object(self, s3_key: str) -> Tuple[bytes, str]:
        """Download raw bytes + content-type. Raises ClientError if missing."""
        response = self._client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        body = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")
        return body, content_type

    def object_exists(self, s3_key: str) -> bool:
        try:
            self._client.head_object(Bucket=S3_BUCKET, Key=s3_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise

    # ------------------------------------------------------------------ #
    #  Delete
    # ------------------------------------------------------------------ #

    def delete_object(self, s3_key: str) -> bool:
        try:
            self._client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            logger.info("Deleted s3://%s/%s", S3_BUCKET, s3_key)
            return True
        except ClientError as e:
            logger.error("S3 delete failed: %s", e)
            raise
