"""
services/dynamodb_service.py — All DynamoDB interactions in one place.

Two GSIs are used for filter-based listing:
  1. user_id-uploaded_at-index  → filter by owner
  2. tag-uploaded_at-index      → filter by tag

Both indexes sort by uploaded_at (ISO-8601) so results are chronological.
"""
import logging
from typing import List, Optional

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from src.config import DYNAMODB_TABLE
from src.models.image_metadata import ImageMetadata
from src.utils.aws_clients import get_dynamodb_resource

logger = logging.getLogger(__name__)


class DynamoDBService:
    def __init__(self):
        resource = get_dynamodb_resource()
        self._table = resource.Table(DYNAMODB_TABLE)

    # ------------------------------------------------------------------ #
    #  Write
    # ------------------------------------------------------------------ #

    def put_image_metadata(self, metadata: ImageMetadata) -> bool:
        try:
            self._table.put_item(Item=metadata.to_item())
            logger.info("Saved metadata for image_id=%s", metadata.image_id)
            return True
        except ClientError as e:
            logger.error("DynamoDB put_item failed: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Read — single item
    # ------------------------------------------------------------------ #

    def get_image_metadata(self, image_id: str) -> Optional[ImageMetadata]:
        try:
            response = self._table.get_item(Key={"image_id": image_id})
            item = response.get("Item")
            return ImageMetadata.from_item(item) if item else None
        except ClientError as e:
            logger.error("DynamoDB get_item failed: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Read — list with filters
    # ------------------------------------------------------------------ #

    def list_images(
        self,
        user_id: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 50,
        last_evaluated_key: Optional[dict] = None,
    ) -> dict:
        """
        Returns {"items": [...], "last_evaluated_key": {...} | None}

        Filter priority:
          1. user_id  → query GSI user_id-uploaded_at-index
          2. tag      → query GSI tag-uploaded_at-index
          3. (none)   → scan (acceptable at small scale; use a GSI in prod)

        Combining both filters: query by user_id GSI then apply a filter
        expression on tag (avoids a scatter-gather scan).
        """
        kwargs = {"Limit": limit}
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key

        try:
            if user_id and tag:
                # Query user GSI, then filter by tag client-side via FilterExpression
                kwargs["IndexName"] = "user_id-uploaded_at-index"
                kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id)
                kwargs["FilterExpression"] = Attr("tag").eq(tag)
                kwargs["ScanIndexForward"] = False   # newest first
                response = self._table.query(**kwargs)

            elif user_id:
                kwargs["IndexName"] = "user_id-uploaded_at-index"
                kwargs["KeyConditionExpression"] = Key("user_id").eq(user_id)
                kwargs["ScanIndexForward"] = False
                response = self._table.query(**kwargs)

            elif tag:
                kwargs["IndexName"] = "tag-uploaded_at-index"
                kwargs["KeyConditionExpression"] = Key("tag").eq(tag)
                kwargs["ScanIndexForward"] = False
                response = self._table.query(**kwargs)

            else:
                # No filters — full scan (paginated)
                response = self._table.scan(**kwargs)

            items = [ImageMetadata.from_item(i) for i in response.get("Items", [])]
            return {
                "items": items,
                "last_evaluated_key": response.get("LastEvaluatedKey"),
            }

        except ClientError as e:
            logger.error("DynamoDB list failed: %s", e)
            raise

    # ------------------------------------------------------------------ #
    #  Delete
    # ------------------------------------------------------------------ #

    def delete_image_metadata(self, image_id: str) -> bool:
        try:
            self._table.delete_item(Key={"image_id": image_id})
            logger.info("Deleted metadata for image_id=%s", image_id)
            return True
        except ClientError as e:
            logger.error("DynamoDB delete_item failed: %s", e)
            raise
