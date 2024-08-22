import cuid
import boto3

S3 = boto3.client("s3", region_name="eu-central-1")

def upload_markup (markup, s3_bucket_name):
    cuid_str = cuid.cuid()

    S3.put_object(
        Body = markup.encode('utf-8'),
        Bucket = s3_bucket_name,
        Key = cuid_str,
        ContentType = "image/svg+xml",
    )

    return cuid_str

def get_object_url(s3_file_key, s3_bucket_name):
    try:
        S3.get_object(
            Key=s3_file_key,
            Bucket=s3_bucket_name
        )

    except(Exception):
        return None

    return S3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": s3_bucket_name, "Key": s3_file_key},
    ).split("?")[0]

def upload_file(
    local_file_path,
    s3_bucket_name,
    s3_file_key,
):
    S3.upload_file(
        local_file_path,
        s3_bucket_name,
        s3_file_key,
    )
    return get_object_url(s3_file_key, s3_bucket_name)
