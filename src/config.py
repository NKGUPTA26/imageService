"""
config.py — central configuration pulled from environment variables.
Defaults are wired for LocalStack so the service runs out-of-the-box locally.
"""
import os

# AWS / LocalStack
AWS_REGION        = os.getenv("REGION", "us-east-1")
AWS_ENDPOINT_URL  = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")  # None in real AWS
S3_BUCKET         = os.getenv("S3_BUCKET", "image-service-bucket")
DYNAMODB_TABLE    = os.getenv("DYNAMODB_TABLE", "image-metadata")

# Only override endpoint when running locally
IS_LOCAL = bool(AWS_ENDPOINT_URL)

# Presigned URL expiry (seconds)
PRESIGNED_URL_EXPIRY = int(os.getenv("PRESIGNED_URL_EXPIRY", "3600"))

# Allowed MIME types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
}

# Max upload size (bytes) — 10 MB
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)))
