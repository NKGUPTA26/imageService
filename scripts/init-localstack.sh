#!/bin/bash
# init-localstack.sh — runs inside LocalStack container on startup

set -e

echo "==> Initializing LocalStack resources..."

AWS_ENDPOINT="http://localhost:4566"
REGION="us-east-1"
BUCKET_NAME="image-service-bucket"
TABLE_NAME="image-metadata"

# ---------- S3 ----------
echo "--> Creating S3 bucket: $BUCKET_NAME"
awslocal s3 mb s3://$BUCKET_NAME --region $REGION

# Enable versioning (good practice for image storage)
awslocal s3api put-bucket-versioning \
  --bucket $BUCKET_NAME \
  --versioning-configuration Status=Enabled

# CORS so a browser client could call presigned URLs directly
awslocal s3api put-bucket-cors \
  --bucket $BUCKET_NAME \
  --cors-configuration '{
    "CORSRules": [{
      "AllowedOrigins": ["*"],
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "MaxAgeSeconds": 3000
    }]
  }'

# ---------- DynamoDB ----------
echo "--> Creating DynamoDB table: $TABLE_NAME"
awslocal dynamodb create-table \
  --table-name $TABLE_NAME \
  --attribute-definitions \
      AttributeName=image_id,AttributeType=S \
      AttributeName=user_id,AttributeType=S \
      AttributeName=uploaded_at,AttributeType=S \
      AttributeName=tag,AttributeType=S \
  --key-schema \
      AttributeName=image_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --global-secondary-indexes \
    '[
      {
        "IndexName": "user_id-uploaded_at-index",
        "KeySchema": [
          {"AttributeName": "user_id", "KeyType": "HASH"},
          {"AttributeName": "uploaded_at", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
      },
      {
        "IndexName": "tag-uploaded_at-index",
        "KeySchema": [
          {"AttributeName": "tag", "KeyType": "HASH"},
          {"AttributeName": "uploaded_at", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
      }
    ]' \
  --region $REGION

echo "==> LocalStack initialization complete."
