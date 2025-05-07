import json
import boto3
import logging
import urllib.parse
import os

# AWS Clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Constants
USERS_TABLE = os.environ.get("USERS_TABLE", "users")

# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB Table
users_table = dynamodb.Table(USERS_TABLE)


def get_s3_record(record: dict) -> tuple[str, str]:
    """Extract the S3 bucket and key from an SQS-wrapped S3 event."""
    body = json.loads(record["body"])
    s3_event = (
        json.loads(body["Records"][0]) if isinstance(body["Records"][0], str) else body
    )
    s3_info = s3_event["Records"][0]["s3"]

    bucket = s3_info["bucket"]["name"]
    key = urllib.parse.unquote_plus(s3_info["object"]["key"])
    return bucket, key


def read_json_from_s3(bucket: str, key: str) -> dict:
    """Fetch and parse a JSON file from S3."""
    logger.info(f"Reading file from s3://{bucket}/{key}")
    response = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def lookup_user(email: str) -> dict | None:
    """Retrieve a user record from DynamoDB by email."""
    response = users_table.get_item(Key={"email": email})
    return response.get("Item")


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    for record in event.get("Records", []):
        try:
            logger.debug("Raw record: %s", record)

            bucket, key = get_s3_record(record)
            email_data = read_json_from_s3(bucket, key)

            user_email = email_data.get("to", "").strip().lower()
            if not user_email:
                logger.warning("Missing 'to' email in %s", key)
                continue

            user = lookup_user(user_email)
            if not user:
                logger.info("No user found for %s, skipping.", user_email)
                continue

            logger.info("Found user: %s", json.dumps(user))

        except Exception:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
