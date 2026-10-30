import io
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_client():
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


def upload_file(file_bytes: bytes, s3_key: str, content_type: str = "application/octet-stream") -> bool:
    """Upload bytes to S3. Returns True on success."""
    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        logger.info("Uploaded %s to S3 (%d bytes)", s3_key, len(file_bytes))
        return True
    except ClientError as e:
        logger.error("S3 upload failed for %s: %s", s3_key, e)
        return False


def download_file(s3_key: str) -> Optional[bytes]:
    """Download a file from S3 and return its bytes."""
    client = _get_client()
    try:
        response = client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
        return response["Body"].read()
    except ClientError as e:
        logger.error("S3 download failed for %s: %s", s3_key, e)
        return None


def delete_file(s3_key: str) -> bool:
    """Delete a file from S3. Returns True on success."""
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)
        logger.info("Deleted %s from S3", s3_key)
        return True
    except ClientError as e:
        logger.error("S3 delete failed for %s: %s", s3_key, e)
        return False


def get_presigned_url(s3_key: str, expires: int = 3600) -> Optional[str]:
    """Generate a presigned URL for temporary download access."""
    client = _get_client()
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
            ExpiresIn=expires,
        )
        return url
    except ClientError as e:
        logger.error("Failed to generate presigned URL for %s: %s", s3_key, e)
        return None
