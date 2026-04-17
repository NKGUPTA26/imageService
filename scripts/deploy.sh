#!/bin/bash
# deploy.sh — packages Lambda functions and wires up API Gateway on LocalStack

set -e

ENDPOINT="http://localhost:4566"
REGION="us-east-1"
ACCOUNT_ID="000000000000"   # LocalStack dummy account
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/lambda-role"
RUNTIME="python3.11"

echo "==> Building Lambda deployment package..."
rm -rf /tmp/lambda_pkg && mkdir /tmp/lambda_pkg
cp -r src/* /tmp/lambda_pkg/
pip install -r requirements.txt -t /tmp/lambda_pkg/ -q
cd /tmp/lambda_pkg && zip -r /tmp/lambda.zip . -q
cd -
echo "    Package ready: /tmp/lambda.zip ($(du -sh /tmp/lambda.zip | cut -f1))"

create_or_update_lambda() {
  local NAME=$1
  local HANDLER=$2

  if awslocal lambda get-function --function-name "$NAME" --region $REGION &>/dev/null 2>&1; then
    echo "--> Updating Lambda: $NAME"
    awslocal lambda update-function-code \
      --function-name "$NAME" \
      --zip-file fileb:///tmp/lambda.zip \
      --region $REGION > /dev/null
  else
    echo "--> Creating Lambda: $NAME"
    awslocal lambda create-function \
      --function-name "$NAME" \
      --runtime $RUNTIME \
      --handler "$HANDLER" \
      --role "$ROLE_ARN" \
      --zip-file fileb:///tmp/lambda.zip \
      --environment "Variables={
        DYNAMODB_TABLE=image-metadata,
        S3_BUCKET=image-service-bucket,
        AWS_ENDPOINT_URL=http://localstack:4566,
        REGION=us-east-1
      }" \
      --timeout 30 \
      --memory-size 256 \
      --region $REGION > /dev/null
  fi
}

# ---------- Create IAM role (LocalStack accepts any ARN) ----------
awslocal iam create-role \
  --role-name lambda-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --region $REGION > /dev/null 2>&1 || true

# ---------- Deploy Lambda functions ----------
create_or_update_lambda "upload-image"    "handlers.upload.handler"
create_or_update_lambda "list-images"     "handlers.list_images.handler"
create_or_update_lambda "get-image"       "handlers.get_image.handler"
create_or_update_lambda "delete-image"    "handlers.delete_image.handler"

# ---------- API Gateway ----------
echo "==> Setting up API Gateway..."
API_ID=$(awslocal apigateway create-rest-api \
  --name "image-service-api" \
  --region $REGION \
  --query 'id' --output text 2>/dev/null || \
  awslocal apigateway get-rest-apis \
    --query "items[?name=='image-service-api'].id | [0]" \
    --output text --region $REGION)

ROOT_ID=$(awslocal apigateway get-resources \
  --rest-api-id $API_ID --region $REGION \
  --query 'items[?path==`/`].id | [0]' --output text)

create_resource_and_method() {
  local PATH_PART=$1
  local HTTP_METHOD=$2
  local LAMBDA_NAME=$3
  local PARENT_ID=${4:-$ROOT_ID}

  RESOURCE_ID=$(awslocal apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $PARENT_ID \
    --path-part "$PATH_PART" \
    --region $REGION \
    --query 'id' --output text)

  awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method $HTTP_METHOD \
    --authorization-type NONE \
    --region $REGION > /dev/null

  LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${LAMBDA_NAME}"
  awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method $HTTP_METHOD \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" \
    --region $REGION > /dev/null

  echo "$RESOURCE_ID"
}

IMAGES_ID=$(create_resource_and_method "images" "POST" "upload-image")
create_resource_and_method "images" "GET"  "list-images"  $ROOT_ID > /dev/null

IMAGE_RESOURCE_ID=$(awslocal apigateway create-resource \
  --rest-api-id $API_ID --parent-id $ROOT_ID \
  --path-part "images" --region $REGION \
  --query 'id' --output text 2>/dev/null || echo $IMAGES_ID)

ITEM_RESOURCE_ID=$(awslocal apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $IMAGE_RESOURCE_ID \
  --path-part "{image_id}" \
  --region $REGION \
  --query 'id' --output text)

for METHOD in GET DELETE; do
  LAMBDA=$( [ "$METHOD" = "GET" ] && echo "get-image" || echo "delete-image" )
  awslocal apigateway put-method \
    --rest-api-id $API_ID --resource-id $ITEM_RESOURCE_ID \
    --http-method $METHOD --authorization-type NONE --region $REGION > /dev/null
  awslocal apigateway put-integration \
    --rest-api-id $API_ID --resource-id $ITEM_RESOURCE_ID \
    --http-method $METHOD --type AWS_PROXY --integration-http-method POST \
    --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${LAMBDA}/invocations" \
    --region $REGION > /dev/null
done

awslocal apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name dev \
  --region $REGION > /dev/null

echo ""
echo "======================================================"
echo "  Deployment complete!"
echo "  Base URL: ${ENDPOINT}/restapis/${API_ID}/dev/_user_request_"
echo "  POST   /images            — upload image"
echo "  GET    /images            — list images (filters: user_id, tag)"
echo "  GET    /images/{image_id} — view/download image"
echo "  DELETE /images/{image_id} — delete image"
echo "======================================================"
