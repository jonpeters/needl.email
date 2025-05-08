import json
import boto3
import os
import logging
import requests 

# Constants
TELEGRAM_BOT_ID = os.environ.get("TELEGRAM_BOT_ID")
USERS_TABLE = os.environ.get("USERS_TABLE", "users")

# Clients
dynamodb = boto3.resource("dynamodb")

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB Table
users_table = dynamodb.Table(USERS_TABLE)


def send_telegram_notification(bot_token: str, chat_id: str, message: str) -> dict:
    """Send a message using the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()


def lookup_user(email: str) -> dict | None:
    """Retrieve a user record from DynamoDB by email."""
    response = users_table.get_item(Key={"email": email})
    return response.get("Item")


def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))

    for record in event.get("Records", []):
        try:
            # Parse SQS message body (assumed to be JSON)
            message = json.loads(record["body"])

            # Extract recipient email
            to_email = message.get("to", "").strip().lower()
            if not to_email:
                logger.warning("No 'to' address found in message.")
                continue

            # Lookup user in DynamoDB
            user = lookup_user(to_email)
            if not user:
                logger.info(f"No user found for email: {to_email}")
                continue

            telegram_id = user.get("telegram_id")
            if not telegram_id:
                logger.warning(f"User {to_email} does not have a telegram_id.")
                continue

            classification = message.get("classification", "")
            if not classification:
                logger.warning("No classification found in message.")
                continue
            
            message = f"{message.get("subject", "")}\n\n{classification}"

            logger.info(f"Sending Telegram message to {telegram_id}: {classification}")
            send_resp = send_telegram_notification(
                TELEGRAM_BOT_ID, telegram_id, classification
            )
            logger.info("Telegram response: %s", send_resp)

        except Exception as e:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
