resource "aws_sqs_queue" "ses_email_queue" {
  name                       = "${var.app_name}-raw"
  visibility_timeout_seconds = 60
}

resource "aws_sqs_queue" "sanitized_queue" {
  name                       = "${var.app_name}-sanitized"
  visibility_timeout_seconds = 60
}

resource "aws_sqs_queue" "classified_queue" {
  name                       = "${var.app_name}-classified"
  visibility_timeout_seconds = 60
}

resource "aws_sqs_queue" "webhook_queue" {
  name                       = "${var.app_name}-webhook"
  visibility_timeout_seconds = 60
}
