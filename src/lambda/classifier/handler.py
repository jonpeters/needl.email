import json
import boto3
import logging
import urllib.parse
import os
import re

# Constants
USERS_TABLE = os.environ.get("USERS_TABLE", "users")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID")
SQS_QUEUE_URL = os.environ["OUTPUT_SQS_URL"]
REGION = os.environ["REGION"]
MAX_PROMPT_TOKENS = 4000
MAX_TOKENS = 512

# AWS Clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=REGION)
sqs = boto3.client("sqs")


# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB Table
users_table = dynamodb.Table(USERS_TABLE)

PROMPT_TEMPLATE = """
You are an AI assistant that helps users decide whether they need to check an email right away. Your job is to explain whether the email is worth their immediate attention.

Mark emails as worth reading if they are:

- Personal and conversational (e.g. from a friend or someone they know)
- Urgent or time-sensitive (e.g. school closures, security alerts, weather issues)
- Actionable (e.g. needs a reply, contains a decision or next step)
- Highly relevant (e.g. from family, recruiters, or about their kids)

Suppress emails that are:

- Routine (e.g. receipts, shipping, statements)
- Promotional or commercial (ads, sales)
- Automated or low-signal (newsletters, onboarding, notifications)

Respond only with a JSON object in this format:

{"worth_reading": true | false, "reason": "Natural, human-sounding explanation — friendly and short, as if texting the user. Start with 'You received an email that...' or something similar."}

Do not include anything outside the JSON.

Subject: {subject}
From: {from}
Body: {body}
"""


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


def trim_token_length(text: str, max_tokens: int = MAX_PROMPT_TOKENS) -> str:
    """Truncate text to roughly fit within a token budget (based on ~4 characters/token)."""
    max_length = max_tokens * 4  # Approximate 4 chars/token
    return text[:max_length]


def safe_json_parse(text: str) -> dict:
    """Attempt to parse JSON from LLM output, fallback to regex fix if needed."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^}]*:.*?\}", text, re.DOTALL)
        if match:
            json_str = re.sub(
                r"(\"reason\"\s*:\s*)([^\"].*?)([\}\n])", r'\1"\2"\3', match.group(0)
            )
            return json.loads(json_str)
        raise ValueError("Could not extract valid JSON from model response")


def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    for record in event.get("Records", []):
        try:
            logger.debug("Raw record: %s", record)

            # read the s3 object specified in the incoming record
            bucket, key = get_s3_record(record)
            email_data = read_json_from_s3(bucket, key)

            # sanity check; all received emails should always have a "to" address
            user_email = email_data.get("to", "").strip().lower()
            if not user_email:
                logger.warning("Missing 'to' email in %s", key)
                continue

            # check if there is a record in the "users" table for the "to" address
            user = lookup_user(user_email)
            if not user:
                logger.info("No user found for %s, skipping.", user_email)

                # if there is not, no need to classify the email as there is no one to notify
                continue

            logger.info("Found user: %s", json.dumps(user))

            # extract additional data from s3 object
            from_email = email_data.get("from", "").strip().lower()
            subject = user_email = email_data.get("subject", "").strip().lower()
            body = user_email = email_data.get("body", "").strip().lower()

            # init the prompt
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

            # call bedrock
            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(bedrock_payload),
            )

            result = json.loads(response["body"].read())
            logger.info("Inference result: " + str(result))

            raw_text = result["content"][0].get("text", "").strip()
            parsed = safe_json_parse(raw_text)

            logger.info("Parsed classification: " + str(parsed))

            # if classified positively, push it to sqs
            if parsed.get("worth_reading"):
                email_data["classification"] = parsed["reason"]
                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL, MessageBody=json.dumps(email_data)
                )

        except Exception:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
