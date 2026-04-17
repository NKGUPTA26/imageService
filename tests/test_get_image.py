"""
tests/test_get_image.py — Tests for GET /images/{image_id}.
"""
import base64
import json
import pytest

from tests.conftest import TINY_JPEG_B64, TINY_JPEG_BYTES, make_apigw_event


def _upload(user_id="u1", tags=None):
    from src.handlers.upload import handler as upload_handler
    body = {
        "user_id": user_id,
        "filename": "photo.jpg",
        "content_type": "image/jpeg",
        "image_data": TINY_JPEG_B64,
        "tags": tags or ["test"],
    }
    resp = upload_handler({"body": json.dumps(body)}, None)
    return json.loads(resp["body"])["image"]["image_id"]


class TestGetImageHandler:

    # ------------------------------------------------------------------ #
    #  Happy path — presigned URL (default)
    # ------------------------------------------------------------------ #

    def test_get_image_returns_200(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload()
        resp = handler(make_apigw_event(path_params={"image_id": image_id}), None)
        assert resp["statusCode"] == 200

    def test_get_image_response_contains_metadata(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload(user_id="alice")
        body = json.loads(
            handler(make_apigw_event(path_params={"image_id": image_id}), None)["body"]
        )
        assert body["image"]["image_id"] == image_id
        assert body["image"]["user_id"] == "alice"
        assert body["image"]["filename"] == "photo.jpg"

    def test_get_image_response_contains_download_url(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload()
        body = json.loads(
            handler(make_apigw_event(path_params={"image_id": image_id}), None)["body"]
        )
        assert "download_url" in body
        assert body["download_url"].startswith("https://") or \
               body["download_url"].startswith("http://")

    def test_get_image_response_contains_expires_in(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload()
        body = json.loads(
            handler(make_apigw_event(path_params={"image_id": image_id}), None)["body"]
        )
        assert body["expires_in"] == 3600

    # ------------------------------------------------------------------ #
    #  Happy path — direct binary download
    # ------------------------------------------------------------------ #

    def test_get_image_download_true_returns_binary(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload()
        resp = handler(
            make_apigw_event(
                path_params={"image_id": image_id},
                query_params={"download": "true"},
            ),
            None,
        )
        assert resp["statusCode"] == 200
        assert resp.get("isBase64Encoded") is True
        assert resp["headers"]["Content-Type"] == "image/jpeg"
        assert "attachment" in resp["headers"]["Content-Disposition"]

    def test_get_image_download_binary_data_matches_original(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload()
        resp = handler(
            make_apigw_event(
                path_params={"image_id": image_id},
                query_params={"download": "true"},
            ),
            None,
        )
        returned_bytes = base64.b64decode(resp["body"])
        assert returned_bytes == TINY_JPEG_BYTES

    # ------------------------------------------------------------------ #
    #  Error cases
    # ------------------------------------------------------------------ #

    def test_get_image_not_found_returns_404(self, aws_mock):
        from src.handlers.get_image import handler
        resp = handler(
            make_apigw_event(path_params={"image_id": "non-existent-id"}), None
        )
        assert resp["statusCode"] == 404

    def test_get_image_missing_path_param_returns_400(self, aws_mock):
        from src.handlers.get_image import handler
        resp = handler(make_apigw_event(path_params={}), None)
        assert resp["statusCode"] == 400

    def test_get_image_empty_image_id_returns_400(self, aws_mock):
        from src.handlers.get_image import handler
        resp = handler(make_apigw_event(path_params={"image_id": "   "}), None)
        assert resp["statusCode"] == 400

    # ------------------------------------------------------------------ #
    #  Response shape
    # ------------------------------------------------------------------ #

    def test_get_image_metadata_has_all_fields(self, aws_mock):
        from src.handlers.get_image import handler
        image_id = _upload()
        body = json.loads(
            handler(make_apigw_event(path_params={"image_id": image_id}), None)["body"]
        )
        for field in ("image_id", "user_id", "filename", "content_type",
                      "size_bytes", "tags", "uploaded_at"):
            assert field in body["image"], f"Missing field: {field}"

    def test_get_image_download_url_contains_image_id(self, aws_mock):
        """Presigned URL should reference the correct S3 key (contains image_id)."""
        from src.handlers.get_image import handler
        image_id = _upload()
        body = json.loads(
            handler(make_apigw_event(path_params={"image_id": image_id}), None)["body"]
        )
        assert image_id in body["download_url"]
