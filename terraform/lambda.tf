
resource "aws_lambda_function" "needl_email_sanitizer" {
  function_name    = "needl-email-sanitizer"
  filename         = "${path.module}/../build/sanitizer.zip"
  role             = aws_iam_role.needl_email_lambda_sanitizer_exec_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = filebase64sha256("${path.module}/../build/sanitizer.zip")
  timeout          = 60

  environment {
    variables = {
      OUTPUT_S3_BUCKET  = aws_s3_bucket.sanitized_storage.bucket
      USER_EMAILS_TABLE = aws_dynamodb_table.user_emails.name
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.ses_email_queue.arn
  function_name    = aws_lambda_function.needl_email_sanitizer.arn
  batch_size       = 10
  enabled          = true
}
