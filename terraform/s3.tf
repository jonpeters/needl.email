data "aws_s3_bucket" "needl-bucket-raw" {
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

resource "aws_s3_bucket" "s3_bucket_sanitized" {
  bucket        = "${var.app_name}-storage-sanitized"
  force_destroy = true
}

resource "aws_s3_bucket_notification" "sanitized_event_to_sns" {
  bucket = aws_s3_bucket.s3_bucket_sanitized.bucket

  topic {
    topic_arn = aws_sns_topic.email_events.arn
    events    = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_sns_topic_policy.allow_sanitized_s3_publish]
}
