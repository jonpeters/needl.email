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

# trust policy for lambda
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
        Resource = "arn:aws:s3:::${aws_s3_bucket.sanitized_storage.bucket}/*"
      },
      {
        Effect = "Allow",
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        Resource = aws_sqs_queue.ses_email_queue.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.needl_email_lambda_sanitizer_exec_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}
