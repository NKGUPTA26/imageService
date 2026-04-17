# Image Service API — Documentation

A serverless image storage service built on **AWS Lambda + API Gateway + S3 + DynamoDB**,
developed with a LocalStack local development environment.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Data Model](#data-model)
3. [Setup & Running Locally](#setup--running-locally)
4. [Running Tests](#running-tests)
5. [API Reference](#api-reference)
   - [Upload Image](#1-upload-image)
   - [List Images](#2-list-images)
   - [View / Download Image](#3-view--download-image)
   - [Delete Image](#4-delete-image)
6. [Error Reference](#error-reference)
7. [Design Decisions](#design-decisions)

---

## Architecture

```
Client
  │
  ▼
API Gateway  ──▶  Lambda (upload)     ──▶  S3 (image bytes)
             ──▶  Lambda (list)       ──▶  DynamoDB (metadata)
             ──▶  Lambda (get)        ──▶  S3 + DynamoDB
             ──▶  Lambda (delete)     ──▶  S3 + DynamoDB
```

### DynamoDB Table: `image-metadata`

| Key type | Attribute    | Notes                        |
|----------|--------------|------------------------------|
| PK (HASH)| `image_id`   | UUID v4                      |
| GSI-1    | `user_id` (HASH) + `uploaded_at` (RANGE) | Filter by owner |
| GSI-2    | `tag` (HASH) + `uploaded_at` (RANGE)     | Filter by tag   |

Both GSIs sort by `uploaded_at` (ISO-8601) so results arrive newest-first.

### S3 Bucket: `image-service-bucket`

Objects are stored at:  `images/{user_id}/{image_id}/{filename}`

Server-side encryption (AES-256) is applied on every PUT.

---

## Data Model

### Image Record

```json
{
  "image_id":     "550e8400-e29b-41d4-a716-446655440000",
  "user_id":      "user-123",
  "filename":     "sunset.jpg",
  "content_type": "image/jpeg",
  "size_bytes":   204800,
  "description":  "Golden hour at Coorg",
  "tags":         ["nature", "travel"],
  "uploaded_at":  "2024-04-16T10:30:00+00:00"
}
```

---

## Setup & Running Locally

### Prerequisites

- Docker & Docker Compose
- Python 3.7+
- AWS CLI (`pip install awscli`)
- `awslocal` wrapper (`pip install awscli-local`)

### 1. Start LocalStack

```bash
docker-compose up -d
# Wait ~15 seconds for init script to create S3 + DynamoDB
docker-compose logs localstack | grep "initialization complete"
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Deploy Lambda functions & API Gateway

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
# Note the Base URL printed at the end — you'll need it for API calls.
```

### Environment variables

| Variable            | Default                    | Description                          |
|---------------------|----------------------------|--------------------------------------|
| `AWS_ENDPOINT_URL`  | `http://localhost:4566`    | Override for LocalStack              |
| `S3_BUCKET`         | `image-service-bucket`     | S3 bucket name                       |
| `DYNAMODB_TABLE`    | `image-metadata`           | DynamoDB table name                  |
| `REGION`            | `us-east-1`                | AWS region                           |
| `PRESIGNED_URL_EXPIRY` | `3600`                  | Presigned URL TTL in seconds         |
| `MAX_UPLOAD_SIZE`   | `10485760` (10 MB)         | Maximum image upload size in bytes   |

---

## Running Tests

Tests use **moto** to mock AWS — no LocalStack or real AWS needed.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run a specific test file
pytest tests/test_upload.py -v

# Run a single test
pytest tests/test_upload.py::TestUploadHandler::test_upload_success_returns_201 -v
```

**Test suite summary:** 68 tests across 4 handler test files + 1 service test file.

---

## API Reference

### Base URL (LocalStack)

```
http://localhost:4566/restapis/{api_id}/dev/_user_request_
```

The `{api_id}` is printed by `deploy.sh`. Export it for convenience:

```bash
export BASE_URL="http://localhost:4566/restapis/REPLACE_ME/dev/_user_request_"
```

---

### 1. Upload Image

Upload an image with metadata. The image must be **base64-encoded**.

```
POST /images
Content-Type: application/json
```

#### Request Body

| Field          | Type            | Required | Description                                        |
|----------------|-----------------|----------|----------------------------------------------------|
| `user_id`      | string          | ✅       | Owner of the image                                 |
| `filename`     | string          | ✅       | Original filename (e.g. `sunset.jpg`)              |
| `content_type` | string          | ✅       | MIME type: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/bmp` |
| `image_data`   | string (base64) | ✅       | Base64-encoded image bytes                         |
| `description`  | string          | ❌       | Free-text description                              |
| `tags`         | array or string | ❌       | Tag list e.g. `["nature","travel"]` or `"nature,travel"` |

#### Example Request

```bash
IMAGE_B64=$(base64 -i ~/photo.jpg)

curl -s -X POST "$BASE_URL/images" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\":      \"user-123\",
    \"filename\":     \"photo.jpg\",
    \"content_type\": \"image/jpeg\",
    \"image_data\":   \"$IMAGE_B64\",
    \"description\":  \"Golden hour at Coorg\",
    \"tags\":         [\"nature\", \"travel\"]
  }" | jq .
```

#### Success Response — `201 Created`

```json
{
  "message": "Image uploaded successfully.",
  "image": {
    "image_id":     "550e8400-e29b-41d4-a716-446655440000",
    "user_id":      "user-123",
    "filename":     "photo.jpg",
    "content_type": "image/jpeg",
    "size_bytes":   204800,
    "description":  "Golden hour at Coorg",
    "tags":         ["nature", "travel"],
    "uploaded_at":  "2024-04-16T10:30:00+00:00"
  }
}
```

#### Error Responses

| Code | Reason                                          |
|------|-------------------------------------------------|
| 400  | Missing required fields                         |
| 400  | Unsupported `content_type`                      |
| 400  | `image_data` is not valid base64                |
| 400  | Image exceeds 10 MB size limit                  |
| 500  | Internal server error                           |

---

### 2. List Images

Retrieve a paginated list of images. Supports **two independent filters**
that can also be **combined**.

```
GET /images
```

#### Query Parameters

| Parameter | Type    | Description                                          |
|-----------|---------|------------------------------------------------------|
| `user_id` | string  | **Filter 1** — return only images owned by this user |
| `tag`     | string  | **Filter 2** — return only images with this tag      |
| `limit`   | integer | Records per page (default: 20, max: 100)             |
| `cursor`  | string  | Pagination token from previous response's `next_cursor` |

#### Example Requests

```bash
# All images (no filter)
curl -s "$BASE_URL/images" | jq .

# Filter by user
curl -s "$BASE_URL/images?user_id=user-123" | jq .

# Filter by tag
curl -s "$BASE_URL/images?tag=nature" | jq .

# Combined filter (AND logic)
curl -s "$BASE_URL/images?user_id=user-123&tag=nature" | jq .

# Paginated
curl -s "$BASE_URL/images?user_id=user-123&limit=5" | jq .
# Use next_cursor value from above to fetch the next page:
curl -s "$BASE_URL/images?user_id=user-123&limit=5&cursor=CURSOR_TOKEN" | jq .
```

#### Success Response — `200 OK`

```json
{
  "count":  2,
  "images": [
    {
      "image_id":     "550e8400-...",
      "user_id":      "user-123",
      "filename":     "photo.jpg",
      "content_type": "image/jpeg",
      "size_bytes":   204800,
      "description":  "Golden hour",
      "tags":         ["nature"],
      "uploaded_at":  "2024-04-16T10:30:00+00:00"
    }
  ],
  "next_cursor": "eyJpbWFnZV9pZCI6ICI1NTBlODQwMC4uLiJ9",
  "filters": {
    "user_id": "user-123",
    "tag":     null
  }
}
```

> `next_cursor` is `null` when there are no more pages.

#### Error Responses

| Code | Reason                         |
|------|--------------------------------|
| 400  | `limit` is not a valid integer |
| 400  | `cursor` token is invalid      |
| 500  | Internal server error          |

---

### 3. View / Download Image

Retrieve image metadata and a time-limited download URL, or download the
raw image bytes directly.

```
GET /images/{image_id}
GET /images/{image_id}?download=true
```

#### Path Parameters

| Parameter  | Description         |
|------------|---------------------|
| `image_id` | UUID of the image   |

#### Query Parameters

| Parameter  | Type    | Description                                                                   |
|------------|---------|-------------------------------------------------------------------------------|
| `download` | boolean | `true` → return raw image bytes (base64 in Lambda proxy). Default: `false`   |

#### Example Requests

```bash
IMAGE_ID="550e8400-e29b-41d4-a716-446655440000"

# Get metadata + presigned URL (default)
curl -s "$BASE_URL/images/$IMAGE_ID" | jq .

# Download raw bytes directly
curl -s "$BASE_URL/images/$IMAGE_ID?download=true" \
  --output downloaded_photo.jpg
```

#### Success Response — `200 OK` (default, presigned URL)

```json
{
  "image": {
    "image_id":     "550e8400-...",
    "user_id":      "user-123",
    "filename":     "photo.jpg",
    "content_type": "image/jpeg",
    "size_bytes":   204800,
    "description":  "Golden hour",
    "tags":         ["nature"],
    "uploaded_at":  "2024-04-16T10:30:00+00:00"
  },
  "download_url": "https://image-service-bucket.s3.amazonaws.com/images/user-123/550e8400-.../photo.jpg?X-Amz-Signature=...",
  "expires_in":   3600
}
```

#### Success Response — `200 OK` (`?download=true`)

```
HTTP/1.1 200 OK
Content-Type: image/jpeg
Content-Disposition: attachment; filename="photo.jpg"

<binary image data>
```

#### Error Responses

| Code | Reason                        |
|------|-------------------------------|
| 400  | Missing or blank `image_id`   |
| 404  | Image not found               |
| 500  | Internal server error         |

---

### 4. Delete Image

Permanently delete an image from both S3 and DynamoDB.

```
DELETE /images/{image_id}
```

#### Path Parameters

| Parameter  | Description        |
|------------|--------------------|
| `image_id` | UUID of the image  |

#### Example Request

```bash
IMAGE_ID="550e8400-e29b-41d4-a716-446655440000"

curl -s -X DELETE "$BASE_URL/images/$IMAGE_ID" | jq .
```

#### Success Response — `200 OK`

```json
{
  "message":  "Image deleted successfully.",
  "image_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Partial Failure Response — `207 Multi-Status`

Returned when one of the two delete operations fails (rare; the other
operation is still attempted so state is as clean as possible).

```json
{
  "message":  "Partial deletion — some resources could not be cleaned up.",
  "errors":   ["S3 delete failed: ..."],
  "image_id": "550e8400-..."
}
```

#### Error Responses

| Code | Reason                        |
|------|-------------------------------|
| 400  | Missing or blank `image_id`   |
| 404  | Image not found               |
| 207  | Partial failure               |
| 500  | Internal server error         |

---

## Error Reference

All error responses follow this shape:

```json
{
  "error":   "Human-readable message",
  "details": "Optional technical detail"
}
```

| HTTP Code | Meaning                                  |
|-----------|------------------------------------------|
| 400       | Bad Request — invalid input              |
| 404       | Not Found — resource does not exist      |
| 207       | Multi-Status — partial success           |
| 500       | Internal Server Error — unexpected fault |

---

## Design Decisions

### Why presigned URLs for downloads?
Returning a presigned S3 URL instead of streaming bytes through Lambda/API Gateway:
- **Cost**: avoids Lambda egress charges for large images.
- **Scalability**: S3 serves the download directly, no Lambda invocation.
- **Flexibility**: clients can cache the URL for up to its TTL.

The `?download=true` escape hatch is provided for small images or clients
that cannot follow redirects.

### Why two GSIs?
DynamoDB does not support ad-hoc filtering efficiently. Two GSIs let us run
**O(result set)** queries instead of full-table scans for the two most common
access patterns (`user_id` and `tag`). Combining both filters queries the
`user_id` GSI then applies a `FilterExpression` on `tag` — cheaper than a
scan, correct for expected cardinality.

### Why cursor-based pagination over offset?
DynamoDB's `LastEvaluatedKey` is cursor-based by design. Offset pagination
(`LIMIT x OFFSET y`) would require scanning and discarding rows, which is
both slow and expensive at scale.

### Idempotent deletes
The delete handler fetches metadata first (404 guard), then deletes S3 and
DynamoDB independently so a failure in one leg doesn't block the other,
and the 207 response tells the caller exactly what succeeded.
