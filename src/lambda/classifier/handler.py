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
SQS_QUEUE_URL_GMAIL = os.environ["OUTPUT_SQS_URL_GMAIL"]
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
Your job is to classify emails. There are 2 main "types" of emails:

1. From Google / Gmail asking for approval to accept forwarded emails
2. Needs to be evaluated against criteria to determine if the content of the email is important enough to warrant immediate notification of the user

The output should be JSON, in the following structure:

{
  "worth_reading": true | false,
  "email": "some.user@gmail.com",
  "gmail_forward_confirm_link": "<confirmation URL or null>",
  "reason": "Natural, human-sounding explanation — friendly and short, as if texting the user. Start with 'You received an email that...' or something similar."
}

Here is an example of a Gmail forwarding confirmation email. The wording may vary slightly, but the key indicator is that it contains a Google link to confirm mail forwarding.

some.user@gmail.com has requested to automatically forward mail to your email 
address forward@needl.email.

To allow some.user@gmail.com to automatically forward mail to your address, 
please click the link below to confirm the request:

https://mail-settings.google.com/mail/vf-%5BANGjdJ-EGO3oLBDGs9jEpsIHXxv-J3-LlxFwjRVmw4QtscIdaU90vyKOn1GJRpm-59zaeZpnHprqmV8ht_we%5D-gtpgtw7AH8vLXayx1LA0w5lH3sc

If you click the link and it appears to be broken, please copy and paste it
into a new browser window.

Thanks for using Gmail!

If you determine that the email is of this type, please extract the URL and place it in the gmail_forward_confirm_link property, and also extract the email address that the request is for and place it email property, and then return.

If you determine that the email is of the second type, please classify it according to the following criteria:

- worth_reading is true if emails are:
  - Personal/conversational (friends, acquaintances)
  - Urgent/time-sensitive (alerts, closures, issues)
  - Actionable (requires reply or action)
  - Highly relevant (family, recruiters, children's activities)

- worth_reading is false if emails are:
  - Routine (receipts, statements, shipping updates)
  - Promotional/commercial (advertisements, sales)
  - Automated/low-value (newsletters, notifications)

Here is the email:

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

            # Classify
            parsed_result, subject = classify_email(email_data)
            
            # First check if its a Gmail forward request
            confirm_link = parsed_result.get("gmail_forward_confirm_link")
            if confirm_link:
                user_email = parsed_result.get("email")
                message_body = json.dumps({"email": user_email, "url": confirm_link})
                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL_GMAIL,
                    MessageBody=message_body
                )
                logger.info(f"Found gmail confirmation link: {message_body}")
                return
            
            # Check if there is a record in the "users" table for the "to" address
            user = lookup_user(user_email)

            # Send positive classifications to SQS; no-op otherwise
            if user and parsed_result.get("worth_reading"):
                reason = parsed_result["reason"]
                text = f"{subject}\n\n{reason}"
                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MessageBody=json.dumps({"user_email": user_email, "text": text}),
                )

        except Exception:
            logger.exception("Error processing record")

    return {"statusCode": 200, "body": "Processing complete"}
