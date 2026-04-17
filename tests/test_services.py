"""
tests/test_services.py — Unit tests for S3Service and DynamoDBService directly.

These tests validate the service layer in isolation from the HTTP handlers.
"""
import pytest
import boto3

from tests.conftest import TINY_JPEG_BYTES
from src.models.image_metadata import ImageMetadata
from src.services.s3_service import S3Service
from src.services.dynamodb_service import DynamoDBService


def _make_metadata(**kwargs):
    defaults = dict(
        user_id="svc-user",
        filename="svc_test.jpg",
        content_type="image/jpeg",
        s3_key="images/svc-user/abc/svc_test.jpg",
        size_bytes=len(TINY_JPEG_BYTES),
        tags=["svc"],
    )
    defaults.update(kwargs)
    return ImageMetadata(**defaults)


class TestS3Service:

    def test_upload_and_verify_object_exists(self, aws_mock):
        svc = S3Service()
        svc.upload_image("test/key.jpg", TINY_JPEG_BYTES, "image/jpeg", {})
        assert svc.object_exists("test/key.jpg") is True

    def test_object_does_not_exist_returns_false(self, aws_mock):
        svc = S3Service()
        assert svc.object_exists("does/not/exist.jpg") is False

    def test_upload_and_get_object_roundtrip(self, aws_mock):
        svc = S3Service()
        svc.upload_image("test/img.jpg", TINY_JPEG_BYTES, "image/jpeg", {})
        data, ct = svc.get_object("test/img.jpg")
        assert data == TINY_JPEG_BYTES
        assert ct == "image/jpeg"

    def test_delete_removes_object(self, aws_mock):
        svc = S3Service()
        svc.upload_image("test/del.jpg", TINY_JPEG_BYTES, "image/jpeg", {})
        svc.delete_object("test/del.jpg")
        assert svc.object_exists("test/del.jpg") is False

    def test_generate_presigned_url_returns_string(self, aws_mock):
        svc = S3Service()
        svc.upload_image("test/img.jpg", TINY_JPEG_BYTES, "image/jpeg", {})
        url = svc.generate_presigned_url("test/img.jpg")
        assert isinstance(url, str)
        assert len(url) > 20

    def test_upload_stores_metadata(self, aws_mock):
        svc = S3Service()
        svc.upload_image(
            "test/meta.jpg",
            TINY_JPEG_BYTES,
            "image/jpeg",
            {"image_id": "id-123", "user_id": "u1"},
        )
        s3 = boto3.client("s3", region_name="us-east-1")
        head = s3.head_object(Bucket="test-bucket", Key="test/meta.jpg")
        assert head["Metadata"]["image_id"] == "id-123"


class TestDynamoDBService:

    def test_put_and_get_roundtrip(self, aws_mock):
        svc  = DynamoDBService()
        meta = _make_metadata()
        svc.put_image_metadata(meta)
        fetched = svc.get_image_metadata(meta.image_id)
        assert fetched is not None
        assert fetched.image_id  == meta.image_id
        assert fetched.user_id   == meta.user_id
        assert fetched.filename  == meta.filename

    def test_get_nonexistent_returns_none(self, aws_mock):
        svc = DynamoDBService()
        assert svc.get_image_metadata("no-such-id") is None

    def test_delete_removes_record(self, aws_mock):
        svc  = DynamoDBService()
        meta = _make_metadata()
        svc.put_image_metadata(meta)
        svc.delete_image_metadata(meta.image_id)
        assert svc.get_image_metadata(meta.image_id) is None

    def test_list_all_returns_all_records(self, aws_mock):
        svc = DynamoDBService()
        for i in range(3):
            svc.put_image_metadata(_make_metadata(user_id=f"u{i}", s3_key=f"k{i}"))
        result = svc.list_images()
        assert len(result["items"]) == 3

    def test_list_filter_by_user_id(self, aws_mock):
        svc = DynamoDBService()
        svc.put_image_metadata(_make_metadata(user_id="alice", s3_key="k1"))
        svc.put_image_metadata(_make_metadata(user_id="alice", s3_key="k2"))
        svc.put_image_metadata(_make_metadata(user_id="bob",   s3_key="k3"))
        result = svc.list_images(user_id="alice")
        assert len(result["items"]) == 2
        assert all(i.user_id == "alice" for i in result["items"])

    def test_list_filter_by_tag(self, aws_mock):
        svc = DynamoDBService()
        svc.put_image_metadata(_make_metadata(s3_key="k1", tags=["sunset"]))
        svc.put_image_metadata(_make_metadata(s3_key="k2", tags=["sunset"]))
        svc.put_image_metadata(_make_metadata(s3_key="k3", tags=["food"]))
        result = svc.list_images(tag="sunset")
        assert len(result["items"]) == 2

    def test_list_pagination_limit(self, aws_mock):
        svc = DynamoDBService()
        for i in range(5):
            svc.put_image_metadata(_make_metadata(user_id="pg", s3_key=f"k{i}"))
        result = svc.list_images(user_id="pg", limit=2)
        assert len(result["items"]) == 2
        assert result["last_evaluated_key"] is not None

    def test_list_pagination_last_page_has_no_cursor(self, aws_mock):
        svc = DynamoDBService()
        for i in range(3):
            svc.put_image_metadata(_make_metadata(user_id="last", s3_key=f"k{i}"))
        result = svc.list_images(user_id="last", limit=10)
        assert result["last_evaluated_key"] is None

    def test_metadata_tags_persisted(self, aws_mock):
        svc  = DynamoDBService()
        meta = _make_metadata(tags=["a", "b", "c"])
        svc.put_image_metadata(meta)
        fetched = svc.get_image_metadata(meta.image_id)
        assert set(fetched.tags) == {"a", "b", "c"}

    def test_metadata_description_persisted(self, aws_mock):
        svc  = DynamoDBService()
        meta = _make_metadata(description="A rainy afternoon")
        svc.put_image_metadata(meta)
        fetched = svc.get_image_metadata(meta.image_id)
        assert fetched.description == "A rainy afternoon"
