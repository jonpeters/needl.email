import json
import logging
import requests
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.client("dynamodb")
USERS_TABLE_NAME = "users"


def lambda_handler(event, context):
    """
    Lambda handler triggered by SQS events.

    For each message, this function:
    - Parses the JSON body for 'email' and 'url'
    - Sends a POST request to the Gmail confirmation URL (following redirects)
    - If the response is HTTP 200, it updates the corresponding user record in DynamoDB
      by setting 'forward_confirmed' = true for that email
    - If any step fails, the error is logged and re-raised so SQS can retry the message
    """

    for record in event["Records"]:
        try:
            # Log the raw message body
            logger.info("Received SQS event body: %s", record["body"])
            body = json.loads(record["body"])

            email = body.get("email")
            url = body.get("url")

            if not email or not url:
                raise ValueError(f"Missing email or url in body: {body}")

            logger.info(f"Processing URL confirmation for {email}: {url}")

            # Send POST request and follow redirects (like curl -L -X POST)
            response = requests.post(url, allow_redirects=True)

            logger.info(
                f"POST completed. Status: {response.status_code} | Final URL: {response.url}"
            )

            # Only consider successful if we get HTTP 200
            if response.status_code != 200:
                raise Exception(
                    f"Non-200 response from Gmail forward confirmation: {response.status_code} | Body: {response.text[:300]}"
                )

            # Upsert 'forward_confirmed' = true in DynamoDB users table
            dynamodb.update_item(
                TableName=USERS_TABLE_NAME,
                Key={"email": {"S": email}}, 
                UpdateExpression="SET forward_confirmed = :val",
                ExpressionAttributeValues={":val": {"BOOL": True}},
            )
            logger.info(f"DynamoDB updated: forward_confirmed = true for {email}")

        except Exception as e:
            # Log the error with traceback, then re-raise to trigger SQS retry
            logger.error(
                f"Error processing message for email: {body.get('email', 'unknown')}",
                exc_info=True,
            )
            raise

    return {"statusCode": 200, "body": "Processed all messages"}
