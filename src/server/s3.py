import cuid
import boto3

S3 = boto3.client("s3")

def upload_markup (markup, bucket):
    cuid_str = cuid.cuid()
    
    S3.put_object(
        Body = markup.encode('utf-8'),
        Bucket = bucket,
        Key = cuid_str,
        ContentType = "image/svg+xml",
    )

    return cuid_str