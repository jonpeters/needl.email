import json
import boto3
import logging
import urllib.parse
import os
import re

# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
USERS_TABLE = os.environ.get("USERS_TABLE", "users")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID")
SQS_QUEUE_URL = os.environ["OUTPUT_SQS_URL"]
REGION = os.environ["REGION"]

# Constants
MAX_PROMPT_TOKENS = 4000
MAX_TOKENS = 512

# AWS Clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=REGION)
sqs = boto3.client("sqs")

users_table = dynamodb.Table(USERS_TABLE)

PROMPT_TEMPLATE = """
You are an AI assistant that helps users decide whether they need to check an email right away. Your job is to classify emails to determine if they require immediate attention.

Respond only with a JSON object in this format:
{
  "worth_reading": true | false,
  "gmail_forward_confirm_link": "<confirmation URL or null>",
  "reason": "Natural, human-sounding explanation — friendly and short, as if texting the user. Start with 'You received an email that...' or something similar."
}

Classify emails as follows:

- worth_reading is true if emails are:
  - Personal/conversational (friends, acquaintances)
  - Urgent/time-sensitive (alerts, closures, issues)
  - Actionable (requires reply or action)
  - Highly relevant (family, recruiters, children's activities)

- worth_reading is false if emails are:
  - Routine (receipts, statements, shipping updates)
  - Promotional/commercial (advertisements, sales)
  - Automated/low-value (newsletters, notifications)

Additionally:
- If the email is specifically a Gmail forwarding confirmation request (contains phrases like "requested to automatically forward mail") **and** the sender's email address is clearly from an official Google domain (e.g., ending with "@gmail.com" or "@google.com"), set gmail_forward_confirm_link to the exact confirmation URL provided in the email body.
- Otherwise, set gmail_forward_confirm_link to null.

Subject: {subject}
From: {from}
Body: {body}
"""


def get_s3_record(record):
    """Extract the bucket and key from an SQS-triggered S3 event."""
    body = json.loads(record["body"])
    s3_event = (
        json.loads(body["Records"][0]) if isinstance(body["Records"][0], str) else body
    )
    s3_info = s3_event["Records"][0]["s3"]
    bucket = s3_info["bucket"]["name"]
    key = urllib.parse.unquote_plus(s3_info["object"]["key"])
    return bucket, key


def read_json_from_s3(bucket, key):
    """Fetch and parse JSON content from an S3 object."""
    logger.info(f"Reading file from s3://{bucket}/{key}")
    response = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def lookup_user(email):
    """Retrieve user information from DynamoDB by email."""
    response = users_table.get_item(Key={"email": email})
    return response.get("Item")


def trim_token_length(text, max_tokens=MAX_PROMPT_TOKENS):
    """Trim text to fit approximately within token limits."""
    return text[: max_tokens * 4]  # Roughly 4 characters per token


def safe_json_parse(text):
    """Attempt to safely parse JSON, with fallback handling."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^}]*:.*?\}", text, re.DOTALL)
        if match:
            fixed_json = re.sub(
                r"(\"reason\"\s*:\s*)([^\"].*?)([}\n])", r'\1"\2"\3', match.group(0)
            )
            return json.loads(fixed_json)
        raise ValueError("Could not extract valid JSON")


def classify_email(email_data):
    """Classify email content using an AI model."""
    from_email = email_data.get("from", "").strip().lower()
    subject = email_data.get("subject", "").strip()
    body = email_data.get("body", "").strip()

    prompt = trim_token_length(
        PROMPT_TEMPLATE.replace("{from}", from_email)
        .replace("{subject}", subject)
        .replace("{body}", body)
    )

    bedrock_payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(bedrock_payload),
    )

    result = json.loads(response["body"].read())
    parsed = safe_json_parse(result["content"][0]["text"].strip())
    return parsed, subject


def lambda_handler(event, context):
    """Lambda handler to classify emails and forward important ones."""
    logger.info("Received event: %s", json.dumps(event))

    for record in event.get("Records", []):
        try:
            bucket, key = get_s3_record(record)
            email_data = read_json_from_s3(bucket, key)

            # Sanity check; all received emails should always have a "to" address
            user_email = email_data.get("to", "").strip().lower()
            if not user_email:
                logger.warning("Missing 'to' email in %s", key)
                continue

            # Check if there is a record in the "users" table for the "to" address
            user = lookup_user(user_email)

            # Don't bother classifying if there is no user record
            if not user:
                logger.info("No user found for %s", user_email)
                continue

            # Classify
            parsed_result, subject = classify_email(email_data)

            # Send positive classifications to SQS; no-op otherwise
            if parsed_result.get("worth_reading"):
                reason = parsed_result["reason"]
                text = f"{subject}\n\n{reason}"
                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MessageBody=json.dumps({"user_email": user_email, "text": text}),
                )

        except Exception:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
