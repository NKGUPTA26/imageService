"""
utils/aws_clients.py — Boto3 client/resource factory.

Using module-level singletons keeps Lambda warm-start performance good.
The endpoint_url kwarg is set only when AWS_ENDPOINT_URL is present so the
same code works against real AWS without modification.
"""
import boto3
from src.config import AWS_REGION, AWS_ENDPOINT_URL

_kwargs = {"region_name": AWS_REGION}
if AWS_ENDPOINT_URL:
    _kwargs["endpoint_url"] = AWS_ENDPOINT_URL


def get_s3_client():
    return boto3.client("s3", **_kwargs)


def get_dynamodb_resource():
    return boto3.resource("dynamodb", **_kwargs)


def get_dynamodb_client():
    return boto3.client("dynamodb", **_kwargs)
