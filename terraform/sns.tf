resource "aws_sns_topic" "email_events" {
  name = "email-events"
}

# SQS raw queue subscription to SNS
resource "aws_sns_topic_subscription" "classifier_sqs_sub" {
  topic_arn            = aws_sns_topic.email_events.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.sanitized_queue.arn
  raw_message_delivery = true
}