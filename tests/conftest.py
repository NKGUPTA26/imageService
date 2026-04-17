"""
tests/conftest.py — Shared pytest fixtures using moto for AWS mocking.

moto intercepts all boto3 calls so tests never hit real AWS or LocalStack.
"""
import base64
import os
import pytest
import boto3

# ── Point boto3 at moto's virtual AWS before any import touches real AWS ──
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
# Override endpoint so aws_clients.py does NOT inject localhost:4566
os.environ["AWS_ENDPOINT_URL"] = ""
os.environ["S3_BUCKET"]        = "test-bucket"
os.environ["DYNAMODB_TABLE"]   = "test-image-metadata"
os.environ["REGION"]           = "us-east-1"

from moto import mock_aws   # noqa: E402  (must come after env setup)


BUCKET     = "test-bucket"
TABLE_NAME = "test-image-metadata"
REGION     = "us-east-1"

# ── Minimal 1×1 pixel valid JPEG ──────────────────────────────────────────
TINY_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
    b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xff\xd9"
)
TINY_JPEG_B64 = base64.b64encode(TINY_JPEG_BYTES).decode()


@pytest.fixture(scope="function")
def aws_mock():
    """Start moto mock for S3 + DynamoDB for the duration of each test."""
    with mock_aws():
        # ── S3 ──────────────────────────────────────────────────────────
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET)

        # ── DynamoDB ────────────────────────────────────────────────────
        ddb = boto3.resource("dynamodb", region_name=REGION)
        ddb.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[
                {"AttributeName": "image_id",    "AttributeType": "S"},
                {"AttributeName": "user_id",     "AttributeType": "S"},
                {"AttributeName": "uploaded_at", "AttributeType": "S"},
                {"AttributeName": "tag",         "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "image_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-uploaded_at-index",
                    "KeySchema": [
                        {"AttributeName": "user_id",     "KeyType": "HASH"},
                        {"AttributeName": "uploaded_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "tag-uploaded_at-index",
                    "KeySchema": [
                        {"AttributeName": "tag",         "KeyType": "HASH"},
                        {"AttributeName": "uploaded_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        yield {"s3": s3, "ddb": ddb}


@pytest.fixture
def sample_upload_body():
    return {
        "user_id":      "user-123",
        "filename":     "test.jpg",
        "content_type": "image/jpeg",
        "image_data":   TINY_JPEG_B64,
        "description":  "A test image",
        "tags":         ["nature", "test"],
    }


@pytest.fixture
def upload_event(sample_upload_body):
    import json
    return {"body": json.dumps(sample_upload_body)}


def make_apigw_event(method="GET", path_params=None, query_params=None, body=None):
    import json
    return {
        "httpMethod": method,
        "pathParameters": path_params or {},
        "queryStringParameters": query_params or {},
        "body": json.dumps(body) if body else None,
    }
