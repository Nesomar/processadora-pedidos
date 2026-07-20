"""Fábrica única de clients boto3 contra o Ministack (evita duplicar credenciais/endpoint)."""

import os

import boto3


def build_client(service: str):
    return boto3.client(
        service,
        endpoint_url=os.environ["AWS_ENDPOINT_URL"],
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )
