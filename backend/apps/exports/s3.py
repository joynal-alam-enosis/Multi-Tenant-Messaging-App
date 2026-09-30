"""
S3 client helper for conversation exports.

Uses MiniStack locally (AWS_ENDPOINT_URL=http://ministack:4566)
or real AWS S3 in production.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)

# Default bucket name for exports
DEFAULT_EXPORT_BUCKET = "messaging-exports"


def get_s3_client():
    """
    Returns a boto3 S3 client configured for MiniStack or real AWS.
    
    Uses environment variables:
    - AWS_ENDPOINT_URL: MiniStack endpoint (e.g., http://ministack:4566)
    - AWS_REGION: AWS region (default: us-east-1)
    - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY: Credentials
    """
    kwargs = {
        "service_name": "s3",
        "region_name": getattr(settings, "AWS_REGION", os.environ.get("AWS_REGION", "us-east-1")),
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    }
    
    endpoint = getattr(settings, "AWS_ENDPOINT_URL", None) or os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        # MiniStack requires path-style addressing
        kwargs["config"] = Config(s3={"addressing_style": "path"})
    
    return boto3.client(**kwargs)


def get_export_bucket_name() -> str:
    """Returns the export bucket name from settings or environment."""
    return getattr(
        settings,
        "EXPORT_S3_BUCKET",
        os.environ.get("EXPORT_S3_BUCKET", DEFAULT_EXPORT_BUCKET)
    )


def ensure_bucket_exists(bucket_name: Optional[str] = None) -> str:
    """
    Idempotently ensure the exports bucket exists.
    
    Args:
        bucket_name: Optional bucket name override
        
    Returns:
        The bucket name that was ensured
        
    Raises:
        ClientError: If bucket creation fails for reasons other than "already exists"
    """
    bucket = bucket_name or get_export_bucket_name()
    client = get_s3_client()
    
    try:
        client.head_bucket(Bucket=bucket)
        logger.debug("Export bucket already exists: %s", bucket)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket", "NotFound"):
            logger.info("Creating export bucket: %s", bucket)
            client.create_bucket(Bucket=bucket)
        else:
            logger.error("Failed to check/create bucket %s: %s", bucket, e)
            raise
    
    return bucket


def upload_export(bucket: str, key: str, data: bytes, content_type: str = "application/json") -> str:
    """
    Upload export data to S3.
    
    Args:
        bucket: S3 bucket name
        key: Object key (path within bucket)
        data: JSON bytes to upload
        content_type: MIME type
        
    Returns:
        ETag of the uploaded object (without quotes)
    """
    client = get_s3_client()
    response = client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    etag = response.get("ETag", "").strip('"')
    logger.info("Uploaded export to s3://%s/%s (ETag: %s)", bucket, key, etag)
    return etag


def generate_presigned_download_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for downloading an export.
    
    Args:
        bucket: S3 bucket name
        key: Object key
        expires_in: URL expiry in seconds (default: 1 hour)
        
    Returns:
        Presigned URL string
    """
    client = get_s3_client()
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
    logger.debug("Generated presigned URL for s3://%s/%s (expires in %ss)", bucket, key, expires_in)
    return url


def delete_export(bucket: str, key: str) -> bool:
    """
    Delete an export from S3.
    
    Args:
        bucket: S3 bucket name
        key: Object key
        
    Returns:
        True if deleted, False if not found
    """
    client = get_s3_client()
    try:
        client.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted export s3://%s/%s", bucket, key)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "NoSuchKey":
            return False
        raise