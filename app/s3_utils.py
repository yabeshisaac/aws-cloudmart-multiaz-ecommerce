import boto3
from botocore.config import Config
from config import Config as AppConfig

REGION = "ap-south-2"

_s3 = boto3.client(
    "s3",
    region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
)

def get_presigned_url(key, expires=3600):
    if not key:
        return None
    return _s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": AppConfig.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )

def upload_file(local_path, key, content_type="image/png"):
    _s3.upload_file(
        local_path,
        AppConfig.S3_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
