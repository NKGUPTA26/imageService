# Image Service

A production-grade serverless image storage API built on AWS Lambda, API Gateway, S3, and DynamoDB — with a full LocalStack local development environment.

## Quick Start

```bash
# 1. Clone and enter the repo
cd image-service

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start LocalStack (creates S3 bucket + DynamoDB table automatically)
docker-compose up -d

# 4. Deploy Lambda functions + API Gateway to LocalStack
chmod +x scripts/deploy.sh && ./scripts/deploy.sh

# 5. Export the printed Base URL
export BASE_URL="http://localhost:4566/restapis/<api_id>/dev/_user_request_"

# 6. Upload your first image
IMAGE_B64=$(base64 -i /path/to/photo.jpg)
curl -X POST "$BASE_URL/images" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"u1\",\"filename\":\"photo.jpg\",\"content_type\":\"image/jpeg\",\"image_data\":\"$IMAGE_B64\",\"tags\":[\"test\"]}"
```

## Run Tests

```bash
pytest          # 68 tests, no AWS credentials needed (uses moto)
```

## Project Structure

```
image-service/
├── docker-compose.yml          # LocalStack
├── requirements.txt
├── pytest.ini
├── scripts/
│   ├── init-localstack.sh      # S3 bucket + DynamoDB table bootstrap
│   └── deploy.sh               # Lambda + API Gateway deployment
├── src/
│   ├── config.py               # Env-var configuration
│   ├── handlers/
│   │   ├── upload.py           # POST /images
│   │   ├── list_images.py      # GET  /images
│   │   ├── get_image.py        # GET  /images/{id}
│   │   └── delete_image.py     # DELETE /images/{id}
│   ├── models/
│   │   └── image_metadata.py   # Data model + DynamoDB serialization
│   ├── services/
│   │   ├── s3_service.py       # All S3 operations
│   │   └── dynamodb_service.py # All DynamoDB operations + GSI queries
│   └── utils/
│       ├── aws_clients.py      # Boto3 client factory (LocalStack-aware)
│       ├── response.py         # HTTP response helpers
│       └── validators.py       # Input validation
├── tests/
│   ├── conftest.py             # moto fixtures + shared helpers
│   ├── test_upload.py          # 14 tests
│   ├── test_list_images.py     # 16 tests
│   ├── test_get_image.py       # 11 tests
│   ├── test_delete_image.py    # 10 tests
│   └── test_services.py        # 17 tests
└── docs/
    └── API.md                  # Full API reference
```

## API Endpoints

| Method   | Path                  | Description                          |
|----------|-----------------------|--------------------------------------|
| `POST`   | `/images`             | Upload image + metadata              |
| `GET`    | `/images`             | List images (filter: user_id, tag)   |
| `GET`    | `/images/{image_id}`  | Get metadata + presigned download URL|
| `DELETE` | `/images/{image_id}`  | Delete image from S3 + DynamoDB      |

See [`docs/API.md`](docs/API.md) for full reference including request/response schemas.
