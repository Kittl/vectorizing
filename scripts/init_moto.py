"""Create separate local application and test buckets if they do not exist."""

import os

import boto3

s3 = boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"])
existing = {bucket["Name"] for bucket in s3.list_buckets()["Buckets"]}

for name in (os.environ["S3_BUCKET"], os.environ["S3_TEST_BUCKET"]):
    if name not in existing:
        s3.create_bucket(
            Bucket=name,
            CreateBucketConfiguration={
                "LocationConstraint": os.environ["AWS_DEFAULT_REGION"],
            },
        )
