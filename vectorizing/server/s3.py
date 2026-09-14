import os
from functools import lru_cache

import boto3
import cuid
from botocore.exceptions import ClientError


@lru_cache(maxsize=1)
def get_s3_client():
    endpoint_url = os.getenv("AWS_ENDPOINT_URL") or None
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"),
        endpoint_url=endpoint_url,
    )


def upload_markup(markup, s3_bucket_name):
    cuid_str = cuid.cuid()

    get_s3_client().put_object(
        Body=markup.encode("utf-8"),
        Bucket=s3_bucket_name,
        Key=cuid_str,
        ContentType="image/svg+xml",
    )

    return cuid_str


def get_object_url(s3_file_key, s3_bucket_name):
    s3 = get_s3_client()
    try:
        s3.head_object(
            Key=s3_file_key,
            Bucket=s3_bucket_name,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchKey", "NotFound"}:
            raise
        return None

    object_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": s3_bucket_name, "Key": s3_file_key},
    )
    return object_url if os.getenv("AWS_ENDPOINT_URL") else object_url.split("?")[0]


def upload_file(local_file_path, s3_bucket_name, s3_file_key):
    get_s3_client().upload_file(
        local_file_path,
        s3_bucket_name,
        s3_file_key,
    )
    return get_object_url(s3_file_key, s3_bucket_name)
