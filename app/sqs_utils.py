import json
import boto3
from config import Config

_sqs = boto3.client("sqs", region_name=Config.AWS_REGION)


def send_order_message(order_id, total_amount, customer_email):
    if not Config.SQS_QUEUE_URL:
        return
    _sqs.send_message(
        QueueUrl=Config.SQS_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "order_id": order_id,
                "total_amount": str(total_amount),
                "customer_email": customer_email,
            }
        ),
    )
