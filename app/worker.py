"""
Long-polls the SQS queue and 'processes' each order (marks it PROCESSING,
then SHIPPED). This demonstrates the decoupling pattern from the architecture
doc: checkout returns instantly to the user, this worker does the (simulated)
heavy lifting - e.g. sending confirmation emails, updating inventory, etc.

Run as a systemd service (ecommerce-worker.service) on at least one instance.
"""
import json
import time

import boto3

import db
from config import Config

sqs = boto3.client("sqs", region_name=Config.AWS_REGION)


def process_message(body):
    data = json.loads(body)
    order_id = data["order_id"]
    print(f"Processing order {order_id} for {data.get('customer_email')}...")

    db.update_order_status(order_id, "PROCESSING")
    time.sleep(2)  # simulate work: inventory check, payment capture, etc.

    print(f"Order {order_id} is PROCESSING and awaiting admin approval.")


def main():
    if not Config.SQS_QUEUE_URL:
        print("SQS_QUEUE_URL not set. Exiting.")
        return

    print("Worker started. Long-polling SQS...")
    while True:
        resp = sqs.receive_message(
            QueueUrl=Config.SQS_QUEUE_URL,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=20,
        )
        messages = resp.get("Messages", [])
        for msg in messages:
            try:
                process_message(msg["Body"])
                sqs.delete_message(QueueUrl=Config.SQS_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
            except Exception as e:
                print(f"Error processing message: {e}")


if __name__ == "__main__":
    main()
