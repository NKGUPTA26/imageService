"""
tests/test_list_images.py — Tests for GET /images (list handler).
"""
import base64
import json
import pytest

from tests.conftest import TINY_JPEG_B64, make_apigw_event


def _upload(user_id="u1", tags=None, filename="img.jpg"):
    """Helper: upload a single image and return its image_id."""
    from src.handlers.upload import handler as upload_handler
    body = {
        "user_id": user_id,
        "filename": filename,
        "content_type": "image/jpeg",
        "image_data": TINY_JPEG_B64,
        "tags": tags or [],
    }
    resp = upload_handler({"body": json.dumps(body)}, None)
    return json.loads(resp["body"])["image"]["image_id"]


class TestListImagesHandler:

    # ------------------------------------------------------------------ #
    #  No-filter listing
    # ------------------------------------------------------------------ #

    def test_list_returns_200(self, aws_mock):
        from src.handlers.list_images import handler
        resp = handler(make_apigw_event(), None)
        assert resp["statusCode"] == 200

    def test_list_empty_when_no_images(self, aws_mock):
        from src.handlers.list_images import handler
        body = json.loads(handler(make_apigw_event(), None)["body"])
        assert body["count"] == 0
        assert body["images"] == []

    def test_list_returns_all_images_without_filter(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(user_id="u1")
        _upload(user_id="u2")
        _upload(user_id="u3")
        body = json.loads(handler(make_apigw_event(), None)["body"])
        assert body["count"] == 3

    # ------------------------------------------------------------------ #
    #  Filter 1: user_id
    # ------------------------------------------------------------------ #

    def test_filter_by_user_id(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(user_id="alice")
        _upload(user_id="alice")
        _upload(user_id="bob")
        body = json.loads(
            handler(make_apigw_event(query_params={"user_id": "alice"}), None)["body"]
        )
        assert body["count"] == 2
        assert all(img["user_id"] == "alice" for img in body["images"])

    def test_filter_by_user_id_returns_empty_for_unknown_user(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(user_id="alice")
        body = json.loads(
            handler(make_apigw_event(query_params={"user_id": "charlie"}), None)["body"]
        )
        assert body["count"] == 0

    # ------------------------------------------------------------------ #
    #  Filter 2: tag
    # ------------------------------------------------------------------ #

    def test_filter_by_tag(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(user_id="u1", tags=["nature"])
        _upload(user_id="u2", tags=["nature"])
        _upload(user_id="u3", tags=["food"])
        body = json.loads(
            handler(make_apigw_event(query_params={"tag": "nature"}), None)["body"]
        )
        assert body["count"] == 2

    def test_filter_by_tag_returns_empty_for_unknown_tag(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(tags=["nature"])
        body = json.loads(
            handler(make_apigw_event(query_params={"tag": "sports"}), None)["body"]
        )
        assert body["count"] == 0

    # ------------------------------------------------------------------ #
    #  Combined filters
    # ------------------------------------------------------------------ #

    def test_filter_by_user_id_and_tag_combined(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(user_id="alice", tags=["nature"])
        _upload(user_id="alice", tags=["food"])
        _upload(user_id="bob",   tags=["nature"])

        body = json.loads(
            handler(
                make_apigw_event(query_params={"user_id": "alice", "tag": "nature"}),
                None,
            )["body"]
        )
        assert body["count"] == 1
        assert body["images"][0]["user_id"] == "alice"

    # ------------------------------------------------------------------ #
    #  Pagination
    # ------------------------------------------------------------------ #

    def test_pagination_limit_respected(self, aws_mock):
        from src.handlers.list_images import handler
        for i in range(5):
            _upload(user_id="u1", filename=f"img{i}.jpg")

        body = json.loads(
            handler(make_apigw_event(query_params={"user_id": "u1", "limit": "2"}), None)["body"]
        )
        assert body["count"] == 2
        assert body["next_cursor"] is not None

    def test_pagination_cursor_advances_page(self, aws_mock):
        from src.handlers.list_images import handler
        for i in range(4):
            _upload(user_id="pager", filename=f"img{i}.jpg")

        first_page = json.loads(
            handler(make_apigw_event(query_params={"user_id": "pager", "limit": "2"}), None)["body"]
        )
        cursor = first_page["next_cursor"]
        assert cursor is not None

        second_page = json.loads(
            handler(
                make_apigw_event(query_params={"user_id": "pager", "limit": "2", "cursor": cursor}),
                None,
            )["body"]
        )
        assert second_page["count"] == 2
        # No overlap between pages
        first_ids  = {img["image_id"] for img in first_page["images"]}
        second_ids = {img["image_id"] for img in second_page["images"]}
        assert first_ids.isdisjoint(second_ids)

    def test_pagination_invalid_cursor_returns_400(self, aws_mock):
        from src.handlers.list_images import handler
        resp = handler(make_apigw_event(query_params={"cursor": "INVALID!!"}), None)
        assert resp["statusCode"] == 400

    def test_pagination_limit_exceeds_max_is_capped(self, aws_mock):
        from src.handlers.list_images import handler
        # Should not raise; just caps at MAX_LIMIT
        resp = handler(make_apigw_event(query_params={"limit": "9999"}), None)
        assert resp["statusCode"] == 200

    def test_pagination_invalid_limit_returns_400(self, aws_mock):
        from src.handlers.list_images import handler
        resp = handler(make_apigw_event(query_params={"limit": "abc"}), None)
        assert resp["statusCode"] == 400

    # ------------------------------------------------------------------ #
    #  Response shape
    # ------------------------------------------------------------------ #

    def test_response_contains_filters_echo(self, aws_mock):
        from src.handlers.list_images import handler
        body = json.loads(
            handler(make_apigw_event(query_params={"user_id": "u1", "tag": "x"}), None)["body"]
        )
        assert body["filters"]["user_id"] == "u1"
        assert body["filters"]["tag"] == "x"

    def test_image_items_have_required_fields(self, aws_mock):
        from src.handlers.list_images import handler
        _upload(user_id="u1")
        body = json.loads(
            handler(make_apigw_event(query_params={"user_id": "u1"}), None)["body"]
        )
        img = body["images"][0]
        for f in ("image_id", "user_id", "filename", "content_type", "size_bytes", "uploaded_at"):
            assert f in img
