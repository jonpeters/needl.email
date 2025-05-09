# trust policy to allow SES to publish to the raw bucket
resource "aws_sqs_queue_policy" "allow_s3_publish" {
  queue_url = aws_sqs_queue.ses_email_queue.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = { Service = "s3.amazonaws.com" },
        Action    = "sqs:SendMessage",
        Resource  = aws_sqs_queue.ses_email_queue.arn,
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:s3:::${local.bucket}"
          }
        }
      }
    ]
  })
}

# trust policy for sanitizer lambda
resource "aws_iam_role" "needl_email_lambda_sanitizer_exec_role" {
  name = "needl-email-lambda-sanitizer-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# sanitizer lambda policy
resource "aws_iam_policy" "lambda_policy" {
  name = "lambda-email-processing-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject"
        ],
        Resource = "arn:aws:s3:::${data.aws_s3_bucket.needl-bucket-raw.bucket}/*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:PutObject"
        ],
        Resource = "arn:aws:s3:::${aws_s3_bucket.s3_bucket_sanitized.bucket}/*"
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.ses_email_queue.arn
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem"
        ],
        Resource = aws_dynamodb_table.user_emails.arn
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.needl_email_lambda_sanitizer_exec_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# allow sanitized s3 bucket to publish to sqs
resource "aws_sqs_queue_policy" "allow_s3_sanitized_publish" {
  queue_url = aws_sqs_queue.sanitized_queue.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = { Service = "s3.amazonaws.com" },
        Action    = "sqs:SendMessage",
        Resource  = aws_sqs_queue.sanitized_queue.arn,
        Condition = {
          ArnLike = {
            "aws:SourceArn" = aws_s3_bucket.s3_bucket_sanitized.arn
          }
        }
      }
    ]
  })
}

# trust policy for classifier lambda
resource "aws_iam_role" "needl_email_lambda_classifier_exec_role" {
  name = "needl-email-lambda-classifier-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "classifier_lambda_policy" {
  name = "lambda-classifier-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject"
        ],
        Resource = "${aws_s3_bucket.s3_bucket_sanitized.arn}/*"
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.sanitized_queue.arn
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:SendMessage"
        ],
        Resource = aws_sqs_queue.classified_queue.arn
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem"
        ],
        Resource = aws_dynamodb_table.users.arn
      },
      {
        Sid    = "AllowInvokeBedrockModel",
        Effect = "Allow",
        Action = [
          "bedrock:InvokeModel"
        ],
        Resource = "arn:aws:bedrock:us-east-1::foundation-model/${local.bedrock_model_id}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_classifier_attachment" {
  role       = aws_iam_role.needl_email_lambda_classifier_exec_role.name
  policy_arn = aws_iam_policy.classifier_lambda_policy.arn
}

resource "aws_iam_role" "needl_email_lambda_notifier_exec_role" {
  name = "needl-email-lambda-notifier-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "notifier_lambda_policy" {
  name = "lambda-notifier-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.classified_queue.arn
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem"
        ],
        Resource = aws_dynamodb_table.users.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_notifier_attachment" {
  role       = aws_iam_role.needl_email_lambda_notifier_exec_role.name
  policy_arn = aws_iam_policy.notifier_lambda_policy.arn
}

resource "aws_iam_role" "needl_email_lambda_webhook_exec_role" {
  name = "needl-email-lambda-webhook-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "webhook_lambda_policy" {
  name = "lambda-webhook-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:SendMessage"
        ],
        Resource = aws_sqs_queue.webhook_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_webhook_attachment" {
  role       = aws_iam_role.needl_email_lambda_webhook_exec_role.name
  policy_arn = aws_iam_policy.webhook_lambda_policy.arn
}

resource "aws_iam_role" "needl_email_lambda_chat_exec_role" {
  name = "needl-email-lambda-chat-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Action = "sts:AssumeRole",
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_policy" "chat_lambda_policy" {
  name = "lambda-chat-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.webhook_queue.arn
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ],
        Resource = aws_dynamodb_table.users.arn
      },
      {
        Effect = "Allow",
        Action = [
          "dynamodb:GetItem",
          "dynamodb:DeleteItem"
        ],
        Resource = aws_dynamodb_table.pending_links.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_chat_attachment" {
  role       = aws_iam_role.needl_email_lambda_chat_exec_role.name
  policy_arn = aws_iam_policy.chat_lambda_policy.arn
}
