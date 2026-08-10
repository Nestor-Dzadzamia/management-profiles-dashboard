from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

from config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


@lru_cache
def get_s3_client() -> "S3Client":
    settings = get_settings()
    client: S3Client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    _ensure_bucket(client, settings.s3_bucket)
    return client


def _ensure_bucket(client: "S3Client", bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


class Storage:
    def __init__(self) -> None:
        self._client = get_s3_client()
        self._bucket = get_settings().s3_bucket

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def download(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return bytes(response["Body"].read())

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
