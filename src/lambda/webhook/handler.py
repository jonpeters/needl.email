import json
import os
import boto3
import logging

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# SQS configuration
SQS_QUEUE_URL = os.environ.get("OUTPUT_SQS_URL")
sqs = boto3.client("sqs")


def lambda_handler(event, context):
    try:
        # Step 1: Extract and parse the raw body
        raw_body = event.get("body", "{}")
        telegram_event = json.loads(raw_body)

        # Step 2: Extract chat ID and message text
        message = telegram_event.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        user_text = message.get("text", "")

        logger.info(f"Chat ID: {chat_id}")
        logger.info(f"User message: {user_text}")

        # Step 3: Send to SQS
        payload = {
            "chat_id": chat_id,
            "text": user_text,
        }

        sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(payload))

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception as e:
        logger.exception("Failed to process Telegram webhook event")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
