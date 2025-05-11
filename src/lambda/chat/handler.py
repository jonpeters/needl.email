import json
import boto3
import logging
import os

# Logger setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SQS_QUEUE_URL = os.environ["OUTPUT_SQS_URL"]

# AWS Clients
sqs = boto3.client("sqs")

# DynamoDB setup (future use)
dynamodb = boto3.resource("dynamodb")


def lambda_handler(event, context):
    """Currently, this lambda acts only as a pass-through, forwarding messages directly to SQS.
    In the future, chat history will be updated in DynamoDB here."""
    logger.info("Event received: %s", json.dumps(event))

    for record in event.get("Records", []):
        try:
            message = json.loads(record["body"])
            user_email = message.get("user_email")
            text = message.get("text", "").strip()

            logger.info(f"user_email: {user_email}, Text: {text}")

            payload = {
                "user_email": user_email,
                "text": text,
            }

            sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(payload))

        except Exception as e:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
