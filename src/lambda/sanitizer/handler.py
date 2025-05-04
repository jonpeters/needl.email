import json
import os
import re
import boto3
import logging
from bs4 import BeautifulSoup
from email import policy
from email.parser import BytesParser
from email.header import decode_header, make_header

# Set up logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3 = boto3.client("s3")

# Destination bucket is passed via environment variable
OUTPUT_S3_BUCKET = os.environ["OUTPUT_S3_BUCKET"]

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

            # Parse the email using Python's email module
            msg = BytesParser(policy=policy.default).parsebytes(raw_email)
            sender = msg.get("From", "unknown")
            subject = decode_mime_words(msg.get("Subject", ""))
            body_text = extract_body(msg)

            # Build the output JSON
            cleaned = {
                "from": sender,
                "subject": subject,
                "body": body_text
            }

            # Step 6: Write to cleaned bucket with safe key
            base_key = os.path.basename(key).split(".")[0]
            output_key = f"{base_key}.json"

            s3.put_object(
                Bucket=OUTPUT_S3_BUCKET,
                Key=output_key,
                Body=json.dumps(cleaned, indent=2),
                ContentType="application/json"
            )

            logger.info("Wrote cleaned email to s3://%s/%s", OUTPUT_S3_BUCKET, output_key)

        except Exception as e:
            logger.exception("Failed to process record")
