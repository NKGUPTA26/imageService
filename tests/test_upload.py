"""
tests/test_upload.py — Tests for POST /images (upload handler).
"""
import base64
import json
import pytest

from tests.conftest import TINY_JPEG_B64, make_apigw_event


class TestUploadHandler:

    # ------------------------------------------------------------------ #
    #  Happy path
    # ------------------------------------------------------------------ #

    def test_upload_success_returns_201(self, aws_mock, upload_event):
        from src.handlers.upload import handler
        response = handler(upload_event, None)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["message"] == "Image uploaded successfully."
        assert "image" in body
        assert body["image"]["user_id"] == "user-123"
        assert body["image"]["filename"] == "test.jpg"

    def test_upload_success_stores_metadata(self, aws_mock, upload_event):
        from src.handlers.upload import handler
        from src.services.dynamodb_service import DynamoDBService

        handler(upload_event, None)

        # Independently verify DynamoDB was written
        ddb = DynamoDBService()
        response = json.loads(handler(upload_event, None)["body"])
        image_id = response["image"]["image_id"]
        record = ddb.get_image_metadata(image_id)
        assert record is not None
        assert record.user_id == "user-123"

    def test_upload_success_stores_object_in_s3(self, aws_mock, upload_event):
        import boto3, os
        from src.handlers.upload import handler

        response = handler(upload_event, None)
        body = json.loads(response["body"])
        s3_key = body["image"]["image_id"]  # key contains image_id

        s3 = boto3.client("s3", region_name="us-east-1")
        objects = s3.list_objects_v2(Bucket="test-bucket")
        keys = [o["Key"] for o in objects.get("Contents", [])]
        assert any("user-123" in k for k in keys)

    def test_upload_with_tags(self, aws_mock):
        from src.handlers.upload import handler
        body = {
            "user_id": "u1", "filename": "a.jpg",
            "content_type": "image/jpeg",
            "image_data": TINY_JPEG_B64,
            "tags": ["sunset", "beach"],
        }
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 201
        assert json.loads(resp["body"])["image"]["tags"] == ["sunset", "beach"]

    def test_upload_with_comma_separated_tags_string(self, aws_mock):
        from src.handlers.upload import handler
        body = {
            "user_id": "u1", "filename": "a.jpg",
            "content_type": "image/jpeg",
            "image_data": TINY_JPEG_B64,
            "tags": "food,travel,2024",
        }
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 201
        tags = json.loads(resp["body"])["image"]["tags"]
        assert "food" in tags and "travel" in tags

    def test_upload_png_content_type(self, aws_mock):
        from src.handlers.upload import handler
        body = {
            "user_id": "u1", "filename": "img.png",
            "content_type": "image/png",
            "image_data": TINY_JPEG_B64,   # bytes type doesn't matter for this test
        }
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 201

    # ------------------------------------------------------------------ #
    #  Validation failures — 400
    # ------------------------------------------------------------------ #

    def test_upload_missing_user_id_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        body = {"filename": "a.jpg", "content_type": "image/jpeg", "image_data": TINY_JPEG_B64}
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 400
        assert "user_id" in json.loads(resp["body"])["error"]

    def test_upload_missing_filename_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        body = {"user_id": "u1", "content_type": "image/jpeg", "image_data": TINY_JPEG_B64}
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 400

    def test_upload_missing_image_data_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        body = {"user_id": "u1", "filename": "a.jpg", "content_type": "image/jpeg"}
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 400

    def test_upload_invalid_content_type_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        body = {
            "user_id": "u1", "filename": "a.pdf",
            "content_type": "application/pdf",
            "image_data": TINY_JPEG_B64,
        }
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 400
        assert "Unsupported content_type" in json.loads(resp["body"])["error"]

    def test_upload_invalid_base64_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        body = {
            "user_id": "u1", "filename": "a.jpg",
            "content_type": "image/jpeg",
            "image_data": "THIS IS NOT BASE64!!!",
        }
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 400
        assert "base64" in json.loads(resp["body"])["error"].lower()

    def test_upload_invalid_json_body_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        resp = handler({"body": "not-json-at-all"}, None)
        assert resp["statusCode"] == 400

    def test_upload_empty_body_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        resp = handler({"body": None}, None)
        assert resp["statusCode"] == 400

    def test_upload_oversized_image_returns_400(self, aws_mock):
        from src.handlers.upload import handler
        big_data = base64.b64encode(b"x" * (11 * 1024 * 1024)).decode()
        body = {
            "user_id": "u1", "filename": "big.jpg",
            "content_type": "image/jpeg",
            "image_data": big_data,
        }
        resp = handler({"body": json.dumps(body)}, None)
        assert resp["statusCode"] == 400
        assert "size" in json.loads(resp["body"])["error"].lower()

    # ------------------------------------------------------------------ #
    #  Response shape
    # ------------------------------------------------------------------ #

    def test_upload_response_contains_expected_fields(self, aws_mock, upload_event):
        from src.handlers.upload import handler
        body = json.loads(handler(upload_event, None)["body"])
        image = body["image"]
        for field in ("image_id", "user_id", "filename", "content_type",
                      "size_bytes", "tags", "uploaded_at"):
            assert field in image, f"Missing field: {field}"

    def test_upload_response_size_bytes_is_accurate(self, aws_mock, upload_event):
        from src.handlers.upload import handler
        from tests.conftest import TINY_JPEG_BYTES
        body = json.loads(handler(upload_event, None)["body"])
        assert body["image"]["size_bytes"] == len(TINY_JPEG_BYTES)
