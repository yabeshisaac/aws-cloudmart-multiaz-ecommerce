import os
import boto3

_ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "ap-south-2"))


def _get_ssm_param(name, default="", decrypt=False):
    try:
        resp = _ssm.get_parameter(Name=name, WithDecryption=decrypt)
        return resp["Parameter"]["Value"]
    except Exception:
        return default


class Config:
    # --- Aurora / RDS ---
    DB_HOST = os.environ.get("DB_HOST", "")          # Aurora WRITER endpoint
    DB_USER = os.environ.get("DB_USER", "admin")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "ecommerce")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))

    # --- S3 (product images) ---
    S3_BUCKET = os.environ.get("S3_BUCKET", "")
    AWS_REGION = os.environ.get("AWS_REGION", "ap-south-2")

    # --- SQS (async order processing) ---
    SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")

    # --- Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # --- Cognito (auth) — pulled from SSM Parameter Store ---
    COGNITO_USER_POOL_ID = _get_ssm_param("/ecommerce/COGNITO_USER_POOL_ID")
    COGNITO_CLIENT_ID = _get_ssm_param("/ecommerce/COGNITO_CLIENT_ID")
    COGNITO_CLIENT_SECRET = _get_ssm_param(
        "/ecommerce/COGNITO_CLIENT_SECRET", decrypt=True
    )
