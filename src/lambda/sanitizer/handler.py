import json
import os
import re
import boto3
import logging
from bs4 import BeautifulSoup
from email import policy
from email.parser import BytesParser
from email.header import decode_header, make_header
from email.utils import parseaddr
from datetime import datetime

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

# Environment vars
OUTPUT_S3_BUCKET = os.environ["OUTPUT_S3_BUCKET"]
USER_EMAILS_TABLE = os.environ["USER_EMAILS_TABLE"]

# DynamoDB table object
user_emails_table = dynamodb.Table(USER_EMAILS_TABLE)

def clean_text(text: str) -> str:
    """Strip HTML tags and normalize whitespace in email content."""
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(separator=" ", strip=True)
    return re.sub(r'\s+', ' ', cleaned).strip()

def decode_mime_words(s: str) -> str:
    """Decode MIME-encoded email subject strings."""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s

def extract_body(msg):
    """Extract plain text or fallback to cleaned HTML."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_content()
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return clean_text(part.get_content())
    return ""

def lambda_handler(event, context):
    logger.info("Processing %d records", len(event["Records"]))

    for record in event["Records"]:
        try:
            # Parse the outer SQS message body
            sqs_body = json.loads(record["body"])
            s3_event = json.loads(sqs_body["Message"]) if "Message" in sqs_body else sqs_body

            # Get bucket and key from the inner S3 event
            s3_info = s3_event["Records"][0]["s3"]
            bucket = s3_info["bucket"]["name"]
            key = s3_info["object"]["key"]

            logger.info("Fetching email from s3://%s/%s", bucket, key)

            # Download the raw email
            response = s3.get_object(Bucket=bucket, Key=key)
            raw_email = response["Body"].read()

            # Parse the email
            msg = BytesParser(policy=policy.default).parsebytes(raw_email)
            from_name, from_email = parseaddr(msg.get("From", "unknown"))
            subject = decode_mime_words(msg.get("Subject", ""))
            body_text = extract_body(msg)

            # Write cleaned body to S3
            base_key = os.path.basename(key).split(".")[0]
            output_key = f"{base_key}.txt"
            s3_path = f"s3://{OUTPUT_S3_BUCKET}/{output_key}"

            s3.put_object(
                Bucket=OUTPUT_S3_BUCKET,
                Key=output_key,
                Body=body_text,
                ContentType="application/json"
            )

            logger.info("Wrote cleaned email to %s", s3_path)

            # Insert metadata into user_emails table
            now = datetime.utcnow().isoformat(timespec="milliseconds")
            user_emails_table.put_item(
                Item={
                    "user_email": from_email,
                    "display_name": from_name,
                    "timestamp": now,
                    "s3_path": s3_path,
                    "subject": subject
                }
            )

            logger.info("Inserted record into user_emails for %s", from_email)

        except Exception:
            logger.exception("Failed to process record")
