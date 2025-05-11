import json
import os
import boto3
import logging
import re

# Logger setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SQS_QUEUE_URL = os.environ.get("OUTPUT_SQS_URL")
PENDING_LINKS_TABLE = os.environ.get("PENDING_LINKS_TABLE", "pending_links")
USERS_TABLE = os.environ.get("USERS_TABLE", "users")
TELEGRAM_TABLE = os.environ.get("TELEGRAM_TABLE", "telegram")

# AWS clients
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

# DynamoDB tables
telegram_table = dynamodb.Table(TELEGRAM_TABLE)
pending_links_table = dynamodb.Table(PENDING_LINKS_TABLE)
users_table = dynamodb.Table(USERS_TABLE)

# Regex for detecting /link command
LINK_PATTERN = re.compile(r"^/link\s+(\S+)$")


def handle_link_command(chat_id, link_code, user_text):
    """Handle the /link command from a Telegram message."""
    logger.info("Processing a /link command")

    pending_resp = pending_links_table.get_item(Key={"link_code": link_code})
    pending = pending_resp.get("Item")

    if not pending:
        logger.warning(f"No pending link found for code: {link_code}")
        return None

    user_email = pending.get("user_email")
    if not user_email:
        logger.warning(f"Link code {link_code} missing user_email.")
        return None

    user_resp = users_table.get_item(Key={"email": user_email})
    user = user_resp.get("Item")

    if not user:
        logger.warning(f"No user found for email: {user_email}")
        return None

    # Update user with telegram_id
    users_table.update_item(
        Key={"email": user_email},
        UpdateExpression="SET telegram_id = :tid",
        ExpressionAttributeValues={":tid": str(chat_id)},
    )

    telegram_payload = {"telegram_id": str(chat_id), "user_email": user_email}
    telegram_table.put_item(Item=telegram_payload)

    pending_links_table.delete_item(Key={"link_code": link_code})

    logger.info(f"Linked Telegram ID {chat_id} to user {user_email}")
    logger.info(f"Deleted pending link: {link_code}")

    payload = {"user_email": user_email, "text": user_text}
    return payload


def handle_regular_message(chat_id, user_text):
    """Handle any regular message (non-/link) from Telegram."""
    try:
        response = telegram_table.get_item(Key={"telegram_id": chat_id})
        user_email = response["Item"]["user_email"]
        logger.info(f"Retrieved user_email: {user_email}")
    except Exception as e:
        logger.error(f"No user_email found for telegram_id: {chat_id}")

    return {"user_email": user_email, "text": user_text}


def lambda_handler(event, context):
    """Main handler for Telegram webhook Lambda."""
    try:
        telegram_event = json.loads(event.get("body", "{}"))
        message = telegram_event.get("message", {})

        chat_id = str(message.get("chat", {}).get("id")).strip()
        user_text = message.get("text", "")

        logger.info(f"Chat ID: {chat_id}")
        logger.info(f"User message: {user_text}")

        match = LINK_PATTERN.match(user_text)
        if match:
            payload = handle_link_command(chat_id, match.group(1), user_text)
        else:
            payload = handle_regular_message(chat_id, user_text)

        sqs.send_message(QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(payload))

        return {"statusCode": 200, "body": json.dumps({"status": "ok"})}

    except Exception as e:
        logger.exception("Failed to process Telegram webhook event")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
