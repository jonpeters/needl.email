import json
import boto3
import logging
import re
import os

# Logger setup
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment
PENDING_LINKS_TABLE = os.environ.get("PENDING_LINKS_TABLE", "pending_links")
USERS_TABLE = os.environ.get("USERS_TABLE", "users")

# DynamoDB setup
dynamodb = boto3.resource("dynamodb")
pending_links_table = dynamodb.Table(PENDING_LINKS_TABLE)
users_table = dynamodb.Table(USERS_TABLE)

# Regex for command pattern
LINK_PATTERN = re.compile(r"^/link\s+(\S+)$")


def lambda_handler(event, context):
    logger.info("Event received: %s", json.dumps(event))

    for record in event.get("Records", []):
        try:
            message = json.loads(record["body"])
            chat_id = message.get("chat_id")
            text = message.get("text", "").strip()

            logger.info(f"Chat ID: {chat_id}, Text: {text}")

            # Check for /link pattern
            match = LINK_PATTERN.match(text)
            if not match:
                logger.info("Message is not a /link command. Ignoring.")
                continue

            code = match.group(1)
            logger.info(f"Extracted link code: {code}")

            # Lookup in pending_links table
            pending_resp = pending_links_table.get_item(Key={"link_code": code})
            pending = pending_resp.get("Item")

            if not pending:
                logger.warning(f"No pending link found for code: {code}")
                continue

            user_email = pending.get("user_email")
            if not user_email:
                logger.warning(f"Link code {code} missing user_email.")
                continue

            logger.info(f"Found pending link for {user_email}")

            # Lookup user
            user_resp = users_table.get_item(Key={"email": user_email})
            user = user_resp.get("Item")

            if not user:
                logger.warning(f"No user found for email: {user_email}")
                continue

            # Update user with telegram_id
            users_table.update_item(
                Key={"email": user_email},
                UpdateExpression="SET telegram_id = :tid",
                ExpressionAttributeValues={":tid": str(chat_id)},
            )

            logger.info(f"✅ Linked Telegram ID {chat_id} to user {user_email}")
            
            # Delete the pending link entry
            pending_links_table.delete_item(Key={"link_code": code})
            logger.info(f"🗑️ Deleted pending link: {code}")

        except Exception as e:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
