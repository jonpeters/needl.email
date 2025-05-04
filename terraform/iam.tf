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
