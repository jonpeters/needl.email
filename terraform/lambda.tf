
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
      OUTPUT_S3_BUCKET  = aws_s3_bucket.s3_bucket_sanitized.bucket
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


resource "aws_lambda_function" "needl_email_classifier" {
  function_name    = "needl-email-classifier"
  filename         = "${path.module}/../build/classifier.zip"
  role             = aws_iam_role.needl_email_lambda_classifier_exec_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = filebase64sha256("${path.module}/../build/classifier.zip")
  timeout          = 60

  environment {
    variables = {
      USER_EMAILS_TABLE = aws_dynamodb_table.user_emails.name
      BEDROCK_MODEL_ID  = local.bedrock_model_id
      OUTPUT_SQS_URL    = aws_sqs_queue.chat_queue.url
      REGION            = var.aws_region
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger_classifier" {
  event_source_arn = aws_sqs_queue.sanitized_queue.arn
  function_name    = aws_lambda_function.needl_email_classifier.arn
  batch_size       = 10
  enabled          = true
}

resource "aws_lambda_function" "needl_email_notifier" {
  function_name    = "needl-email-notifier"
  filename         = "${path.module}/../build/notifier.zip"
  role             = aws_iam_role.needl_email_lambda_notifier_exec_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = filebase64sha256("${path.module}/../build/notifier.zip")
  timeout          = 60

  environment {
    variables = {
      USER_EMAILS_TABLE = aws_dynamodb_table.user_emails.name
      TELEGRAM_BOT_ID   = var.telegram_id
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger_notifier" {
  event_source_arn = aws_sqs_queue.notify_queue.arn
  function_name    = aws_lambda_function.needl_email_notifier.arn
  batch_size       = 10
  enabled          = true
}

resource "aws_lambda_function" "needl_email_webhook" {
  function_name    = "needl-email-webhook"
  filename         = "${path.module}/../build/webhook.zip"
  role             = aws_iam_role.needl_email_lambda_webhook_exec_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = filebase64sha256("${path.module}/../build/webhook.zip")
  timeout          = 60

  environment {
    variables = {
      OUTPUT_SQS_URL = aws_sqs_queue.chat_queue.url
    }
  }
}

resource "aws_lambda_function_url" "needl_email_webhook_url" {
  function_name      = aws_lambda_function.needl_email_webhook.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_function" "needl_email_chat" {
  function_name    = "needl-email-chat"
  filename         = "${path.module}/../build/chat.zip"
  role             = aws_iam_role.needl_email_lambda_chat_exec_role.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = filebase64sha256("${path.module}/../build/chat.zip")
  timeout          = 60

  environment {
    variables = {
      OUTPUT_SQS_URL = aws_sqs_queue.notify_queue.url
    }
  }
}

resource "aws_lambda_event_source_mapping" "sqs_trigger_chat" {
  event_source_arn = aws_sqs_queue.chat_queue.arn
  function_name    = aws_lambda_function.needl_email_chat.arn
  batch_size       = 10
  enabled          = true
}