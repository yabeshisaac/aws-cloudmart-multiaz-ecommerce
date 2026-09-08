# CloudMart Application Source

This folder contains the sanitized application source used by the CloudMart AWS project.

## Structure

```text
app/
├── app.py
├── auth_utils.py
├── config.py
├── db.py
├── s3_utils.py
├── sqs_utils.py
├── worker.py
├── requirements.txt
├── templates/
└── static/

systemd/
├── ecommerce.service
└── ecommerce-worker.service

.env.example
.gitignore
```

## Application Components

- Flask storefront and cart
- Cognito sign-up, confirmation and login
- Admin authorization using Cognito groups
- Aurora MySQL data access through PyMySQL
- S3 presigned URLs for product images
- SQS order publishing
- Background SQS worker
- Gunicorn/systemd application service

## Configuration

The real runtime environment file is intentionally not included.

Copy `.env.example` to your private runtime environment file and supply your own values. Never commit real database passwords, Flask secret keys, AWS credentials, or other secrets.

Cognito configuration is loaded from AWS Systems Manager Parameter Store by `app/config.py`.

## Deployment Note

The included systemd units reflect the original EC2 deployment path:

```text
/opt/ecommerce-app
```

The application and worker were run as separate services:
- `ecommerce.service`
- `ecommerce-worker.service`

## Security

No real database password, Flask secret key, AWS access key, or secret access key is included in this GitHub-ready package.
