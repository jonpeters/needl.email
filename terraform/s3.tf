data "aws_s3_bucket" "needl-bucket" {
  bucket = local.bucket
}

resource "aws_s3_bucket_notification" "email_event_to_sqs" {
  bucket = local.bucket

  queue {
    queue_arn     = aws_sqs_queue.ses_email_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = ""
  }

  depends_on = [aws_sqs_queue_policy.allow_s3_publish]
}
