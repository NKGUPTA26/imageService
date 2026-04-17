"""
tests/test_delete_image.py — Tests for DELETE /images/{image_id}.
"""
import json
import boto3
import pytest

from tests.conftest import TINY_JPEG_B64, make_apigw_event


def _upload(user_id="u1"):
    from src.handlers.upload import handler as upload_handler
    body = {
        "user_id": user_id,
        "filename": "del_test.jpg",
        "content_type": "image/jpeg",
        "image_data": TINY_JPEG_B64,
        "tags": ["deletable"],
    }
    resp = upload_handler({"body": json.dumps(body)}, None)
    data = json.loads(resp["body"])
    return data["image"]["image_id"], data["image"]


class TestDeleteImageHandler:

    # ------------------------------------------------------------------ #
    #  Happy path
    # ------------------------------------------------------------------ #

    def test_delete_returns_200(self, aws_mock):
        from src.handlers.delete_image import handler
        image_id, _ = _upload()
        resp = handler(make_apigw_event(path_params={"image_id": image_id}), None)
        assert resp["statusCode"] == 200

    def test_delete_response_contains_image_id(self, aws_mock):
        from src.handlers.delete_image import handler
        image_id, _ = _upload()
        body = json.loads(
            handler(make_apigw_event(path_params={"image_id": image_id}), None)["body"]
        )
        assert body["image_id"] == image_id
        assert "deleted" in body["message"].lower()

    def test_delete_removes_metadata_from_dynamodb(self, aws_mock):
        from src.handlers.delete_image import handler
        from src.services.dynamodb_service import DynamoDBService

        image_id, _ = _upload()
        handler(make_apigw_event(path_params={"image_id": image_id}), None)

        # Metadata should be gone
        assert DynamoDBService().get_image_metadata(image_id) is None

    def test_delete_removes_object_from_s3(self, aws_mock):
        from src.handlers.delete_image import handler
        from src.services.dynamodb_service import DynamoDBService

        image_id, meta = _upload()
        # Capture s3_key before deletion
        record = DynamoDBService().get_image_metadata(image_id)
        s3_key = record.s3_key

        handler(make_apigw_event(path_params={"image_id": image_id}), None)

        s3 = boto3.client("s3", region_name="us-east-1")
        objects = s3.list_objects_v2(Bucket="test-bucket")
        keys = [o["Key"] for o in objects.get("Contents", [])]
        assert s3_key not in keys

    def test_delete_image_no_longer_retrievable(self, aws_mock):
        from src.handlers.delete_image import handler
        from src.handlers.get_image import handler as get_handler

        image_id, _ = _upload()
        handler(make_apigw_event(path_params={"image_id": image_id}), None)

        # Subsequent GET should 404
        get_resp = get_handler(make_apigw_event(path_params={"image_id": image_id}), None)
        assert get_resp["statusCode"] == 404

    def test_delete_image_no_longer_in_list(self, aws_mock):
        from src.handlers.delete_image import handler
        from src.handlers.list_images import handler as list_handler

        image_id, _ = _upload(user_id="owner")
        handler(make_apigw_event(path_params={"image_id": image_id}), None)

        list_resp = json.loads(
            list_handler(make_apigw_event(query_params={"user_id": "owner"}), None)["body"]
        )
        ids = [img["image_id"] for img in list_resp["images"]]
        assert image_id not in ids

    # ------------------------------------------------------------------ #
    #  Error cases
    # ------------------------------------------------------------------ #

    def test_delete_non_existent_returns_404(self, aws_mock):
        from src.handlers.delete_image import handler
        resp = handler(make_apigw_event(path_params={"image_id": "ghost-id"}), None)
        assert resp["statusCode"] == 404

    def test_delete_missing_path_param_returns_400(self, aws_mock):
        from src.handlers.delete_image import handler
        resp = handler(make_apigw_event(path_params={}), None)
        assert resp["statusCode"] == 400

    def test_delete_empty_image_id_returns_400(self, aws_mock):
        from src.handlers.delete_image import handler
        resp = handler(make_apigw_event(path_params={"image_id": "   "}), None)
        assert resp["statusCode"] == 400

    def test_double_delete_second_call_returns_404(self, aws_mock):
        from src.handlers.delete_image import handler
        image_id, _ = _upload()
        handler(make_apigw_event(path_params={"image_id": image_id}), None)
        resp = handler(make_apigw_event(path_params={"image_id": image_id}), None)
        assert resp["statusCode"] == 404
