"""Cliente fino sobre S3 (constitution VIII — wrapper síncrono, DI de Settings)."""

import boto3

from pedidos_shared.settings import Settings


class S3Client:
    def __init__(self, settings: Settings) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def put_object(
        self, bucket: str, key: str, body: bytes, content_type: str | None = None
    ) -> None:
        extra = {"ContentType": content_type} if content_type else {}
        self._client.put_object(Bucket=bucket, Key=key, Body=body, **extra)

    def get_object(self, bucket: str, key: str) -> bytes:
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
